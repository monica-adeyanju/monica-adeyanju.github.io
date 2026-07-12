# Serverless AI Chatbot

A fully serverless REST API that lets anyone chat with an AI (Claude via Amazon Bedrock). It remembers conversations using DynamoDB. The whole thing deploys as a single CloudFormation stack — no servers to manage, no Docker containers, nothing to SSH into.

## How It Works

```
User sends message → API Gateway → Lambda → Bedrock (Claude) → Response back
                                      ↕
                                   DynamoDB (saves conversation history)
```

**The flow:**

1. A user sends a POST request to `/chat` with a message (e.g., "What is serverless?")
2. **API Gateway** receives the HTTPS request and routes it to Lambda
3. **Lambda** (Python function) does the work:
   - Loads previous messages from DynamoDB for that session (so Claude has context)
   - Sends the full conversation to **Bedrock** (Amazon's managed AI service running Claude)
   - Gets the AI response back
   - Stores both the user message and AI reply in **DynamoDB** with a TTL (auto-deletes after 7 days)
   - Returns the response to the user
4. User gets back the AI answer + a session ID to continue the conversation

## AWS Services Used

| Service | Role |
|---------|------|
| **API Gateway** | The front door — accepts HTTPS requests, handles CORS |
| **Lambda** | The brain — runs the Python code, no server to maintain |
| **Bedrock** | The AI — hosts Claude, you pay per token, no GPU management |
| **DynamoDB** | The memory — stores chat history per session, scales infinitely |
| **S3** | The host — stores the chat UI static files (HTML, CSS, JS) |
| **CloudFront** | The CDN — serves the UI globally with HTTPS and caching |
| **CloudFormation** | The deployer — defines all resources as code, one command to create/destroy |

## Architecture Diagram

![Architecture](architecture.svg)

```
┌──────────┐     ┌─────────────────┐     ┌────────────┐     ┌─────────────────┐
│  Client  │────▶│  API Gateway    │────▶│   Lambda   │────▶│  Amazon Bedrock  │
│          │◀────│  (REST API)     │◀────│  (Python)  │◀────│  (Claude)        │
└──────────┘     └─────────────────┘     └─────┬──────┘     └─────────────────┘
      │                                         │
      │                                         ▼
      │                                  ┌─────────────┐
      │                                  │  DynamoDB   │
      │                                  │ (History)   │
      │                                  └─────────────┘
      │
      ▼
┌─────────────────┐     ┌─────────────┐
│  CloudFront     │────▶│  S3 Bucket  │
│  (CDN)          │     │  (Chat UI)  │
└─────────────────┘     └─────────────┘
```

## Features

- **Conversational AI** — Powered by Claude via Amazon Bedrock
- **Session Memory** — Maintains conversation context across messages
- **Auto-Cleanup** — TTL-based expiration of old conversations
- **CORS Enabled** — Ready for frontend integration
- **Zero Servers** — Fully serverless, pay only for what you use
- **One-Click Deploy** — Single CloudFormation stack, no manual steps

## Deploy to Your AWS Account

### One-Click Deploy

Click the button below to launch the stack in your AWS account:

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/new?stackName=ai-chatbot&templateURL=https://YOUR_BUCKET.s3.amazonaws.com/template.yaml)

> **Note:** To use the one-click button, first upload `template.yaml` to a public S3 bucket and update the URL above. Alternatively, use the CLI method below.

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
    BedrockModelId=anthropic.claude-3-haiku-20240307-v1:0 \
    ConversationTTLDays=7

# Get your API endpoint
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

## Prerequisites

- An AWS account with [Bedrock model access enabled](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) for Claude
- AWS CLI configured (for CLI deployment)

### Enable Bedrock Model Access

1. Go to the [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Model access** in the left sidebar
3. Click **Manage model access**
4. Enable access for **Anthropic → Claude** models
5. Wait for access status to show "Access granted"

## API Usage

### Send a Message

```bash
# Start a new conversation
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
# Continue the conversation (use the sessionId from above)
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
#     {"role": "user", "content": "What is serverless computing?", "timestamp": 1234567890},
#     {"role": "assistant", "content": "Serverless computing is...", "timestamp": 1234567891}
#   ],
#   "count": 2
# }
```

## Cost Estimate

For light usage (~100 conversations/day):
- **Lambda**: Free tier covers it (1M requests/month free)
- **API Gateway**: ~$0.35/month (100k requests)
- **DynamoDB**: Free tier covers it (25 GB storage, 25 WCU/RCU)
- **Bedrock (Claude Haiku)**: ~$0.50–$2.00/month depending on message length

**Total: Under $3/month** for a personal project.

## Updating the Lambda Code

The CloudFormation template includes inline placeholder code. To deploy the full Lambda function:

```bash
# Package the Lambda code
cd lambda
zip function.zip index.py

# Update the function
aws lambda update-function-code \
  --function-name ai-chatbot-handler \
  --zip-file fileb://function.zip
```

## Deploying the Chat UI

The stack creates an S3 bucket and CloudFront distribution for hosting the chat frontend. After deploying the CloudFormation stack:

```bash
# 1. Get your stack outputs
aws cloudformation describe-stacks --stack-name ai-chatbot --query 'Stacks[0].Outputs' --output table

# 2. Update the API endpoint in chat.js
# Open frontend/chat.js and replace API_ENDPOINT with the ApiEndpoint output value

# 3. Upload frontend files to S3
aws s3 sync frontend/ s3://YOUR_CHAT_UI_BUCKET_NAME/

# 4. Visit your chat UI
# Open the ChatUIURL from the stack outputs (CloudFront URL)
```

The chat UI is a simple, clean web interface where users can:
- Send messages and receive AI responses in real-time
- Maintain conversation context (session persists across messages)
- Start new conversations

No frameworks, no build step — just HTML, CSS, and vanilla JavaScript.

## Cleanup

To delete all resources:

```bash
aws cloudformation delete-stack --stack-name ai-chatbot
```

This removes the API Gateway, Lambda function, DynamoDB table, and IAM role.

## File Structure

```
projects/ai-chatbot/
├── template.yaml        # CloudFormation stack (all AWS resources)
├── architecture.svg     # Architecture diagram
├── lambda/
│   └── index.py         # Lambda function source code
├── frontend/
│   ├── index.html       # Chat UI web page
│   └── chat.js          # Frontend JavaScript (API calls, state)
└── README.md            # This file
```

## License

MIT — use this however you want.
