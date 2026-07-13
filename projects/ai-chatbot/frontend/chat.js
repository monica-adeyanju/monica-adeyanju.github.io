/**
 * Chat Module - handles messaging, RAG toggle, file upload, and usage display.
 */

let sessionId = null;
let loading = false;

const chat = document.getElementById("chat");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const typingEl = document.getElementById("typing");

// ─── Send Message ──────────────────────────────────────────────────────────
async function sendMessage() {
    const msg = msgInput.value.trim();
    if (!msg || loading) return;

    addMessage("user", msg);
    msgInput.value = "";
    setLoading(true);

    const useRAG = document.getElementById("ragToggle").checked;

    try {
        const res = await apiFetch("/chat", {
            method: "POST",
            body: JSON.stringify({ message: msg, sessionId: sessionId, useRAG: useRAG }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || `HTTP ${res.status}`);
        }

        const data = await res.json();
        sessionId = data.sessionId;

        // Build metadata string
        const meta = [];
        if (data.model) meta.push(data.model.split("/").pop().split("-").slice(0,3).join("-"));
        if (data.tokensUsed) meta.push(`${data.tokensUsed} tokens`);
        if (data.ragUsed) meta.push("RAG");

        addMessage("assistant", data.response, meta.join(" · "));
        loadUsage();

    } catch (e) {
        addMessage("error", `Error: ${e.message}`);
    } finally {
        setLoading(false);
    }
}

// ─── UI Helpers ────────────────────────────────────────────────────────────
function addMessage(role, text, metaText) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;

    if (metaText) {
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = metaText;
        div.appendChild(meta);
    }

    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

function setLoading(state) {
    loading = state;
    sendBtn.disabled = state;
    typingEl.style.display = state ? "block" : "none";
    if (state) { chat.appendChild(typingEl); chat.scrollTop = chat.scrollHeight; }
}

// ─── Usage Display ─────────────────────────────────────────────────────────
async function loadUsage() {
    try {
        const res = await apiFetch("/usage", { method: "GET" });
        if (!res.ok) return;
        const data = await res.json();
        const pct = data.percentUsed || 0;
        document.getElementById("usageBar").style.width = `${Math.min(pct, 100)}%`;
        document.getElementById("usageText").textContent = `${pct}% used`;
    } catch (e) {
        // Silent fail on usage load
    }
}

// ─── File Upload ───────────────────────────────────────────────────────────
function showUploadModal() {
    document.getElementById("uploadModal").style.display = "flex";
    document.getElementById("uploadStatus").textContent = "";
}

function hideUploadModal() {
    document.getElementById("uploadModal").style.display = "none";
}

async function uploadFile() {
    const fileInput = document.getElementById("fileInput");
    const statusEl = document.getElementById("uploadStatus");
    const file = fileInput.files[0];

    if (!file) { statusEl.textContent = "Please select a file"; return; }

    statusEl.textContent = "Getting upload URL...";

    try {
        // Get presigned URL from our API
        const res = await apiFetch("/upload", {
            method: "POST",
            body: JSON.stringify({ filename: file.name }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || "Failed to get upload URL");
        }

        const { uploadUrl } = await res.json();

        // Upload file directly to S3
        statusEl.textContent = "Uploading...";
        const uploadRes = await fetch(uploadUrl, {
            method: "PUT",
            body: file,
            headers: { "Content-Type": file.type || "application/octet-stream" },
        });

        if (!uploadRes.ok) throw new Error("Upload to S3 failed");

        statusEl.textContent = `Uploaded "${file.name}" successfully. Enable RAG to use it.`;
        fileInput.value = "";

    } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
    }
}

// ─── API Helper (adds auth token) ─────────────────────────────────────────
async function apiFetch(path, options = {}) {
    const token = getToken();
    const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: token } : {}),
        ...(options.headers || {}),
    };
    return fetch(CONFIG.API_ENDPOINT + path, { ...options, headers });
}

// ─── Keyboard ──────────────────────────────────────────────────────────────
msgInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
