"""
Production-Grade AI Chatbot Lambda Handler

Features:
  - Multi-model fallback (primary → fallback on throttle/error)
  - Bedrock Guardrails (content safety + PII filtering)
  - RAG (document-grounded answers via S3 context)
  - Token usage tracking with budget enforcement
  - X-Ray tracing for full observability
  - Custom CloudWatch metrics
  - Cognito-authenticated users

Endpoints:
  POST /chat    - Send message, get AI response (with guardrails + RAG)
  GET  /history - Retrieve conversation history
  POST /upload  - Get presigned URL for document upload (RAG)
  GET  /usage   - Get token usage stats for current user
"""

import json
import os
import time
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone

# ─── X-Ray Tracing ──────────────────────────────────────────────────────────
from aws_xray_sdk.core import xray_recorder, patch_all
patch_all()

# ─── Configuration ──────────────────────────────────────────────────────────
CONVERSATION_TABLE = os.environ["CONVERSATION_TABLE"]
USAGE_TABLE = os.environ["USAGE_TABLE"]
PRIMARY_MODEL = os.environ["PRIMARY_MODEL_ID"]
FALLBACK_MODEL = os.environ["FALLBACK_MODEL_ID"]
TTL_DAYS = int(os.environ.get("TTL_DAYS", 7))
MAX_TOKEN_BUDGET = int(os.environ.get("MAX_TOKEN_BUDGET", 50000))
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
DOCUMENT_BUCKET = os.environ["DOCUMENT_BUCKET"]

SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Be concise, accurate, and friendly. "
    "If provided with document context, use it to ground your answers. "
    "If you don't know something, say so honestly."
)
MAX_HISTORY = 20
APP_NAME = os.environ.get("APP_NAME", "ai-chatbot")

# ─── AWS Clients ────────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime")
bedrock_agent = boto3.client("bedrock-agent-runtime")
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

conv_table = dynamodb.Table(CONVERSATION_TABLE)
usage_table = dynamodb.Table(USAGE_TABLE)


# ─── Main Handler ───────────────────────────────────────────────────────────
def handler(event, context):
    """Route requests based on path and method."""
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    # Extract user ID from Cognito claims
    user_id = extract_user_id(event)

    try:
        if path == "/chat" and method == "POST":
            return handle_chat(event, user_id)
        elif path == "/history" and method == "GET":
            return handle_history(event, user_id)
        elif path == "/upload" and method == "POST":
            return handle_upload(event, user_id)
        elif path == "/usage" and method == "GET":
            return handle_usage(event, user_id)
        else:
            return resp(404, {"error": "Not found"})
    except Exception as e:
        print(f"Unhandled error: {e}")
        emit_metric("Errors", 1)
        return resp(500, {"error": "Internal server error"})


def extract_user_id(event):
    """Extract authenticated user ID from Cognito JWT claims."""
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        return claims.get("sub", claims.get("email", "anonymous"))
    except (KeyError, TypeError):
        return "anonymous"

# ═══════════════════════════════════════════════════════════════════════════
# CHAT HANDLER - with guardrails, RAG, fallback, and token tracking
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("handle_chat")
def handle_chat(event, user_id):
    """Process chat message with full production pipeline."""
    # Parse request
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON"})

    message = body.get("message", "").strip()
    if not message:
        return resp(400, {"error": "Message is required"})
    if len(message) > 4000:
        return resp(400, {"error": "Message too long (max 4000 chars)"})

    session_id = body.get("sessionId") or str(uuid.uuid4())
    use_rag = body.get("useRAG", False)

    # ── Step 1: Check token budget ──────────────────────────────────────
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = get_usage(user_id, today)
    if usage >= MAX_TOKEN_BUDGET:
        emit_metric("RateLimited", 1)
        return resp(429, {
            "error": "Daily token budget exceeded",
            "usage": usage,
            "limit": MAX_TOKEN_BUDGET,
        })

    # ── Step 2: Apply input guardrail ───────────────────────────────────
    guardrail_result = apply_guardrail(message, "INPUT")
    if guardrail_result.get("blocked"):
        emit_metric("GuardrailBlocked", 1)
        return resp(400, {
            "error": "Message blocked by safety policy",
            "reason": guardrail_result.get("reason", "Content policy violation"),
        })

    # ── Step 3: RAG - Retrieve relevant context from documents ──────────
    rag_context = ""
    if use_rag:
        rag_context = retrieve_document_context(message, user_id)

    # ── Step 4: Build conversation with history ─────────────────────────
    history = get_conversation_history(session_id)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    
    # Inject RAG context into user message if available
    user_content = message
    if rag_context:
        user_content = (
            f"Use the following document context to help answer:\n"
            f"---\n{rag_context}\n---\n\n"
            f"User question: {message}"
        )
    messages.append({"role": "user", "content": user_content})

    # ── Step 5: Call Bedrock with fallback ───────────────────────────────
    start_time = time.time()
    ai_response, model_used, token_usage = invoke_with_fallback(messages)
    latency = (time.time() - start_time) * 1000  # ms

    if ai_response is None:
        return resp(503, {"error": "AI models unavailable, try again later"})

    # ── Step 6: Apply output guardrail ──────────────────────────────────
    output_guard = apply_guardrail(ai_response, "OUTPUT")
    if output_guard.get("blocked"):
        emit_metric("GuardrailBlocked", 1)
        ai_response = "I can't provide that response due to our safety policy."

    # ── Step 7: Store messages ──────────────────────────────────────────
    now = int(time.time())
    ttl = now + (TTL_DAYS * 86400)
    store_message(session_id, now, "user", message, ttl, user_id)
    store_message(session_id, now + 1, "assistant", ai_response, ttl, user_id)

    # ── Step 8: Track token usage ───────────────────────────────────────
    update_usage(user_id, today, token_usage)

    # ── Step 9: Emit metrics ────────────────────────────────────────────
    emit_metric("MessagesProcessed", 1)
    emit_metric("TokensUsed", token_usage)
    emit_metric("ModelLatency", latency)
    if model_used == FALLBACK_MODEL:
        emit_metric("FallbackInvocations", 1)

    return resp(200, {
        "response": ai_response,
        "sessionId": session_id,
        "model": model_used,
        "tokensUsed": token_usage,
        "ragUsed": bool(rag_context),
    })

# ═══════════════════════════════════════════════════════════════════════════
# BEDROCK - Multi-model invocation with fallback
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("invoke_with_fallback")
def invoke_with_fallback(messages):
    """Try primary model, fall back to secondary on throttle/error."""
    # Try primary model
    result = invoke_bedrock(messages, PRIMARY_MODEL)
    if result is not None:
        return result[0], PRIMARY_MODEL, result[1]

    # Fallback
    print(f"Primary model failed, falling back to {FALLBACK_MODEL}")
    result = invoke_bedrock(messages, FALLBACK_MODEL)
    if result is not None:
        return result[0], FALLBACK_MODEL, result[1]

    return None, None, 0


def invoke_bedrock(messages, model_id):
    """Call Bedrock and return (response_text, token_count) or None."""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages[-MAX_HISTORY:],
        }

        resp_obj = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body),
        )

        result = json.loads(resp_obj["body"].read())
        text = result["content"][0]["text"]
        # Token counting from response metadata
        usage = result.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return (text, tokens)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"Bedrock error ({model_id}): {error_code} - {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Unexpected response format ({model_id}): {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# GUARDRAILS - Content safety filtering
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("apply_guardrail")
def apply_guardrail(content, source):
    """Apply Bedrock Guardrail to input or output content."""
    try:
        response = bedrock.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source=source,
            content=[{"text": {"text": content}}],
        )
        action = response.get("action", "NONE")
        if action == "GUARDRAIL_INTERVENED":
            outputs = response.get("outputs", [])
            reason = outputs[0]["text"] if outputs else "Blocked by guardrail"
            return {"blocked": True, "reason": reason}
        return {"blocked": False}
    except ClientError as e:
        print(f"Guardrail error: {e}")
        # Fail open - don't block if guardrail service is down
        return {"blocked": False}

# ═══════════════════════════════════════════════════════════════════════════
# RAG - Document retrieval for grounded answers
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("retrieve_document_context")
def retrieve_document_context(query, user_id):
    """Retrieve relevant document chunks from S3 for RAG context.
    
    Simple keyword-based retrieval from user's uploaded documents.
    For production, replace with Bedrock Knowledge Base or OpenSearch.
    """
    try:
        # List user's documents
        prefix = f"users/{user_id}/"
        response = s3.list_objects_v2(Bucket=DOCUMENT_BUCKET, Prefix=prefix, MaxKeys=5)
        
        if "Contents" not in response:
            return ""

        # Read and concatenate document content (simple approach)
        context_parts = []
        for obj in response["Contents"]:
            if obj["Size"] > 100000:  # Skip files > 100KB
                continue
            try:
                doc = s3.get_object(Bucket=DOCUMENT_BUCKET, Key=obj["Key"])
                content = doc["Body"].read().decode("utf-8", errors="ignore")
                # Take first 2000 chars of each doc as context
                context_parts.append(content[:2000])
            except Exception:
                continue

        return "\n\n".join(context_parts)[:4000]  # Cap total context

    except ClientError as e:
        print(f"RAG retrieval error: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# UPLOAD HANDLER - Presigned URL for document upload
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("handle_upload")
def handle_upload(event, user_id):
    """Generate presigned URL for document upload to S3."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON"})

    filename = body.get("filename", "").strip()
    if not filename:
        return resp(400, {"error": "filename is required"})

    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in ".-_")
    key = f"users/{user_id}/{safe_name}"

    # Validate file extension
    allowed_extensions = [".txt", ".md", ".pdf", ".csv", ".json", ".docx"]
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in allowed_extensions:
        return resp(400, {
            "error": f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        })

    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": DOCUMENT_BUCKET, "Key": key},
            ExpiresIn=300,  # 5 minutes
        )
        return resp(200, {
            "uploadUrl": presigned_url,
            "key": key,
            "expiresIn": 300,
        })
    except ClientError as e:
        print(f"Presigned URL error: {e}")
        return resp(500, {"error": "Failed to generate upload URL"})

# ═══════════════════════════════════════════════════════════════════════════
# HISTORY + USAGE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════
@xray_recorder.capture("handle_history")
def handle_history(event, user_id):
    """Retrieve conversation history for a session."""
    params = event.get("queryStringParameters") or {}
    session_id = params.get("sessionId", "").strip()

    if not session_id:
        return resp(400, {"error": "sessionId query parameter is required"})

    history = get_conversation_history(session_id, limit=50)
    return resp(200, {
        "sessionId": session_id,
        "messages": history,
        "count": len(history),
    })


@xray_recorder.capture("handle_usage")
def handle_usage(event, user_id):
    """Get token usage stats for the authenticated user."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage_today = get_usage(user_id, today)

    return resp(200, {
        "userId": user_id,
        "date": today,
        "tokensUsed": usage_today,
        "tokenBudget": MAX_TOKEN_BUDGET,
        "remaining": max(0, MAX_TOKEN_BUDGET - usage_today),
        "percentUsed": round((usage_today / MAX_TOKEN_BUDGET) * 100, 1),
    })


# ═══════════════════════════════════════════════════════════════════════════
# DYNAMODB OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════
def store_message(session_id, timestamp, role, content, ttl, user_id):
    """Store a message in the conversation table."""
    try:
        conv_table.put_item(Item={
            "sessionId": session_id,
            "timestamp": timestamp,
            "role": role,
            "content": content,
            "userId": user_id,
            "ttl": ttl,
        })
    except ClientError as e:
        print(f"DynamoDB write error: {e}")


def get_conversation_history(session_id, limit=MAX_HISTORY):
    """Retrieve conversation messages ordered by timestamp."""
    try:
        result = conv_table.query(
            KeyConditionExpression="sessionId = :sid",
            ExpressionAttributeValues={":sid": session_id},
            ScanIndexForward=True,
            Limit=limit,
        )
        return [
            {"role": i["role"], "content": i["content"], "timestamp": int(i["timestamp"])}
            for i in result.get("Items", [])
        ]
    except ClientError as e:
        print(f"DynamoDB read error: {e}")
        return []


def get_usage(user_id, date):
    """Get current token usage for a user on a given date."""
    try:
        result = usage_table.get_item(Key={"userId": user_id, "date": date})
        item = result.get("Item")
        return int(item["tokensUsed"]) if item else 0
    except ClientError as e:
        print(f"Usage read error: {e}")
        return 0


def update_usage(user_id, date, tokens):
    """Increment token usage for a user."""
    try:
        ttl = int(time.time()) + (30 * 86400)  # Keep 30 days
        usage_table.update_item(
            Key={"userId": user_id, "date": date},
            UpdateExpression="SET tokensUsed = if_not_exists(tokensUsed, :zero) + :t, #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={":t": tokens, ":zero": 0, ":ttl": ttl},
        )
    except ClientError as e:
        print(f"Usage write error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY - Custom CloudWatch Metrics
# ═══════════════════════════════════════════════════════════════════════════
def emit_metric(name, value, unit="Count"):
    """Emit a custom CloudWatch metric."""
    try:
        cloudwatch.put_metric_data(
            Namespace=APP_NAME,
            MetricData=[{
                "MetricName": name,
                "Value": value,
                "Unit": "Milliseconds" if name == "ModelLatency" else unit,
                "Dimensions": [{"Name": "Service", "Value": "Chatbot"}],
            }],
        )
    except Exception as e:
        print(f"Metric emit error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE HELPER
# ═══════════════════════════════════════════════════════════════════════════
def resp(status_code, body):
    """Build API Gateway proxy response with CORS headers."""
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
