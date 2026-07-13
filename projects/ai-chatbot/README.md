# Production-Grade Serverless AI Chatbot

A fully serverless, production-grade AI chatbot built on AWS. Features authenticated users, document-grounded answers (RAG), content safety guardrails, token budget enforcement, multi-model failover, and full observability — all deployed as a single CloudFormation stack.

## What Makes This Production-Grade

| Concern | How It's Handled |
|---------|-----------------|
| **Authentication** | Cognito User Pools — email/password sign-up, JWT tokens, per-user sessions |
| **Content Safety** | Bedrock Guardrails — blocks harmful content, anonymizes PII, prevents prompt injection |
| **RAG** | Users upload documents to S3, AI grounds answers in that context |
| **Cost Control** | Per-user daily token budget with enforcement (429 when exceeded) |
| **Resilience** | Multi-model fallback — if primary model throttles, routes to secondary |
| **Observability** | X-Ray tracing, custom CloudWatch metrics, pre-built dashboard, error alarms |
| **Security** | Cognito authorizer on all API endpoints, least-privilege IAM, no public S3 |

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                     │
│   ┌─────────┐    ┌───────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │  Login  │    │   Chat UI     │    │  Upload Doc  │    │  Usage Bar   │  │
│   └────┬────┘    └──────┬────────┘    └──────┬───────┘    └──────┬───────┘  │
└────────┼────────────────┼────────────────────┼───────────────────┼──────────┘
         │                │                    │                   │
         ▼                ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLOUDFRONT (HTTPS CDN)                                │
│                         ┌─────────────────────┐                              │
│                         │   S3 (Frontend)     │                              │
│                         └─────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │  Authenticated API calls (JWT)
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY + COGNITO AUTHORIZER                           │
│    POST /chat    GET /history    POST /upload    GET /usage                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAMBDA (Python 3.12)                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Validate token budget  →  reject if over limit (429)            │    │
│  │  2. Apply INPUT guardrail  →  block harmful/injection content       │    │
│  │  3. Retrieve RAG context   →  pull relevant docs from S3           │    │
│  │  4. Build conversation     →  load history from DynamoDB            │    │
│  │  5. Call Bedrock (primary)  →  fallback to secondary on failure     │    │
│  │  6. Apply OUTPUT guardrail →  filter unsafe responses               │    │
│  │  7. Store messages          →  DynamoDB with TTL                    │    │
│  │  8. Track token usage       →  DynamoDB usage table                 │    │
│  │  9. Emit metrics            →  CloudWatch custom metrics            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                          X-Ray Tracing Active                                 │
└────────┬──────────────┬──────────────┬──────────────┬───────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────────┐
│   Bedrock    │ │ DynamoDB  │ │ DynamoDB  │ │   S3 (Documents) │
│  (Claude)    │ │  (Chat)   │ │  (Usage)  │ │   (RAG Source)   │
│  + Guardrail │ │           │ │           │ │                  │
└──────────────┘ └───────────┘ └───────────┘ └──────────────────┘
```

## AWS Services Used (10 services)

| Service | Role |
|---------|------|
| **Cognito** | User authentication — sign-up, sign-in, JWT tokens |
| **API Gateway** | REST API with Cognito authorizer on all endpoints |
| **Lambda** | Chatbot logic — routing, guardrails, RAG, fallback, metrics |
| **Bedrock** | AI inference (Claude) + Guardrails for content safety |
| **DynamoDB** (×2) | Conversation history + per-user token usage tracking |
| **S3** (×2) | Frontend hosting + document storage for RAG |
| **CloudFront** | CDN for the chat UI with HTTPS |
| **CloudWatch** | Custom metrics dashboard + error alarms |
| **X-Ray** | Distributed tracing across all components |
| **CloudFormation** | Infrastructure as Code — one file deploys everything |

## Features Deep Dive

### Multi-Model Fallback
If the primary model (Claude Haiku 4.5) is throttled or returns an error, the Lambda automatically retries with a fallback model (Claude Sonnet 4). No user-facing errors — the system self-heals.

### Bedrock Guardrails
Every message passes through Bedrock Guardrails twice:
- **Input**: blocks harmful content, prompt injection attacks
- **Output**: filters unsafe responses, anonymizes emails/phone numbers, blocks SSN/credit cards

### RAG (Retrieval-Augmented Generation)
Users upload documents (.txt, .md, .csv, .json, .pdf) via presigned S3 URLs. When RAG is enabled, the Lambda retrieves the user's documents and injects relevant context into the prompt — grounding the AI's answers in real data.

### Token Budget Enforcement
Each user has a configurable daily token budget (default: 50,000 tokens). The system tracks input + output tokens per request and returns HTTP 429 when the budget is exceeded. The frontend shows a real-time usage bar.

### Observability
- **X-Ray**: full distributed trace from API Gateway → Lambda → Bedrock/DynamoDB
- **Custom Metrics**: MessagesProcessed, TokensUsed, ModelLatency, FallbackInvocations, GuardrailBlocked, RateLimited
- **Dashboard**: pre-built CloudWatch dashboard with 4 widgets
- **Alarm**: triggers when Lambda error count exceeds threshold

### Authentication Flow
1. User signs up with email + password → Cognito sends verification email
2. User signs in → receives JWT (ID token + access token)
3. Frontend stores tokens in sessionStorage (cleared on tab close)
4. Every API call includes the JWT in the Authorization header
5. API Gateway validates the JWT via Cognito Authorizer before Lambda runs

## Deploy to Your AWS Account

### One-Click Deploy

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/new?stackName=ai-chatbot&templateURL=https://monica-adeyanju-cfn-templates.s3.amazonaws.com/template.yaml)

### Deploy via AWS CLI

```bash
git clone https://github.com/monica-adeyanju/monica-adeyanju.github.io.git
cd monica-adeyanju.github.io/projects/ai-chatbot

aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name ai-chatbot \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    PrimaryModelId=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
    FallbackModelId=us.anthropic.claude-sonnet-4-20250514-v1:0 \
    MaxTokenBudgetPerSession=50000

aws cloudformation describe-stacks \
  --stack-name ai-chatbot \
  --query 'Stacks[0].Outputs' \
  --output table
```

### Deploy via AWS Console

1. Open [CloudFormation Console](https://console.aws.amazon.com/cloudformation)
2. **Create stack** → Upload `template.yaml`
3. Stack name: `ai-chatbot`
4. Configure parameters (or keep defaults)
5. Acknowledge IAM resources → **Create stack**
6. Wait for CREATE_COMPLETE (~5 minutes)
7. Go to **Outputs** tab → open **ChatUIURL**

### After Deployment

1. **Upload Lambda code**: Package `lambda/index.py` and update the function
2. **Upload frontend**: Sync `frontend/` to the UI S3 bucket (update CONFIG values in auth.js first)
3. **Enable USER_PASSWORD_AUTH**: In Cognito console, add `ALLOW_USER_PASSWORD_AUTH` to the app client

```bash
# Update Lambda
cd lambda && zip function.zip index.py
aws lambda update-function-code \
  --function-name ai-chatbot-handler \
  --zip-file fileb://function.zip

# Update frontend config in auth.js, then:
aws s3 sync frontend/ s3://$(aws cloudformation describe-stacks --stack-name ai-chatbot --query 'Stacks[0].Outputs[?OutputKey==`ChatUIBucketName`].OutputValue' --output text)/
```

## Using the Chatbot

### Sign Up & Sign In
1. Open the CloudFront URL from stack outputs
2. Click "Sign Up" → enter email + password
3. Check your email for the verification code
4. Sign in with your credentials

### Chat
1. Type a message and hit Send
2. The AI responds with metadata (model used, tokens consumed, RAG indicator)
3. Your conversation persists within the session
4. The usage bar shows your daily token budget consumption

### Upload Documents (RAG)
1. Click "Upload Doc" in the toolbar
2. Select a .txt, .md, .csv, or .json file
3. After upload, check the "Use RAG" checkbox
4. Ask questions — the AI will ground answers in your uploaded documents

### Monitor Usage
- The usage bar updates after each message
- When you hit the daily limit, you'll see a "budget exceeded" error
- Budget resets at midnight UTC

## API Endpoints (Authenticated)

All endpoints require a valid Cognito JWT in the `Authorization` header.

| Method | Path | Description |
|--------|------|-------------|
| POST | /chat | Send a message. Body: `{"message": "...", "sessionId": "...", "useRAG": true}` |
| GET | /history?sessionId=xxx | Get conversation history |
| POST | /upload | Get presigned URL. Body: `{"filename": "doc.txt"}` |
| GET | /usage | Get token usage stats for current user |

### Example: Chat Request

```bash
TOKEN="your-cognito-id-token"

curl -X POST https://YOUR_API/prod/chat \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize my uploaded document", "useRAG": true}'

# Response:
# {
#   "response": "Based on your document...",
#   "sessionId": "abc-123",
#   "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
#   "tokensUsed": 847,
#   "ragUsed": true
# }
```

## Observability

### CloudWatch Dashboard
A pre-built dashboard is created with the stack. Find it at:
- Console → CloudWatch → Dashboards → `ai-chatbot-dashboard`

Widgets:
- **Messages Processed** (5-min intervals)
- **Tokens Used** (cumulative)
- **Latency & Fallback Invocations**
- **Guardrail Blocks & Rate Limits**

### X-Ray Traces
- Console → X-Ray → Traces
- Filter by service: `ai-chatbot-handler`
- See full request lifecycle: API GW → Lambda → Bedrock → DynamoDB

### Error Alarm
Triggers when Lambda errors exceed 5 in a 5-minute window.

## Cost Estimate

For moderate usage (~500 conversations/day):

| Service | Cost |
|---------|------|
| Lambda | Free tier |
| API Gateway | ~$1.75/month |
| DynamoDB (×2) | Free tier |
| S3 (×2) | ~$0.05/month |
| CloudFront | Free tier |
| Cognito | Free for first 50,000 MAU |
| Bedrock (Claude Haiku 4.5) | ~$2–8/month |
| X-Ray | Free tier (100k traces/month) |
| CloudWatch | ~$0.30/month |

**Total: ~$5–12/month** depending on usage.

## Cleanup

```bash
aws cloudformation delete-stack --stack-name ai-chatbot
```

Removes all resources. The document S3 bucket must be empty first (or delete objects manually).

## File Structure

```
projects/ai-chatbot/
├── template.yaml          # CloudFormation (all 10 services)
├── lambda/
│   └── index.py           # Full Lambda handler (guardrails, RAG, fallback, metrics)
├── frontend/
│   ├── index.html         # Chat UI with auth + upload + usage bar
│   ├── auth.js            # Cognito authentication module
│   └── chat.js            # Messaging, RAG toggle, file upload
└── README.md              # This file
```

## Prerequisites

- An AWS account (Bedrock models are auto-enabled since Sep 2025)
- AWS CLI configured (for CLI/manual deployment)

## License

MIT — use this however you want.
