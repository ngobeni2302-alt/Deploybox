
import io
import mimetypes
import os
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET = os.environ["DEPLOY_BUCKET"]
TABLE = os.environ["TABLE_NAME"]
REGION = os.environ.get("AWS_REGION", "us-east-1")

MAX_ZIP_BYTES = 15 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_FILES = 250


def update(deployment_id, status, **extra):
    names = {"#status": "status"}
    values = {":status": status}
    assignments = ["#status = :status"]

    for idx, (key, value) in enumerate(extra.items()):
        name = f"#f{idx}"
        token = f":v{idx}"

        names[name] = key
        values[token] = value
        assignments.append(f"{name} = {token}")

    dynamodb.Table(TABLE).update_item(
        Key={"deploymentId": deployment_id},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression="attribute_exists(deploymentId)",
    )


def download_zip(repo, ref):
    # Download an archive from a public GitHub repository.
    url = f"https://api.github.com/repos/{repo}/zipball"

    if ref != "HEAD":
        url += "/" + quote(ref, safe="")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeployBox/0.6"},
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(MAX_ZIP_BYTES + 1)

    if len(data) > MAX_ZIP_BYTES:
        raise ValueError("Repository archive exceeds 15 MB")

    return zipfile.ZipFile(io.BytesIO(data))


def extract_static_files(archive):
    candidates = []
    total = 0

    for item in archive.infolist():
        if item.is_dir():
            continue

        # GitHub archives contain one top-level directory.
        parts = item.filename.split("/")

        if len(parts) < 2:
            continue

        relative = "/".join(parts[1:])

        if not relative or any(
            part in ("", ".", "..")
            for part in relative.split("/")
        ):
            raise ValueError("Unsafe archive path")

        if relative.startswith(".") or any(
            part.startswith(".")
            for part in relative.split("/")
        ):
            continue

        # Exclude common development-only directories.
        if relative.split("/")[0] in (
            "node_modules",
            "src",
            "tests",
            "test",
            "infra",
            "docs",
        ):
            continue

        # Exclude common non-static project files.
        if relative.endswith(
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

        # Reject symbolic links.
        if (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Symbolic links are not supported")

        total += item.file_size
        candidates.append((relative, item))

        if total > MAX_TOTAL_BYTES or len(candidates) > MAX_FILES:
            raise ValueError("Repository exceeds deployment limits")

    if not any(path == "index.html" for path, _ in candidates):
        raise ValueError(
            "Public repository must contain index.html in its root"
        )

    return candidates


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

                content_type = (
                    mimetypes.guess_type(relative)[0]
                    or "application/octet-stream"
                )

                for prefix in (deployment_id, "latest"):
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=f"{repo}/{prefix}/{relative}",
                        Body=data,
                        ContentType=content_type,
                    )

                uploaded.append(
                    f"{repo}/{deployment_id}/{relative}"
                )

        url = (
            f"http://{BUCKET}.s3-website-{REGION}"
            f".amazonaws.com/{repo}/latest/index.html"
        )

        update(
            deployment_id,
            "DEPLOYED",
            s3_keys=uploaded,
            website_url=url,
            completedAt=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "status": "DEPLOYED",
            "website_url": url,
            "files": len(uploaded),
        }

    except Exception as exc:
        update(
            deployment_id,
            "FAILED",
            error_msg=str(exc)[:500],
        )
        raise
