# Deploybox
Elective Project

DeployBox — Cloud-Native Static Deployment Platform

Zero servers. Push to deploy. Global CDN in 60 seconds.

Problem
Developers need instant deployment for static sites without managing EC2/NGINX or paying for idle servers. Existing tools hide AWS complexity but charge extra.

DeployBox is a serverless Vercel-clone built 100% on AWS Educate free-tier services.

Architecture
[ GitHub Push ] -> [ API Gateway /webhook ] -> [ Lambda: Webhook Handler ] -> [ DynamoDB Log ]
                                                |
                                                v
                                      [ Lambda: Deploy Engine ]
                                                |
                                +---------------+---------------+
                                |                               |
                        [ S3 Deploy Bucket ]          [ DynamoDB Update ]
                                |
                        [ CloudFront Invalidation ]
                                |
                        [ SNS Email Alert ]

Why This Design?

S3 + CloudFront vs EC2 + NGINX:
EC2 costs $0.0116/hr even idle, needs patching, scaling. S3 is $0.023/GB, scales to infinite, 0 admin. CloudFront gives global edge + free HTTPS via *.cloudfront.net — no Route53 cost ($0.50/month/hosted zone avoided).

Lambda vs EC2 Runner:
Pay per 100ms execution. GitHub webhook -> Lambda runs only on push. No always-on builder.

DynamoDB vs RDS:
No connection pooling, pay-per-request, perfect for append-only deployment logs. RDS would need VPC + cost.

Educate Adjustment:
Removed CodeBuild (IAM boundary issues in sandbox) + Route53 (cost). Lambda downloads zip via GitHub API, extracts in /tmp, syncs to S3. Same outcome, fewer permissions.

AWS Services Are Going To Be Used

S3: asset storage + dashboard hosting
CloudFront: CDN + HTTPS
Lambda: webhook + deploy engine + notifier
API Gateway: webhook endpoint
DynamoDB: deployment history
SNS: alerts
SAM/CloudFormation: IaC
CloudWatch: logs

Deploy Yourself

sam build
sam deploy --guided

# Set webhook URL in GitHub repo settings

Cost (Educate Free Tier)
S3: first 5GB free, Lambda: 1M free requests, CloudFront: 1TB free, DynamoDB: 25GB free = $0 for demo.

Roadmap
Future: Route53 custom domains
Future: Build step for React/Next static export
Future: Rollback via S3 versioning
Demo
YouTube: (link after Oct 23)
