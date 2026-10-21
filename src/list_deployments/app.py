
import base64
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

TABLE = boto3.resource("dynamodb").Table(
    os.environ["TABLE_NAME"]
)

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

FIELDS = (
    "deploymentId",
    "repo",
    "ref",
    "status",
    "timestamp",
    "completedAt",
    "website_url",
    "error_msg",
)


def respond(status, body):
    return {
        "statusCode": status,
        "headers": HEADERS,
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    repo = params.get("repo", "")

    try:
        limit = int(params.get("limit", "50"))

        if not 1 <= limit <= 100:
            raise ValueError()

        if (
            not isinstance(repo, str)
            or len(repo) > 200
        ):
            raise ValueError()

        options = {
            "Limit": limit
        }

        if repo:
            options["FilterExpression"] = (
                Attr("repo").eq(repo)
            )

        if params.get("cursor"):
            token = params["cursor"]

            if len(token) > 2048:
                raise ValueError()

            options["ExclusiveStartKey"] = (
                json.loads(
                    base64.urlsafe_b64decode(
                        token + "=" * (-len(token) % 4)
                    ).decode()
                )
            )

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):
        return respond(
            400,
            {
                "error": "Invalid repo, limit or cursor"
            },
        )

    try:
        result = TABLE.scan(**options)

        items = sorted(
            result.get("Items", []),
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )

        cursor = None

        if result.get("LastEvaluatedKey"):
            cursor = base64.urlsafe_b64encode(
                json.dumps(
                    result["LastEvaluatedKey"]
                ).encode()
            ).decode().rstrip("=")

        deployments = [
            {
                key: item[key]
                for key in FIELDS
                if key in item
            }
            for item in items
        ]

        return respond(
            200,
            {
                "deployments": deployments,
                "nextCursor": cursor,
            },
        )

    except Exception:
        return respond(
            500,
            {
                "error": "Unable to load deployments"
            },
        )
