
# DeployBox

DeployBox is an AWS serverless static website deployment platform.

It allows users to deploy public GitHub repositories containing prebuilt static websites through a web dashboard.

## Technologies

- Python 3.13
- AWS Lambda
- Amazon API Gateway
- Amazon DynamoDB
- Amazon S3
- Amazon SNS
- AWS SAM
- HTML, CSS and JavaScript
- Git and GitHub

## Architecture

```text
User
 |
 v
DeployBox Dashboard (S3)
 |
 v
Amazon API Gateway
 |
 +-- POST /webhook
 |     |
 |     v
 |   Webhook Lambda
 |     |
 |     +--> DynamoDB
 |     |
 |     v
 |   Deploy Engine Lambda
 |     |
 |     +--> GitHub ZIP archive
 |     |
 |     +--> S3 website hosting
 |     |
 |     +--> DynamoDB status
 |     |
 |     v
 |   Notifier Lambda
 |     |
 |     v
 |   Amazon SNS
 |
 +-- GET /deployments
 |     |
 |     v
 |   List Deployments Lambda
 |
 +-- GET /deployments/{deploymentId}
       |
       v
     Get Deployment Lambda
```

## Features

### GitHub website deployment

Users enter a public GitHub repository in the format:

`owner/repository`

DeployBox downloads the repository archive and publishes its static files to Amazon S3.

The repository must contain `index.html` at its root.

### Deployment tracking

Deployments are stored in DynamoDB.

Supported statuses include:

- RECEIVED
- BUILDING
- DEPLOYED
- FAILED

### Deployment history

The dashboard displays repository names, deployment IDs, statuses, timestamps and website links.

### Deployment details

Users can inspect deployment information, uploaded file counts and failure messages.

### Notifications

DeployBox invokes a notifier Lambda when deployments succeed or fail.

The notifier publishes messages to Amazon SNS.

To receive email notifications, an email subscription must be created and confirmed.

### Error handling

DeployBox validates repository names, Git references and ZIP archives.

Failed deployments are recorded in DynamoDB.

## Project structure

```text
Deploybox/
├── dashboard/
│   └── index.html
├── infra/
│   └── template.yaml
├── src/
│   ├── webhook_handler/
│   │   └── app.py
│   ├── deploy_engine/
│   │   └── app.py
│   ├── list_deployments/
│   │   └── app.py
│   ├── get_deployment/
│   │   └── app.py
│   └── notifier/
│       └── app.py
├── scripts/
│   └── smoke-test.sh
├── tests/
│   └── test_deploybox.py
└── README.md
```

## Requirements

- AWS account
- AWS CLI
- AWS SAM CLI
- Python 3.13
- Git
- A public GitHub repository containing a static website

AWS service charges may apply.

## Deployment

Validate the template:

```bash
sam validate --template-file infra/template.yaml
```

Build:

```bash
sam build --template-file infra/template.yaml
```

Deploy:

```bash
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name deploybox-stack \
  --region us-east-1 \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --confirm-changeset
```

Review the CloudFormation change set before approving it.

Do not approve unexpected replacements or deletions of existing S3 buckets or the DynamoDB table.

## Dashboard

API endpoint:

https://klrm3es403.execute-api.us-east-1.amazonaws.com/Prod

Dashboard:

http://deploybox-dashboard-977476317634.s3-website-us-east-1.amazonaws.com

Upload the dashboard:

```bash
aws s3 cp dashboard/index.html \
  s3://deploybox-dashboard-977476317634/index.html \
  --content-type text/html \
  --region us-east-1
```

## API endpoints

### POST /webhook

Queues a deployment.

Example request:

```json
{
  "repository": {
    "full_name": "mdn/beginner-html-site-styled"
  }
}
```

Successful requests return HTTP 202 and a deployment ID.

### GET /deployments

Returns a page of deployment history.

Supports `limit`, `repo` and `cursor` query parameters.

History is sorted within each scanned page, not globally.

### GET /deployments/{deploymentId}

Returns one deployment record.

### OPTIONS /webhook

Handles browser CORS preflight requests.

## Testing

Run local unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Run live API checks:

```bash
bash scripts/smoke-test.sh
```

Optionally queue a deployment:

```bash
REPO=mdn/beginner-html-site-styled \
  bash scripts/smoke-test.sh
```

After queueing, verify the deployment reaches DEPLOYED and the website opens.

## Deployment limitations

- Public GitHub repositories only.
- Static HTML, CSS, JavaScript and assets only.
- No npm or framework build step.
- Root-level index.html required.
- ZIP archive limit: 15 MB.
- Extracted file limit: 30 MB.
- Maximum deployable files: 250.
- No support for private repositories.

## Security limitations

This is a demonstration application, not a production-secure hosting service.

Current limitations include:

- Unauthenticated deployment API.
- No API rate limiting.
- Public S3 website hosting over HTTP.
- No CloudFront HTTPS distribution.
- No GitHub webhook signature verification.
- No automatic deployment on GitHub push.
- No user accounts or access control.

Do not use sensitive repositories or credentials.

Production improvements should include authentication, authorization, abuse protection, private S3 hosting behind CloudFront, and cost monitoring.

## Verification status

The previous AWS deployment successfully deployed a public GitHub static website.

The final source changes must still pass local tests and be deployed and verified against AWS.

## Conclusion

DeployBox demonstrates how AWS serverless services can work together to automate static website deployment.

It combines API Gateway, Lambda, DynamoDB, S3 and SNS into a single deployment workflow.
