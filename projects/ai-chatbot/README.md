# Serverless AI Chatbot

A fully serverless AI chatbot with a web interface, powered by **Amazon Bedrock (Claude)** with conversation history stored in **DynamoDB**. Deploy the entire stack — backend, frontend, and CDN — with a single CloudFormation template. No manual steps.

## How It Works

```
User sends message → API Gateway → Lambda → Bedrock (Claude) → Response back
                                      ↕
                                   DynamoDB (saves conversation history)
```

**The flow:**

1. User opens the CloudFront URL → loads the chat UI from S3
2. User types a message → JavaScript sends a POST request to API Gateway
3. **API Gateway** routes the request to **Lambda**
4. **Lambda** (Python) does the work:
   - Loads previous messages from DynamoDB for that session (so Claude has context)
   - Sends the full conversation to **Bedrock** (Claude)
   - Gets the AI response back
   - Stores both messages in **DynamoDB** with a TTL (auto-deletes after 7 days)
   - Returns the response
5. User sees the AI reply in the chat interface and can continue the conversation

## AWS Services Used

| Service | Role |
|---------|------|
| **API Gateway** | The front door — accepts HTTPS requests, handles CORS |
| **Lambda** | The brain — runs the Python chatbot code (deployed inline, no manual upload) |
| **Bedrock** | The AI — hosts Claude, pay per token, no GPU management |
| **DynamoDB** | The memory — stores chat history per session, scales infinitely |
| **S3** | The host — stores the chat UI files (auto-deployed by the stack) |
| **CloudFront** | The CDN — serves the UI globally with HTTPS and caching |
| **Custom Resource** | The automator — injects the API endpoint into the frontend and uploads to S3 |
| **CloudFormation** | The deployer — defines all resources as code, one command to create/destroy |

## Architecture Diagram

```
┌──────────────────┐
│   User Browser   │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────┐
│  CloudFront     │────▶│  S3 Bucket  │  ← Chat UI (auto-deployed)
│  (HTTPS CDN)    │     │  (Frontend) │
└────────┬────────┘     └─────────────┘
         │
         │ API calls
         ▼
┌─────────────────┐     ┌────────────┐     ┌─────────────────┐
│  API Gateway    │────▶│   Lambda   │────▶│  Amazon Bedrock  │
│  (REST API)     │◀────│  (Python)  │◀────│  (Claude)        │
└─────────────────┘     └─────┬──────┘     └─────────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  DynamoDB   │
                       │  (History)  │
                       └─────────────┘
```

## Features

- **Chat Web Interface** — Clean UI served via CloudFront, auto-deployed with correct API endpoint
- **Conversational AI** — Powered by Claude via Amazon Bedrock
- **Session Memory** — Maintains conversation context across messages
- **Auto-Cleanup** — TTL-based expiration of old conversations (configurable)
- **Fully Automated** — Lambda code, frontend files, and API wiring all deploy automatically
- **Zero Servers** — Fully serverless, pay only for what you use
- **One-Click Deploy** — Single CloudFormation stack, nothing to configure manually

## Deploy to Your AWS Account

### One-Click Deploy

Click the button below to launch the stack in your AWS account:

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/new?stackName=ai-chatbot&templateURL=https://monica-adeyanju-cfn-templates.s3.amazonaws.com/template.yaml)

> **Note:** You must have [Bedrock model access enabled](#enable-bedrock-model-access) for Claude before deploying.

### Deploy via AWS CLI

```bash
# Clone this repo
git clone https://github.com/monica-adeyanju/monica-adeyanju.github.io.git
cd monica-adeyanju.github.io/projects/ai-chatbot

# Deploy the stack
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name ai-chatbot \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    BedrockModelId=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
    ConversationTTLDays=7

# Get your outputs (including the chat UI URL)
aws cloudformation describe-stacks \
  --stack-name ai-chatbot \
  --query 'Stacks[0].Outputs' \
  --output table
```

### Deploy via AWS Console

1. Open the [CloudFormation Console](https://console.aws.amazon.com/cloudformation)
2. Click **Create stack** → **With new resources**
3. Upload `template.yaml`
4. Set the stack name (e.g., `ai-chatbot`)
5. Configure parameters:
   - **BedrockModelId**: Choose your preferred Claude model
   - **ConversationTTLDays**: How long to keep chat history (default: 7)
   - **StageName**: API stage name (default: prod)
6. Check "I acknowledge that this template creates IAM resources"
7. Click **Create stack**
8. Once complete, find the **ChatUIURL** in the Outputs tab — that's your chatbot

## What Gets Deployed (Automatically)

When the stack creates successfully, you get:

| Output | What It Is |
|--------|-----------|
| **ChatUIURL** | Your chatbot web interface URL (CloudFront) |
| **ApiEndpoint** | The REST API base URL |
| **ChatEndpoint** | POST here to send messages programmatically |
| **HistoryEndpoint** | GET conversation history |
| **ConversationTableName** | DynamoDB table name |

The frontend is deployed automatically with the correct API endpoint injected — no manual configuration needed.

## Prerequisites

- An AWS account with [Bedrock model access enabled](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) for Claude
- AWS CLI configured (for CLI deployment only)

### Enable Bedrock Model Access

1. Go to the [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Model access** in the left sidebar
3. Click **Manage model access**
4. Enable access for **Anthropic → Claude** models
5. Wait for access status to show "Access granted"

## Using the Chatbot

### Via the Web Interface (Recommended)

Once the stack is deployed:

1. Go to the **Outputs** tab of your CloudFormation stack
2. Copy the **ChatUIURL** (e.g., `https://d1234abcdef.cloudfront.net`)
3. Open it in your browser
4. Type a message in the input box and hit **Send**
5. The AI (Claude) will respond in the chat window
6. Keep chatting — the bot remembers your conversation within the session
7. Close the tab and come back later — your history is stored for 7 days (configurable)

> **Note:** CloudFront can take 5–15 minutes to fully activate after initial deployment. If you see a 403 error, wait a few minutes and refresh.

### Via API (for Integrations and Testing)

You can also interact with the chatbot programmatically using the REST API:

### Send a Message

```bash
curl -X POST https://YOUR_API_ENDPOINT/prod/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is serverless computing?"}'

# Response:
# {
#   "response": "Serverless computing is a cloud execution model where...",
#   "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# }
```

```bash
# Continue the conversation
curl -X POST https://YOUR_API_ENDPOINT/prod/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How does it compare to containers?", "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'
```

### Get Conversation History

```bash
curl "https://YOUR_API_ENDPOINT/prod/history?sessionId=a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Response:
# {
#   "sessionId": "a1b2c3d4-...",
#   "messages": [
#     {"role": "user", "content": "What is serverless?", "timestamp": 1234567890},
#     {"role": "assistant", "content": "Serverless computing is...", "timestamp": 1234567891}
#   ],
#   "count": 2
# }
```

## Cost Estimate

For light usage (~100 conversations/day):

| Service | Cost |
|---------|------|
| Lambda | Free tier (1M requests/month free) |
| API Gateway | ~$0.35/month |
| DynamoDB | Free tier (25 GB, 25 WCU/RCU) |
| S3 | ~$0.01/month |
| CloudFront | Free tier (1 TB/month) |
| Bedrock (Claude Haiku) | ~$0.50–$2.00/month |

**Total: Under $3/month** for a personal project.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "AI unavailable" error in chat | Bedrock model access not enabled | Enable Claude 3.5 Haiku in [Bedrock Model Access](https://console.aws.amazon.com/bedrock/home#/modelaccess) |
| 403 error on ChatUI URL | CloudFront still provisioning | Wait 5–15 minutes after stack creation |
| "ResourceNotFoundException" in Lambda logs | Model ID marked as legacy/end-of-life | Update stack with `us.anthropic.claude-haiku-4-5-20251001-v1:0` (inference profile ID with `us.` prefix) |
| Stack fails to create | Missing IAM acknowledgment | Check "I acknowledge that this template creates IAM resources" during deploy |
| CORS error in browser console | API Gateway misconfigured | Ensure stack deployed fully (check all resources are CREATE_COMPLETE) |

To view Lambda error logs:
1. Go to [CloudWatch Logs](https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups)
2. Find `/aws/lambda/ai-chatbot-handler`
3. Open the most recent log stream to see error details

## Cleanup

To delete all resources:

```bash
aws cloudformation delete-stack --stack-name ai-chatbot
```

This removes everything: API Gateway, Lambda functions, DynamoDB table, S3 bucket (contents auto-cleaned), CloudFront distribution, and IAM roles.

## File Structure

```
projects/ai-chatbot/
├── template.yaml        # CloudFormation stack (all resources + inline code)
├── lambda/
│   └── index.py         # Lambda function source (reference/readable version)
├── frontend/
│   ├── index.html       # Chat UI (reference/readable version)
│   └── chat.js          # Frontend JS (reference/readable version)
└── README.md            # This file
```

> **Note:** The `lambda/` and `frontend/` directories contain readable reference versions of the code. The actual deployed code lives inline in `template.yaml` so that the stack is fully self-contained — one file deploys everything.

## License

MIT — use this however you want.
