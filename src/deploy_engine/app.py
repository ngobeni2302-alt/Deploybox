import os
import boto3
import zipfile
import io
import mimetypes
import urllib.request

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET = os.environ['DEPLOY_BUCKET']
TABLE = os.environ['LOG_TABLE']

def lambda_handler(event, context):
    print(f"DeployEngine event: {event}")

    repo = event.get('repo', 'manual-test')
    deployment_id = event.get('deploymentId', 'test-id')

    source_dir = "/var/task/template-site" if os.path.exists("/var/task/template-site") else "template-site"
    if not os.path.exists(source_dir):
        source_dir = "template-site"
    # If deployed via SAM, template-site is packaged with lambda
    # For now create a simple index if not found
    files_uploaded = []
    table = dynamodb.Table(TABLE_NAME)
    try:
        # Walk and upload every file as S3 Object
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                local_path = os.path.join(root, file)
                # Keep path relative to template-site
                rel_path = os.path.relpath(local_path, source_dir)
                s3_key = f"{repo}/{deployment_id}/{rel_path}"
                s3_key_latest = f"{repo}/latest/{rel_path}"
                content_type, _ = mimetypes.guess_type(local_path)
                if content_type is None:
                    content_type = "binary/octet-stream"
                with open(local_path, 'rb') as f:
                    s3.put_object(
                        Bucket=DEPLOY_BUCKET,
                        Key=s3_key,
                        Body=f,
                        ContentType=content_type
                    )
                    # Also deploy to /latest for live URL
                    f.seek(0)
                    s3.put_object(
                        Bucket=DEPLOY_BUCKET,
                        Key=s3_key_latest,
                        Body=f,
                        ContentType=content_type
                    )
                files_uploaded.append(s3_key)
        # If no files found (running in Lambda without template-site), create index.html
        if not files_uploaded:
            html = f"<h1>DeployBox Live</h1><p>Repo: {repo}</p><p>Deployment: {deployment_id}</p><p>Objects: Object Storage Working</p>"
            s3.put_object(
                Bucket=DEPLOY_BUCKET,
                Key=f"{repo}/{deployment_id}/index.html",
                Body=html.encode(),
                ContentType="text/html"
            )
            s3.put_object(
                Bucket=DEPLOY_BUCKET,
                Key=f"{repo}/latest/index.html",
                Body=html.encode(),
                ContentType="text/html"
            )
            files_uploaded.append(f"{repo}/{deployment_id}/index.html")
        # Update DynamoDB to DEPLOYED
        table.update_item(
            Key={'deploymentId': deployment_id},
            UpdateExpression="SET #s = :s, s3_keys = :k, website_url = :u",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':s': 'DEPLOYED',
                ':k': files_uploaded,
                ':u': f"https://{DEPLOY_BUCKET}.s3-website-us-east-1.amazonaws.com/{repo}/latest/index.html"
            }
        )
        print(f"Deployed {len(files_uploaded)} objects to S3: {DEPLOY_BUCKET}")
        return {"status": "DEPLOYED", "objects": files_uploaded, "bucket": DEPLOY_BUCKET}
    except Exception as e:
        print(f"Deploy failed: {e}")
        table.update_item(
            Key={'deploymentId': deployment_id},
            UpdateExpression="SET #s = :s, error_msg = :e",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'FAILED', ':e': str(e)}
        )
        raise