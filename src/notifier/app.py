
import json
import os

import boto3

SNS = boto3.client("sns")
TOPIC = os.environ["SNS_TOPIC"]


def lambda_handler(event, context):
    status = event.get(
        "status",
        "UNKNOWN",
    )

    deployment_id = event.get(
        "deploymentId",
        "unknown",
    )

    repo = event.get(
        "repo",
        "unknown",
    )

    message = {
        "deploymentId": deployment_id,
        "repository": repo,
        "status": status,
        "website_url": event.get("website_url"),
        "error": event.get("error"),
    }

    SNS.publish(
        TopicArn=TOPIC,
        Subject=f"DeployBox: {status}"[:100],
        Message=json.dumps(
            message,
            indent=2,
        ),
    )

    return {
        "published": True
    }
