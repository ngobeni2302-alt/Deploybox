
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

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
    params = event.get("queryStringParameters") or {}
    repo = params.get("repo", "")

    if not isinstance(repo, str) or len(repo) > 200:
        return respond(400, {"error": "Invalid repository"})

    try:
        options = {"Limit": 100}

        if repo:
            options["FilterExpression"] = Attr("repo").eq(repo)

        result = table.scan(**options)

        items = result.get("Items", [])

        items.sort(
            key=lambda item: item.get("timestamp", ""),
            reverse=True,
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
        )

        deployments = [
            {
                key: item[key]
                for key in fields
                if key in item
            }
            for item in items
        ]

        return respond(
            200,
            {"deployments": deployments},
        )

    except Exception:
        return respond(
            500,
            {"error": "Unable to load deployments"},
        )
