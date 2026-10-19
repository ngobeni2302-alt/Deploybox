
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

TABLE = boto3.resource("dynamodb").Table(
    os.environ["TABLE_NAME"]
)


def lambda_handler(event, context):
    # Demo-only endpoint.
    # Returns up to 100 deployment records.
    params = event.get("queryStringParameters") or {}
    repo = params.get("repo", "")

    if len(repo) > 200:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid repo"}),
        }

    kwargs = {"Limit": 100}

    if repo:
        kwargs["FilterExpression"] = Attr("repo").eq(repo)

    result = TABLE.scan(**kwargs)

    items = sorted(
        result.get("Items", []),
        key=lambda item: item.get("timestamp", ""),
        reverse=True,
    )

    # Only expose fields needed by the dashboard.
    allowed = (
        "deploymentId",
        "repo",
        "ref",
        "status",
        "timestamp",
        "website_url",
    )

    items = [
        {
            key: item[key]
            for key in allowed
            if key in item
        }
        for item in items
    ]

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"deployments": items}),
    }
