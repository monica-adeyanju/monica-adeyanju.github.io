"""
Custom Resource Lambda: Deploy Frontend to S3

This function runs during CloudFormation stack create/update and:
1. Reads the frontend files (index.html, chat.js) bundled in this package
2. Replaces the API_ENDPOINT placeholder in chat.js with the real endpoint
3. Uploads everything to the Chat UI S3 bucket

On stack delete, it empties the bucket so CloudFormation can remove it cleanly.
"""

import json
import os
import urllib.request
import boto3

s3 = boto3.client("s3")

# Frontend files are packaged alongside this Lambda (in the same zip)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".json": "application/json",
}


def handler(event, context):
    """CloudFormation Custom Resource handler."""
    try:
        request_type = event["RequestType"]
        bucket_name = event["ResourceProperties"]["BucketName"]
        api_endpoint = event["ResourceProperties"].get("ApiEndpoint", "")

        if request_type in ("Create", "Update"):
            upload_frontend(bucket_name, api_endpoint)
        elif request_type == "Delete":
            empty_bucket(bucket_name)

        send_response(event, context, "SUCCESS", {"Message": f"{request_type} completed"})
    except Exception as e:
        print(f"Error: {str(e)}")
        send_response(event, context, "FAILED", {"Message": str(e)})


def upload_frontend(bucket_name, api_endpoint):
    """Upload frontend files to S3, injecting the real API endpoint."""
    for root, _dirs, files in os.walk(FRONTEND_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            s3_key = os.path.relpath(filepath, FRONTEND_DIR)

            # Read file content
            with open(filepath, "r" if is_text_file(filename) else "rb") as f:
                content = f.read()

            # Inject the real API endpoint into chat.js
            if filename == "chat.js" and isinstance(content, str):
                content = content.replace(
                    "https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/prod",
                    api_endpoint,
                )

            # Determine content type
            ext = os.path.splitext(filename)[1].lower()
            content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

            # Upload to S3
            body = content.encode("utf-8") if isinstance(content, str) else content
            s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=body,
                ContentType=content_type,
            )
            print(f"Uploaded: {s3_key} ({content_type})")


def empty_bucket(bucket_name):
    """Remove all objects from the bucket so CloudFormation can delete it."""
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            objects = page.get("Contents", [])
            if objects:
                s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                )
                print(f"Deleted {len(objects)} objects from {bucket_name}")
    except Exception as e:
        print(f"Error emptying bucket: {str(e)}")


def is_text_file(filename):
    """Check if a file should be read as text."""
    text_extensions = {".html", ".js", ".css", ".json", ".svg", ".txt", ".md"}
    ext = os.path.splitext(filename)[1].lower()
    return ext in text_extensions


def send_response(event, context, status, data):
    """Send response back to CloudFormation."""
    response_body = json.dumps({
        "Status": status,
        "Reason": data.get("Message", "See CloudWatch logs"),
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data,
    })

    req = urllib.request.Request(
        event["ResponseURL"],
        data=response_body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(req)
