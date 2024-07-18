"""
This script streams logs from a Docker container to AWS CloudWatch Logs.

It initializes connections to AWS (for CloudWatch Logs) and Docker, creates necessary
log groups and streams if they do not exist, starts a Docker container to execute a
given command, streams its logs, and pushes them in batches to CloudWatch Logs.

Required Python packages: boto3, docker

Command-line arguments:
    --docker-image: Docker image to run (required)
    --bash-command: Bash command to execute within the Docker container (required)
    --aws-cloudwatch-group: AWS CloudWatch Logs log group name (required)
    --aws-cloudwatch-stream: AWS CloudWatch Logs log stream name (required)
    --aws-access-key-id: AWS Access Key ID (required)
    --aws-secret-access-key: AWS Secret Access Key (required)
    --aws-region: AWS region (required)
"""
import argparse
import boto3
import docker
import time
import datetime
import logging

from botocore.client import BaseClient
from botocore.exceptions import ClientError

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


def create_log_group(client: BaseClient, log_group_name: str) -> None:
    """
    Creates a new log group in AWS CloudWatch Logs.

    Args:
        client (boto3.client): AWS CloudWatch Logs client
        log_group_name (str): Name of the log group to create
    """
    try:
        client.create_log_group(logGroupName=log_group_name)
        logger.info(f"Created log group {log_group_name}")
    except client.exceptions.ResourceAlreadyExistsException:
        logger.info(f"Log group {log_group_name} already exists")


def create_log_stream(client: BaseClient, log_group_name: str, log_stream_name: str) -> None:
    """
    Creates a new log stream in an existing log group in AWS CloudWatch Logs.

    Args:
        client (boto3.client): AWS CloudWatch Logs client
        log_group_name (str): Name of the log group
        log_stream_name (str): Name of the log stream to create
    """
    try:
        client.create_log_stream(logGroupName=log_group_name, logStreamName=log_stream_name)
        logger.info(f"Created log stream {log_stream_name}")
    except client.exceptions.ResourceAlreadyExistsException:
        logger.info(f"Log stream {log_stream_name} already exists")


def push_log_events(
        client: BaseClient,
        log_group_name: str,
        log_stream_name: str,
        log_events: list,
        sequence_token=None
) -> str:
    """
    Pushes log events to a specified log stream in AWS CloudWatch Logs.

    Args:
        client (boto3.client): AWS CloudWatch Logs client
        log_group_name (str): Name of the log group
        log_stream_name (str): Name of the log stream
        log_events (list): List of log events to push
        sequence_token (str, optional): Sequence token for ordering events (default: None)

    Returns:
        str: Next sequence token if successful, otherwise the current sequence token
    """
    if not log_events:
        return sequence_token

    kwargs = {
        'logGroupName': log_group_name,
        'logStreamName': log_stream_name,
        'logEvents': log_events
    }

    if sequence_token:
        kwargs['sequenceToken'] = sequence_token

    try:
        response = client.put_log_events(**kwargs)
        return response['nextSequenceToken']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            logger.warning("Throttling encountered, backing off...")
            time.sleep(2)  # Exponential backoff example
            return push_log_events(client, log_group_name, log_stream_name, log_events, sequence_token)
        else:
            logger.error(f"Failed to push log events: {e}")
            return sequence_token


def main(args):
    """
    Main function to execute the Docker container, stream its logs,
    and push them to AWS CloudWatch Logs.

    Args:
        args (argparse.Namespace): Parsed command-line arguments
    """
    # Initialize AWS and Docker clients
    cloudwatch_client = boto3.client(
        'logs',
        aws_access_key_id=args.aws_access_key_id,
        aws_secret_access_key=args.aws_secret_access_key,
        region_name=args.aws_region
    )

    try:
        create_log_group(cloudwatch_client, args.aws_cloudwatch_group)
        create_log_stream(cloudwatch_client, args.aws_cloudwatch_group, args.aws_cloudwatch_stream)

        client = docker.from_env()
        log_events = []
        sequence_token = None

        # Start Docker container
        container = client.containers.run(
            args.docker_image,
            f"/bin/bash -c '{args.bash_command}'",
            detach=True,
            stdout=True,
            stderr=True
        )

        try:
            # Stream container logs
            for line in container.logs(stream=True, stdout=True, stderr=True):
                message = line.decode('utf-8').strip()
                if message:
                    log_event = {
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).timestamp(),
                        'message': message
                    }
                    log_events.append(log_event)

                    if len(log_events) >= 10:  # Adjust batch size as needed
                        sequence_token = push_log_events(
                            cloudwatch_client,
                            args.aws_cloudwatch_group,
                            args.aws_cloudwatch_stream,
                            log_events,
                            sequence_token
                        )
                        log_events = []

            # Push remaining logs after container exits
            log_events.extend([
                {
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).timestamp(),
                    'message': line.decode('utf-8').strip()
                }
                for line in container.logs(stdout=True, stderr=True) if line.decode('utf-8').strip()
            ])

            # Push any remaining log events
            if log_events:
                push_log_events(
                    cloudwatch_client, args.aws_cloudwatch_group, args.aws_cloudwatch_stream, log_events, sequence_token
                )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")

        finally:
            # Clean up container
            container.stop()
            container.remove()

    except docker.errors.DockerException as e:
        logger.error(f"Docker error: {e}")
    except ClientError as e:
        logger.error(f"AWS error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker-image', required=True)
    parser.add_argument('--bash-command', required=True)
    parser.add_argument('--aws-cloudwatch-group', required=True)
    parser.add_argument('--aws-cloudwatch-stream', required=True)
    parser.add_argument('--aws-access-key-id', required=True)
    parser.add_argument('--aws-secret-access-key', required=True)
    parser.add_argument('--aws-region', required=True)

    args = parser.parse_args()
    main(args)
