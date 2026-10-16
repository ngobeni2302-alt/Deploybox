import os, boto3
sns = boto3.client('sns')
TOPIC = os.environ['SNS_TOPIC']

def lambda_handler(event, context):
    sns.publish(TopicArn=TOPIC, Subject='DeployBox Deployed', Message=f"Deployed {event.get('deploymentId')}")
    return {'published': True}