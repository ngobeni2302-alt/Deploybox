
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

TABLE = os.environ["TABLE_NAME"]
ENGINE = os.environ["DEPLOY_ENGINE_FUNCTION"]

REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def response(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    try:
        body = event.get("body") or "{}"
        data = json.loads(body) if isinstance(body, str) else body

        if not isinstance(data, dict):
            raise ValueError("Body must be an object")

        repo_data = data.get("repository") or {}
        repo = (
            repo_data.get("full_name")
            if isinstance(repo_data, dict)
            else None
        )

        ref = data.get("ref") or "HEAD"

        if not isinstance(repo, str) or not REPO_PATTERN.fullmatch(repo):
            raise ValueError(
                "repository.full_name must be owner/repo"
            )

        if (
            not isinstance(ref, str)
            or len(ref) > 200
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", ref)
            or ".." in ref
        ):
            raise ValueError("Invalid ref")

    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return response(400, {"error": str(exc)})

    deployment_id = uuid.uuid4().hex[:12]

    table = dynamodb.Table(TABLE)

    table.put_item(
        Item={
            "deploymentId": deployment_id,
            "repo": repo,
            "ref": ref,
            "status": "RECEIVED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        result = lambda_client.invoke(
            FunctionName=ENGINE,
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "repo": repo,
                    "ref": ref,
                    "deploymentId": deployment_id,
                }
            ).encode(),
        )

        if result.get("StatusCode") != 202:
            raise RuntimeError(
                "Asynchronous Lambda invocation not accepted"
            )

    except Exception as exc:
        table.update_item(
            Key={"deploymentId": deployment_id},
            UpdateExpression="SET #s = :s, error_msg = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "FAILED",
                ":e": str(exc)[:500],
            },
        )

        return response(
            502,
            {
                "error": "Deployment could not be started",
                "deploymentId": deployment_id,
            },
        )

    return response(
        202,
        {
            "message": "Deployment queued",
            "deploymentId": deployment_id,
            "status": "RECEIVED",
        },
    )
