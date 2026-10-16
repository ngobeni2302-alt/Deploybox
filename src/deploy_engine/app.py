import os, boto3
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET = os.environ['DEPLOY_BUCKET']
TABLE = os.environ['LOG_TABLE']

def lambda_handler(event, context):
    deployment_id = event.get('deploymentId', 'manual')
    table = dynamodb.Table(TABLE)

    # 20% MVP: just deploy a hello page to S3
    s3.put_object(
        Bucket=BUCKET,
        Key='index.html',
        Body=f"<h1>DeployBox Live</h1><p>ID: {deployment_id}</p><p>{datetime.utcnow()}</p>",
        ContentType='text/html'
    )

    table.update_item(
        Key={'deploymentId': deployment_id},
        UpdateExpression='SET #s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': 'DEPLOYED'}
    )
    return {'statusCode': 200, 'deploymentId': deployment_id}