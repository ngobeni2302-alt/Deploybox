
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote

import boto3

BUCKET = os.environ['DEPLOY_BUCKET']
TABLE_NAME = os.environ['TABLE_NAME']
REGION = os.environ.get('AWS_REGION', 'us-east-1')

s3 = boto3.client('s3')
table = boto3.resource('dynamodb').Table(TABLE_NAME)


def lambda_handler(event, context):
    repo = event['repo']
    deployment_id = event['deploymentId']

    prefix = f'{repo}/{deployment_id}'
    latest_prefix = f'{repo}/latest'

    source_dir = (
        Path(__file__).resolve().parent / 'template-site'
    )

    uploaded = []

    try:
        # Find static website files
        paths = (
            sorted(
                p for p in source_dir.rglob('*')
                if p.is_file()
            )
            if source_dir.is_dir()
            else []
        )

        # Fallback HTML when no template files exist
        if not paths:
            html = (
                '<!doctype html>'
                '<html>'
                '<head>'
                '<meta charset="utf-8">'
                '<title>DeployBox</title>'
                '</head>'
                '<body>'
                '<h1>DeployBox Live</h1>'
                f'<p>Repo: {repo}</p>'
                f'<p>Deployment: {deployment_id}</p>'
                '</body>'
                '</html>'
            ).encode('utf-8')

            objects = [
                ('index.html', html)
            ]

        else:
            objects = [
                (
                    p.relative_to(
                        source_dir
                    ).as_posix(),
                    p.read_bytes()
                )
                for p in paths
            ]

        # Upload each file to versioned and latest paths
        for relative_path, contents in objects:
            content_type = (
                mimetypes.guess_type(relative_path)[0]
                or 'application/octet-stream'
            )

            keys = [
                f'{prefix}/{relative_path}',
                f'{latest_prefix}/{relative_path}'
            ]

            for key in keys:
                s3.put_object(
                    Bucket=BUCKET,
                    Key=key,
                    Body=contents,
                    ContentType=content_type
                )

                uploaded.append(key)

        # Generate S3 website URL
        website_url = (
            f'http://{BUCKET}.'
            f's3-website-{REGION}.amazonaws.com/'
            f'{quote(latest_prefix, safe="/")}/index.html'
        )

        # Update DynamoDB to DEPLOYED
        table.update_item(
            Key={
                'deploymentId': deployment_id
            },
            UpdateExpression=(
                'SET #s = :s, '
                's3_keys = :keys, '
                'website_url = :url'
            ),
            ExpressionAttributeNames={
                '#s': 'status'
            },
            ExpressionAttributeValues={
                ':s': 'DEPLOYED',
                ':keys': uploaded,
                ':url': website_url
            }
        )

        return {
            'status': 'DEPLOYED',
            'objects': uploaded,
            'website_url': website_url
        }

    except Exception as exc:
        table.update_item(
            Key={
                'deploymentId': deployment_id
            },
            UpdateExpression=(
                'SET #s = :s, error_msg = :e'
            ),
            ExpressionAttributeNames={
                '#s': 'status'
            },
            ExpressionAttributeValues={
                ':s': 'FAILED',
                ':e': str(exc)
            }
        )

        raise
