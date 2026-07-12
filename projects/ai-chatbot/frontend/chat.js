// ─── Configuration ───────────────────────────────────────────────────────────
// Replace this with your API Gateway endpoint from CloudFormation stack output
const API_ENDPOINT = "https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/prod";

// ─── State ──────────────────────────────────────────────────────────────────
let sessionId = null;
let isLoading = false;

// ─── DOM Elements ───────────────────────────────────────────────────────────
const chatContainer = document.getElementById("chatContainer");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const typingIndicator = document.getElementById("typingIndicator");
const status = document.getElementById("status");
const configBanner = document.getElementById("configBanner");

// Hide config banner if endpoint is set
if (!API_ENDPOINT.includes("YOUR_API_ID")) {
    configBanner.style.display = "none";
}

// ─── Send Message ───────────────────────────────────────────────────────────
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isLoading) return;

    // Clear welcome screen on first message
    const welcome = chatContainer.querySelector(".welcome");
    if (welcome) welcome.remove();

    // Show user message
    appendMessage("user", message);
    messageInput.value = "";

    // Show typing indicator
    setLoading(true);

    try {
        const response = await fetch(`${API_ENDPOINT}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                sessionId: sessionId,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        sessionId = data.sessionId;
        appendMessage("assistant", data.response);
        status.textContent = `Session: ${sessionId.slice(0, 8)}...`;

    } catch (error) {
        appendMessage("error", `Error: ${error.message}`);
        status.textContent = "Error — check API endpoint";
    } finally {
        setLoading(false);
    }
}

// ─── UI Helpers ─────────────────────────────────────────────────────────────
function appendMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = content;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setLoading(loading) {
    isLoading = loading;
    sendButton.disabled = loading;
    typingIndicator.style.display = loading ? "block" : "none";
    if (loading) {
        chatContainer.appendChild(typingIndicator);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

// ─── Keyboard Support ───────────────────────────────────────────────────────
messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// ─── New Chat ───────────────────────────────────────────────────────────────
function newChat() {
    sessionId = null;
    chatContainer.innerHTML = `
        <div class="welcome">
            <h2>Welcome to AI Chatbot</h2>
            <p>Powered by Amazon Bedrock (Claude). Ask me anything — I'll remember our conversation.</p>
        </div>
    `;
    status.textContent = "Ready";
}
