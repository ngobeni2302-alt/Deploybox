
import io
import json
import mimetypes
import os
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

import boto3

S3 = boto3.client("s3")
DYNAMODB = boto3.resource("dynamodb")
LAMBDA = boto3.client("lambda")

BUCKET = os.environ["DEPLOY_BUCKET"]
TABLE = os.environ["TABLE_NAME"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
NOTIFIER = os.environ.get("NOTIFIER_FUNCTION", "")

MAX_ZIP_BYTES = 15 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_FILES = 250


def update(deployment_id, status, **extra):
    fields = {
        "status": status,
        **extra,
    }

    names = {
        f"#k{i}": key
        for i, key in enumerate(fields)
    }

    values = {
        f":v{i}": value
        for i, value in enumerate(fields.values())
    }

    expression = ", ".join(
        f"#k{i} = :v{i}"
        for i in range(len(fields))
    )

    DYNAMODB.Table(TABLE).update_item(
        Key={
            "deploymentId": deployment_id
        },
        UpdateExpression="SET " + expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression=(
            "attribute_exists(deploymentId)"
        ),
    )


def download_zip(repo, ref):
    url = (
        f"https://api.github.com/repos/{repo}/zipball"
    )

    if ref != "HEAD":
        url += "/" + quote(ref, safe="")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DeployBox/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        data = response.read(MAX_ZIP_BYTES + 1)

    if len(data) > MAX_ZIP_BYTES:
        raise ValueError(
            "Repository archive exceeds 15 MB"
        )

    return zipfile.ZipFile(io.BytesIO(data))


def extract_static_files(archive):
    candidates = []
    total = 0

    for item in archive.infolist():
        if item.is_dir():
            continue

        parts = item.filename.split("/")

        if len(parts) < 2:
            continue

        relative = "/".join(parts[1:])
        segments = relative.split("/")

        if any(
            segment in ("", ".", "..")
            or "\\" in segment
            for segment in segments
        ):
            raise ValueError("Unsafe archive path")

        if any(
            segment.startswith(".")
            for segment in segments
        ):
            continue

        if segments[0] in {
            "node_modules",
            "src",
            "tests",
            "test",
            "infra",
            "docs",
        }:
            continue

        if relative.lower().endswith(
            (
                ".py",
                ".env",
                ".yaml",
                ".yml",
                ".toml",
                ".md",
                ".json",
                ".lock",
                ".sh",
            )
        ):
            continue

        file_type = (
            item.external_attr >> 16
        ) & 0o170000

        if file_type == 0o120000:
            raise ValueError(
                "Symbolic links are not supported"
            )

        total += item.file_size
        candidates.append((relative, item))

        if (
            total > MAX_TOTAL_BYTES
            or len(candidates) > MAX_FILES
        ):
            raise ValueError(
                "Repository exceeds deployment limits"
            )

    if not any(
        name == "index.html"
        for name, _ in candidates
    ):
        raise ValueError(
            "Public repository must contain "
            "index.html at its root"
        )

    return candidates


def notify(
    deployment_id,
    repo,
    status,
    website_url=None,
    error=None,
):
    if not NOTIFIER:
        return

    try:
        LAMBDA.invoke(
            FunctionName=NOTIFIER,
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "deploymentId": deployment_id,
                    "repo": repo,
                    "status": status,
                    "website_url": website_url,
                    "error": error,
                }
            ).encode(),
        )

    except Exception as exc:
        print(
            "Notification could not be queued:",
            str(exc),
        )


def lambda_handler(event, context):
    repo = event["repo"]
    deployment_id = event["deploymentId"]
    ref = event.get("ref", "HEAD")

    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        repo,
    ):
        raise ValueError("Invalid repository")

    try:
        update(deployment_id, "BUILDING")

        with download_zip(repo, ref) as archive:
            files = extract_static_files(archive)
            uploaded = []

            for relative, info in files:
                data = archive.read(info)

                if len(data) != info.file_size:
                    raise ValueError(
                        "Invalid archive file size"
                    )

                content_type = (
                    mimetypes.guess_type(relative)[0]
                    or "application/octet-stream"
                )

                for prefix in (
                    deployment_id,
                    "latest",
                ):
                    S3.put_object(
                        Bucket=BUCKET,
                        Key=(
                            f"{repo}/{prefix}/{relative}"
                        ),
                        Body=data,
                        ContentType=content_type,
                    )

                uploaded.append(
                    f"{repo}/{deployment_id}/{relative}"
                )

        url = (
            f"http://{BUCKET}"
            f".s3-website-{REGION}.amazonaws.com/"
            f"{repo}/latest/index.html"
        )

        update(
            deployment_id,
            "DEPLOYED",
            s3_keys=uploaded,
            website_url=url,
            completedAt=datetime.now(
                timezone.utc
            ).isoformat(),
        )

        notify(
            deployment_id,
            repo,
            "DEPLOYED",
            website_url=url,
        )

        return {
            "status": "DEPLOYED",
            "website_url": url,
            "files": len(uploaded),
        }

    except Exception as exc:
        message = str(exc)[:500]

        update(
            deployment_id,
            "FAILED",
            error_msg=message,
            completedAt=datetime.now(
                timezone.utc
            ).isoformat(),
        )

        notify(
            deployment_id,
            repo,
            "FAILED",
            error=message,
        )

        raise
