/**
 * Cognito Authentication Module
 * Uses AWS Cognito User Pools with SRP auth flow (no Amplify dependency).
 * Stores tokens in sessionStorage for security.
 */

// ─── Configuration (injected by deploy script) ─────────────────────────────
const CONFIG = {
    API_ENDPOINT: "__API_ENDPOINT__",
    USER_POOL_ID: "__USER_POOL_ID__",
    CLIENT_ID: "__CLIENT_ID__",
    REGION: "__REGION__",
};

// ─── Token Management ──────────────────────────────────────────────────────
function getToken() {
    return sessionStorage.getItem("id_token");
}

function setTokens(idToken, accessToken, refreshToken) {
    sessionStorage.setItem("id_token", idToken);
    sessionStorage.setItem("access_token", accessToken);
    if (refreshToken) sessionStorage.setItem("refresh_token", refreshToken);
}

function clearTokens() {
    sessionStorage.removeItem("id_token");
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("refresh_token");
}

function getUserEmail() {
    const token = getToken();
    if (!token) return null;
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        return payload.email || payload["cognito:username"];
    } catch { return null; }
}

function isLoggedIn() {
    const token = getToken();
    if (!token) return false;
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        return payload.exp * 1000 > Date.now();
    } catch { return false; }
}

// ─── Auth UI ───────────────────────────────────────────────────────────────
let isSignUp = false;

function toggleAuthMode() {
    isSignUp = !isSignUp;
    document.getElementById("authTitle").textContent = isSignUp ? "Create Account" : "Sign In";
    document.getElementById("authSubtitle").textContent = isSignUp
        ? "Create an account to start chatting"
        : "Sign in to start chatting with AI";
    document.getElementById("authBtn").textContent = isSignUp ? "Sign Up" : "Sign In";
    document.getElementById("authConfirm").style.display = isSignUp ? "block" : "none";
    document.getElementById("authSwitch").innerHTML = isSignUp
        ? 'Already have an account? <a onclick="toggleAuthMode()">Sign In</a>'
        : 'Don\'t have an account? <a onclick="toggleAuthMode()">Sign Up</a>';
    document.getElementById("authError").style.display = "none";
}

function showAuthError(msg) {
    const el = document.getElementById("authError");
    el.textContent = msg;
    el.style.display = "block";
}

async function handleAuth() {
    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value;
    const confirm = document.getElementById("authConfirm").value;

    if (!email || !password) return showAuthError("Email and password required");
    if (isSignUp && password !== confirm) return showAuthError("Passwords don't match");
    if (isSignUp && password.length < 8) return showAuthError("Password must be at least 8 characters");

    const endpoint = `https://cognito-idp.${CONFIG.REGION}.amazonaws.com/`;
    
    try {
        if (isSignUp) {
            // Sign Up
            const res = await fetch(endpoint, {
                method: "POST",
                headers: {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.SignUp"},
                body: JSON.stringify({ClientId: CONFIG.CLIENT_ID, Username: email, Password: password, UserAttributes: [{Name: "email", Value: email}]}),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.message || "Sign up failed");
            showAuthError("Account created! Check your email to verify, then sign in.");
            isSignUp = false;
            toggleAuthMode();
        } else {
            // Sign In (InitiateAuth with USER_PASSWORD_AUTH for simplicity)
            const res = await fetch(endpoint, {
                method: "POST",
                headers: {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"},
                body: JSON.stringify({
                    AuthFlow: "USER_PASSWORD_AUTH",
                    ClientId: CONFIG.CLIENT_ID,
                    AuthParameters: {USERNAME: email, PASSWORD: password},
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.message || "Sign in failed");

            const result = data.AuthenticationResult;
            setTokens(result.IdToken, result.AccessToken, result.RefreshToken);
            showApp();
        }
    } catch (e) {
        showAuthError(e.message);
    }
}

function signOut() {
    clearTokens();
    document.getElementById("app").style.display = "none";
    document.getElementById("authScreen").style.display = "flex";
}

function showApp() {
    document.getElementById("authScreen").style.display = "none";
    document.getElementById("app").style.display = "flex";
    document.getElementById("userInfo").textContent = getUserEmail() || "";
    loadUsage();
}

// ─── Init ──────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
    if (isLoggedIn()) {
        showApp();
    }
});
