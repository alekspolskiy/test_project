# Docker Logs to AWS CloudWatch Logs Streaming

This script facilitates streaming logs from a Docker container to AWS CloudWatch Logs. It initializes connections to AWS and Docker, creates necessary log groups and streams if they do not exist, starts a Docker container to execute a specified command, streams its logs, and pushes them in batches to AWS CloudWatch Logs.

## Prerequisites

Ensure you have the following installed:
- Python 3.x
- Required Python packages: `boto3`, `docker`

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>

2. Install dependencies:
    ```
   pip install -r requirements.txt
   ```

3. Configure AWS credentials:

    Ensure you have AWS Access Key ID, Secret Access Key, and the desired AWS region.

## Usage

Run the script with the following command-line arguments:
```bash
python script_name.py \
    --docker-image <docker-image-name> \
    --bash-command "<bash-command-to-execute>" \
    --aws-cloudwatch-group <cloudwatch-log-group-name> \
    --aws-cloudwatch-stream <cloudwatch-log-stream-name> \
    --aws-access-key-id <aws-access-key-id> \
    --aws-secret-access-key <aws-secret-access-key> \
    --aws-region <aws-region>
```
