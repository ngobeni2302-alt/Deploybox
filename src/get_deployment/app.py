
import json
import os

import boto3

table = boto3.resource("dynamodb").Table(
    os.environ["TABLE_NAME"]
)

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def respond(status, data):
    return {
        "statusCode": status,
        "headers": HEADERS,
        "body": json.dumps(data),
    }


def lambda_handler(event, context):
    params = event.get("pathParameters") or {}
    deployment_id = params.get("deploymentId", "")

    if (
        not deployment_id
        or len(deployment_id) > 100
    ):
        return respond(
            400,
            {"error": "Invalid deployment ID"},
        )

    try:
        result = table.get_item(
            Key={
                "deploymentId": deployment_id
            }
        )

    except Exception:
        return respond(
            500,
            {
                "error": "Could not retrieve deployment"
            },
        )

    item = result.get("Item")

    if not item:
        return respond(
            404,
            {
                "error": "Deployment not found"
            },
        )

    fields = (
        "deploymentId",
        "repo",
        "ref",
        "status",
        "timestamp",
        "completedAt",
        "website_url",
        "error_msg",
        "s3_keys",
    )

    deployment = {
        key: item[key]
        for key in fields
        if key in item
    }

    return respond(
        200,
        {
            "deployment": deployment
        },
    )
