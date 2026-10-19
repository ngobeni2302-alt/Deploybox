
import json
import os
import uuid
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ['TABLE_NAME']
DEPLOY_ENGINE_FUNCTION = os.environ['DEPLOY_ENGINE_FUNCTION']

table = boto3.resource('dynamodb').Table(TABLE_NAME)
lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    try:
        body = event.get('body') or {}

        if isinstance(body, str):
            body = json.loads(body)

        if not isinstance(body, dict):
            raise ValueError('JSON object required')

        repository = body.get('repository') or {}
        repo = repository.get('full_name', 'manual-test')

        if (
            not isinstance(repo, str)
            or not repo
            or '/' not in repo
            or any(
                part in ('', '.', '..')
                for part in repo.split('/')
            )
        ):
            raise ValueError(
                'repository.full_name must be owner/repo'
            )

    except (
        ValueError,
        TypeError,
        AttributeError,
        json.JSONDecodeError
    ) as exc:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(exc)})
        }

    deployment_id = uuid.uuid4().hex[:8]

    table.put_item(
        Item={
            'deploymentId': deployment_id,
            'repo': repo,
            'status': 'RECEIVED',
            'timestamp': datetime.now(
                timezone.utc
            ).isoformat()
        }
    )

    try:
        response = lambda_client.invoke(
            FunctionName=DEPLOY_ENGINE_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps({
                'repo': repo,
                'deploymentId': deployment_id
            }).encode('utf-8')
        )

        if response.get('StatusCode') != 202:
            raise RuntimeError(
                f'Unexpected invoke status: '
                f'{response.get("StatusCode")}'
            )

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

    return {
        'statusCode': 202,
        'body': json.dumps({
            'message': 'Webhook received',
            'deploymentId': deployment_id,
            'status': 'RECEIVED'
        })
    }