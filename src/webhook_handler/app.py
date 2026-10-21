
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

DYNAMODB = boto3.resource("dynamodb")
LAMBDA = boto3.client("lambda")

TABLE_NAME = os.environ["TABLE_NAME"]
ENGINE = os.environ["DEPLOY_ENGINE_FUNCTION"]

REPOSITORY = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z"
)
REF = re.compile(r"[A-Za-z0-9_./-]+\Z")


def response(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        },
        "body": json.dumps(payload),
    }


def lambda_handler(event, context):
    method = (event.get("httpMethod") or "POST").upper()

    if method == "OPTIONS":
        return response(
            200,
            {"message": "CORS preflight accepted"},
        )

    if method != "POST":
        return response(
            405,
            {"error": "Method not allowed"},
        )

    try:
        raw = event.get("body") or "{}"

        if isinstance(raw, str) and len(raw) > 8192:
            raise ValueError("Request body too large")

        data = (
            json.loads(raw)
            if isinstance(raw, str)
            else raw
        )

        if not isinstance(data, dict):
            raise ValueError("Body must be an object")

        repository = data.get("repository")

        repo = (
            repository.get("full_name")
            if isinstance(repository, dict)
            else None
        )

        ref = data.get("ref") or "HEAD"

        if (
            not isinstance(repo, str)
            or not REPOSITORY.fullmatch(repo)
        ):
            raise ValueError(
                "repository.full_name must be owner/repo"
            )

        if (
            not isinstance(ref, str)
            or len(ref) > 200
            or not REF.fullmatch(ref)
            or ".." in ref
            or ref.startswith("/")
        ):
            raise ValueError("Invalid ref")

    except (ValueError, TypeError) as exc:
        return response(
            400,
            {"error": str(exc)},
        )

    deployment_id = uuid.uuid4().hex[:12]
    table = DYNAMODB.Table(TABLE_NAME)

    try:
        table.put_item(
            Item={
                "deploymentId": deployment_id,
                "repo": repo,
                "ref": ref,
                "status": "RECEIVED",
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

    except Exception:
        return response(
            500,
            {"error": "Could not save deployment"},
        )

    try:
        result = LAMBDA.invoke(
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
                "Deployment engine did not accept request"
            )

    except Exception:
        table.update_item(
            Key={
                "deploymentId": deployment_id
            },
            UpdateExpression=(
                "SET #s = :s, error_msg = :e"
            ),
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":s": "FAILED",
                ":e": "Could not queue deployment",
            },
        )

        return response(
            502,
            {
                "error": "Could not queue deployment",
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
