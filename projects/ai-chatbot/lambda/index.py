"""
AI Chatbot Lambda Handler
Powered by Amazon Bedrock (Claude) with DynamoDB conversation history.

Endpoints:
  POST /chat    - Send a message and get an AI response
  GET  /history - Retrieve conversation history by sessionId
"""

import json
import os
import time
import uuid
import boto3
from botocore.exceptions import ClientError

# ─── Configuration ───────────────────────────────────────────────────────────
TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["MODEL_ID"]
TTL_DAYS = int(os.environ.get("TTL_DAYS", 7))

SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Be concise, accurate, and friendly. "
    "If you don't know something, say so honestly."
)
MAX_HISTORY_MESSAGES = 20  # Keep last N messages for context window

# ─── AWS Clients ─────────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    """Main Lambda entry point - routes to chat or history handler."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    try:
        if path == "/chat" and http_method == "POST":
            return handle_chat(event)
        elif path == "/history" and http_method == "GET":
            return handle_history(event)
        else:
            return response(404, {"error": "Not found"})
    except Exception as e:
        print(f"Unhandled error: {str(e)}")
        return response(500, {"error": "Internal server error"})


def handle_chat(event):
    """Process a chat message and return an AI response."""
    # Parse request body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON in request body"})

    message = body.get("message", "").strip()
    if not message:
        return response(400, {"error": "Message is required"})

    if len(message) > 4000:
        return response(400, {"error": "Message too long (max 4000 characters)"})

    # Get or create session
    session_id = body.get("sessionId") or str(uuid.uuid4())

    # Load conversation history from DynamoDB
    history = get_conversation_history(session_id)

    # Build messages array for Bedrock
    messages = []
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})

    # Add the new user message
    messages.append({"role": "user", "content": message})

    # Call Bedrock
    ai_response = invoke_bedrock(messages)

    if ai_response is None:
        return response(503, {"error": "AI model unavailable, try again later"})

    # Store both messages in DynamoDB
    now = int(time.time())
    ttl = now + (TTL_DAYS * 86400)

    # Store user message
    store_message(session_id, now, "user", message, ttl)

    # Store assistant response (timestamp + 1ms to maintain order)
    store_message(session_id, now + 1, "assistant", ai_response, ttl)

    return response(200, {
        "response": ai_response,
        "sessionId": session_id,
    })


def handle_history(event):
    """Retrieve conversation history for a session."""
    params = event.get("queryStringParameters") or {}
    session_id = params.get("sessionId", "").strip()

    if not session_id:
        return response(400, {"error": "sessionId query parameter is required"})

    history = get_conversation_history(session_id, limit=50)

    return response(200, {
        "sessionId": session_id,
        "messages": history,
        "count": len(history),
    })


# ─── Bedrock Integration ─────────────────────────────────────────────────────

def invoke_bedrock(messages):
    """Call Amazon Bedrock with conversation messages."""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages[-MAX_HISTORY_MESSAGES:],  # Trim to fit context
        }

        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body),
        )

        result = json.loads(resp["body"].read())
        return result["content"][0]["text"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"Bedrock error: {error_code} - {str(e)}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Unexpected Bedrock response format: {str(e)}")
        return None


# ─── DynamoDB Operations ─────────────────────────────────────────────────────

def store_message(session_id, timestamp, role, content, ttl):
    """Store a single message in DynamoDB."""
    try:
        table.put_item(Item={
            "sessionId": session_id,
            "timestamp": timestamp,
            "role": role,
            "content": content,
            "ttl": ttl,
        })
    except ClientError as e:
        print(f"DynamoDB write error: {str(e)}")


def get_conversation_history(session_id, limit=MAX_HISTORY_MESSAGES):
    """Retrieve conversation history for a session, ordered by timestamp."""
    try:
        result = table.query(
            KeyConditionExpression="sessionId = :sid",
            ExpressionAttributeValues={":sid": session_id},
            ScanIndexForward=True,  # oldest first
            Limit=limit,
        )
        return [
            {"role": item["role"], "content": item["content"], "timestamp": int(item["timestamp"])}
            for item in result.get("Items", [])
        ]
    except ClientError as e:
        print(f"DynamoDB read error: {str(e)}")
        return []


# ─── Response Helper ─────────────────────────────────────────────────────────

def response(status_code, body):
    """Build an API Gateway proxy response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,GET,OPTIONS",
        },
        "body": json.dumps(body),
    }
