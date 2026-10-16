import json, os, boto3, uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
TABLE = os.environ.get('LOG_TABLE')

def lambda_handler(event, context):
    body = event.get('body', '{}')
    deployment_id = str(uuid.uuid4())[:8]
    
    table = dynamodb.Table(TABLE)
    table.put_item(Item={
        'deploymentId': deployment_id,
        'status': 'RECEIVED',
        'timestamp': datetime.utcnow().isoformat(),
        'repo': 'manual-test'
    })

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Webhook received', 'deploymentId': deployment_id})
    }