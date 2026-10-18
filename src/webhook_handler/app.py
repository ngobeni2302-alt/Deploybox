import json, os, boto3, uuid

dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')


TABLE = os.environ.get('TABLE_NAME')
DEPLOY_ENGINE_FUNCTION = os.environ.get('DEPLOY_ENGINE_FUNCTION')

def lambda_handler(event, context):
    print(f"Webhook event: {event}")


    body = event.get('body')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {}
    repo = "manual-test"
    if body and 'repository' in body:
        repo = body['repository'].get('full_name', 'manual-test')



    deployment_id = uuid.uuid4()[:8]
    
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item={
        'deploymentId': deployment_id,
        'repo': repo,
        'status': 'RECEIVED',
        'timestamp': context.aws_request_id if hasattr(context, 'aws_request_id') else deployment_id
    })

    if DEPLOY_ENGINE_FUNCTION:
        try:
            lambda_client.invoke(
                FunctionName=DEPLOY_ENGINE_FUNCTION,
                InvocationType='Event',
                Payload=json.dumps({'repo': repo, 'deploymentId': deployment_id})
            )
            print(f"Invoked {DEPLOY_ENGINE_FUNCTION} for {deployment_id}")
        except Exception as e:
            print(f"Failed to invoke deploy engine: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Webhook received', 'deploymentId': deployment_id, 'status': 'RECEIVED'})
    }