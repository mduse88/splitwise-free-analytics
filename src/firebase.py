"""Firebase Hosting deployment module."""

import base64
import hashlib
import os
import re
import subprocess
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import firebase_admin
from firebase_admin import credentials, firestore
from src.config import email as email_config
from src.config import app as app_config
from src.logging_utils import log_info, log_verbose, log_error


# Firebase Admin SDK initialization (lazy)
_firebase_app = None
_firestore_client = None


def _init_firebase_admin():
    """Initialize Firebase Admin SDK if not already initialized."""
    global _firebase_app, _firestore_client
    
    if _firebase_app is not None:
        return True
    
    # Get service account from environment
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not service_account_json:
        log_verbose("FIREBASE_SERVICE_ACCOUNT not configured - Firestore disabled")
        return False
    
    try:
        service_account = json.loads(service_account_json)
        cred = credentials.Certificate(service_account)
        _firebase_app = firebase_admin.initialize_app(cred)
        _firestore_client = firestore.client()
        log_verbose("Firebase Admin SDK initialized")
        return True
    except Exception as e:
        log_error("ERROR: Failed to initialize Firebase Admin", str(e))
        return False


def _store_key_in_firestore(key_hex: str, allowed_emails: list[str]) -> bool:
    """Store encryption key in Firestore.
    
    Security: The key is stored in Firestore, not in the page source.
    Firestore security rules check authorizedEmails to ensure only
    authorized users can fetch the key - this is server-side enforcement.
    
    Args:
        key_hex: Hex-encoded AES-256 key.
        allowed_emails: List of authorized emails (for Firestore rule validation).
        
    Returns:
        True if stored successfully, False otherwise.
    """
    if not _init_firebase_admin():
        return False
    
    try:
        doc_ref = _firestore_client.collection("config").document("dashboard")
        doc_ref.set({
            "encryptionKey": key_hex,
            "authorizedEmails": allowed_emails,  # Used by Firestore rules for auth
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        log_verbose("Encryption key stored in Firestore")
        return True
    except Exception as e:
        log_error("ERROR: Failed to store key in Firestore", str(e))
        return False


def get_allowed_emails() -> list[str]:
    """Get list of allowed emails from RECIPIENT_EMAIL config.
    
    Returns:
        List of normalized (lowercase, trimmed) email addresses.
    """
    if not email_config.recipient_email:
        return []
    
    emails = [e.strip().lower() for e in email_config.recipient_email.split(",")]
    return [e for e in emails if e]  # Filter out empty strings


def encrypt_dashboard_with_random_key(html: str) -> tuple[str, str]:
    """Encrypt dashboard HTML with AES-256-GCM using a random key.
    
    Security: Dashboard content is encrypted with a randomly generated key.
    The key is NOT in the page source - it's stored in Firestore and fetched
    after authentication. This prevents any derivation-based attacks.
    
    Args:
        html: Dashboard HTML content to encrypt.
        
    Returns:
        Tuple of (encrypted_hex, key_hex) where:
        - encrypted_hex: Hex-encoded (nonce + ciphertext + tag)
        - key_hex: Hex-encoded 32-byte random AES key
    """
    # Generate random 256-bit key
    key = os.urandom(32)
    
    # Encrypt with AES-GCM (provides authenticity + confidentiality)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    
    ciphertext = aesgcm.encrypt(nonce, html.encode("utf-8"), None)
    
    # Combine nonce + ciphertext (tag is appended by GCM)
    encrypted = nonce + ciphertext
    
    return encrypted.hex(), key.hex()


def prepare_deployment(dashboard_html_path: str) -> bool:
    """Prepare files for Firebase deployment.
    
    Security: The dashboard is AES-256-GCM encrypted inside index.html.
    The encryption key is randomly generated and stored in Firestore,
    NOT in the page source. Users must authenticate to fetch the key.
    
    Args:
        dashboard_html_path: Path to the generated dashboard HTML file.
        
    Returns:
        True if preparation succeeded, False otherwise.
    """
    firebase_public = "firebase_public"
    index_html_path = os.path.join(firebase_public, "index.html")
    
    # Check if firebase_public directory exists
    if not os.path.exists(firebase_public):
        log_info("ERROR: firebase_public directory not found")
        return False
    
    # Check if index.html exists
    if not os.path.exists(index_html_path):
        log_info("ERROR: firebase_public/index.html not found")
        return False
    
    # Get allowed emails and hashes
    allowed_emails = get_allowed_emails()
    if not allowed_emails:
        log_verbose("WARNING: No allowed emails configured (RECIPIENT_EMAIL)")
    
    # Read dashboard HTML and encrypt with random key
    try:
        with open(dashboard_html_path, "r", encoding="utf-8") as f:
            dashboard_content = f.read()
        
        # AES encrypt the dashboard with random key
        encrypted_hex, key_hex = encrypt_dashboard_with_random_key(dashboard_content)
        log_verbose("Dashboard encrypted with AES-256-GCM (random key)")
    except Exception as e:
        log_error("ERROR: Failed to encrypt dashboard", str(e))
        return False
    
    # Store encryption key in Firestore (required)
    #
    # Security: We must NEVER embed the key in the page source. If Firestore storage fails,
    # we abort deployment to prevent accidental plaintext-key exposure.
    if not _store_key_in_firestore(key_hex, allowed_emails):
        log_error(
            "ERROR: Failed to store key in Firestore. Refusing to deploy without Firestore-backed key.",
            "Check FIREBASE_SERVICE_ACCOUNT / Firestore setup / permissions."
        )
        return False
    
    # Read index.html and inject encrypted dashboard
    try:
        with open(index_html_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace placeholders
        content = content.replace("__TITLE_PLACEHOLDER__", app_config.title)
        content = content.replace("__DASHBOARD_DATA_PLACEHOLDER__", encrypted_hex)
        
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        log_error("ERROR: Failed to prepare index.html", str(e))
        return False
    
    # Remove dashboard.html if it exists (security: prevent direct access)
    dashboard_direct = os.path.join(firebase_public, "dashboard.html")
    if os.path.exists(dashboard_direct):
        try:
            os.remove(dashboard_direct)
        except Exception:
            pass  # Non-critical
    
    return True


def deploy() -> str | None:
    """Deploy to Firebase Hosting.
    
    Returns:
        The deployed URL if successful, None otherwise.
    """
    # Check for Firebase token (for CI) or assume logged in locally
    firebase_token = os.getenv("FIREBASE_TOKEN")
    # Check for project ID (for CI where .firebaserc is gitignored)
    firebase_project = os.getenv("FIREBASE_PROJECT_ID")
    
    # Build base command
    cmd_parts = ["firebase", "deploy", "--only", "hosting"]
    if firebase_project:
        cmd_parts.extend(["--project", firebase_project])
    if firebase_token:
        cmd_parts.extend(["--token", firebase_token])
    
    result = None
    
    # Strategy 1: Try direct execution (works in GitHub Actions where firebase is in PATH)
    try:
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=120
        )
    except FileNotFoundError:
        # Strategy 2: Try with nvm sourcing (for local dev with nvm-managed node)
        try:
            cmd_str = " ".join(cmd_parts)
            shell_cmd = f'source "$HOME/.nvm/nvm.sh" 2>/dev/null; {cmd_str}'
            result = subprocess.run(
                shell_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
        except Exception:
            log_info("ERROR: Firebase deploy failed")
            return None
    except subprocess.TimeoutExpired:
        log_info("ERROR: Firebase deploy timed out")
        return None
    except Exception:
        log_info("ERROR: Firebase deploy failed")
        return None
    
    if result is None:
        log_info("ERROR: Firebase deploy - no result")
        return None
    
    if result.returncode != 0:
        log_error("ERROR: Firebase deploy failed", result.stderr)
        return None
    
    # Extract URL from output
    # Firebase outputs something like: "Hosting URL: https://project-id.web.app"
    # Note: Firebase CLI may include ANSI escape codes in output, we need to strip them
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[[0-9;]*m')
    
    for line in result.stdout.split("\n"):
        if "Hosting URL:" in line:
            url = line.split("Hosting URL:")[-1].strip()
            # Strip ANSI escape codes from URL
            url = ansi_escape.sub('', url).strip()
            return url
    
    # Try to construct URL from .firebaserc
    try:
        with open(".firebaserc", "r") as f:
            firebaserc_config = json.load(f)
            project_id = firebaserc_config.get("projects", {}).get("default")
            if project_id:
                return f"https://{project_id}.web.app"
    except Exception:
        pass
    
    return None


def restore_index_html() -> None:
    """Restore index.html to clean template state after deployment.
    
    This ensures the placeholders are back for the next deployment
    and no sensitive data remains in the local file.
    """
    index_html_path = "firebase_public/index.html"
    
    # Clean template content with placeholders (Firestore key version, no client allowlist)
    template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>__TITLE_PLACEHOLDER__</title>
    <script defer src="/__/firebase/12.6.0/firebase-app-compat.js"></script>
    <script defer src="/__/firebase/12.6.0/firebase-auth-compat.js"></script>
    <script defer src="/__/firebase/12.6.0/firebase-firestore-compat.js"></script>
    <script defer src="/__/firebase/init.js"></script>
    <style>
        /* Login page styles - scoped to avoid conflicts with dashboard */
        body:not(.authenticated) { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; padding: 0; }
        body.authenticated { display: block; }
        #login-container { background: rgba(255, 255, 255, 0.95); padding: 48px 40px; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4); text-align: center; max-width: 400px; width: 90%; }
        #login-container .logo { font-size: 48px; margin-bottom: 16px; }
        #login-container h1 { color: #1a1a2e; font-size: 24px; font-weight: 600; margin-bottom: 8px; }
        #login-container .subtitle { color: #666; font-size: 14px; margin-bottom: 32px; }
        #sign-in-btn { display: inline-flex; align-items: center; gap: 12px; background: #4285f4; color: white; border: none; padding: 14px 28px; border-radius: 8px; font-size: 16px; font-weight: 500; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 4px 14px rgba(66, 133, 244, 0.4); }
        #sign-in-btn:hover { background: #3367d6; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(66, 133, 244, 0.5); }
        .google-icon { width: 20px; height: 20px; background: white; border-radius: 4px; padding: 2px; }
        #login-container #error { color: #dc3545; font-size: 14px; margin-top: 20px; padding: 12px; background: #fff5f5; border-radius: 8px; display: none; }
        #sign-out-btn { display: none; margin-top: 16px; background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-size: 14px; cursor: pointer; transition: background 0.2s ease; }
        #sign-out-btn:hover { background: #5a6268; }
        #login-container #loading { color: #666; font-size: 14px; margin-top: 20px; }
        .spinner { display: inline-block; width: 20px; height: 20px; border: 2px solid #ccc; border-top-color: #4285f4; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hidden { display: none !important; }
        #dashboard-container { display: none; width: 100%; min-height: 100vh; }
        body.authenticated #dashboard-container { display: block; }
        body.authenticated #login-container { display: none; }
    </style>
</head>
<body>
    <div id="login-container">
        <div class="logo">📊</div>
        <h1>__TITLE_PLACEHOLDER__</h1>
        <p class="subtitle">Sign in to view your expense dashboard</p>
        <button id="sign-in-btn" onclick="signIn()">
            <svg class="google-icon" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Sign in with Google
        </button>
        <div id="error"></div>
        <button id="sign-out-btn" onclick="signOut()">Try a different account</button>
        <div id="loading" class="hidden"><span class="spinner"></span>Checking authorization...</div>
    </div>
    <div id="dashboard-container"></div>
    <script id="dashboard-data" type="text/plain">__DASHBOARD_DATA_PLACEHOLDER__</script>
    <script>
        // Convert hex string to Uint8Array
        function hexToBytes(hex) {
            const bytes = new Uint8Array(hex.length / 2);
            for (let i = 0; i < hex.length; i += 2) {
                bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
            }
            return bytes;
        }
        
        // Fetch encryption key from Firestore (secure, requires auth)
        async function fetchKeyFromFirestore() {
            const db = firebase.firestore();
            const doc = await db.collection('config').doc('dashboard').get();
            if (!doc.exists) return null;
            const data = doc.data() || {};
            return data.encryptionKey || null;
        }
        
        // Import raw key bytes as CryptoKey
        async function importKey(keyHex) {
            const keyBytes = hexToBytes(keyHex);
            return await crypto.subtle.importKey(
                'raw',
                keyBytes,
                { name: 'AES-GCM', length: 256 },
                false,
                ['decrypt']
            );
        }
        
        // Decrypt AES-GCM encrypted dashboard
        async function decryptDashboard(encryptedHex, keyHex) {
            const encrypted = hexToBytes(encryptedHex);
            const nonce = encrypted.slice(0, 12);  // First 12 bytes are nonce
            const ciphertext = encrypted.slice(12);  // Rest is ciphertext + tag
            
            const key = await importKey(keyHex);
            
            const decrypted = await crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: nonce },
                key,
                ciphertext
            );
            
            return new TextDecoder().decode(decrypted);
        }
        
        function signIn() {
            const provider = new firebase.auth.GoogleAuthProvider();
            firebase.auth().signInWithPopup(provider).catch(error => { showError('Sign-in failed: ' + error.message); });
        }
        function signOut() { firebase.auth().signOut(); }
        function showError(message, showSignOut = false) {
            const errorEl = document.getElementById('error');
            errorEl.textContent = message;
            errorEl.style.display = 'block';
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('sign-out-btn').style.display = showSignOut ? 'inline-block' : 'none';
        }
        async function showDashboard() {
            const encryptedData = document.getElementById('dashboard-data').textContent.trim();
            if (encryptedData && !encryptedData.includes('PLACEHOLDER')) {
                try {
                    // Get encryption key from Firestore (required)
                    const keyHex = await fetchKeyFromFirestore();
                    if (!keyHex) {
                        throw new Error('Could not retrieve encryption key');
                    }
                    
                    // Decrypt the dashboard using AES-GCM
                    const dashboardHtml = await decryptDashboard(encryptedData, keyHex);
                    
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(dashboardHtml, 'text/html');
                    doc.querySelectorAll('style').forEach(style => { document.head.appendChild(style.cloneNode(true)); });
                    document.getElementById('dashboard-container').innerHTML = doc.body.innerHTML;
                    const externalScripts = [];
                    const inlineScripts = [];
                    doc.querySelectorAll('script').forEach(script => {
                        if (script.src) { externalScripts.push(script.src); }
                        else if (script.textContent.trim()) { inlineScripts.push(script.textContent); }
                    });
                    function loadExternalScripts(urls, callback) {
                        if (urls.length === 0) { callback(); return; }
                        let loaded = 0;
                        urls.forEach(url => {
                            const s = document.createElement('script');
                            s.src = url;
                            s.onload = s.onerror = () => { loaded++; if (loaded === urls.length) callback(); };
                            document.body.appendChild(s);
                        });
                    }
                    loadExternalScripts(externalScripts, () => {
                        inlineScripts.forEach(code => { const s = document.createElement('script'); s.textContent = code; document.body.appendChild(s); });
                    });
                    document.body.classList.add('authenticated');
                } catch (e) {
                    if (e && e.code === 'permission-denied') {
                        showError('Access denied. Your account is not authorized.', true);
                        return;
                    }
                    showError('Failed to decrypt dashboard: ' + (e?.message || String(e)));
                }
            } else { showError('Dashboard content not available'); }
        }
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(() => {
                firebase.auth().onAuthStateChanged(async user => {
                    if (user) {
                        document.getElementById('loading').classList.remove('hidden');
                        document.getElementById('sign-in-btn').classList.add('hidden');
                        await showDashboard();
                    } else {
                        document.body.classList.remove('authenticated');
                        document.getElementById('login-container').classList.remove('hidden');
                        document.getElementById('sign-in-btn').classList.remove('hidden');
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('error').style.display = 'none';
                        document.getElementById('sign-out-btn').style.display = 'none';
                    }
                });
            }, 500);
        });
    </script>
</body>
</html>'''
    
    try:
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(template)
    except Exception:
        pass  # Non-critical, will be overwritten on next git pull anyway


def deploy_dashboard(dashboard_html_path: str) -> str | None:
    """Full deployment workflow: prepare and deploy.
    
    Security: Dashboard is embedded in index.html (base64 encoded),
    not deployed as a separate file. Users must authenticate before
    the dashboard content is decoded and displayed.
    
    Args:
        dashboard_html_path: Path to the generated dashboard HTML file.
        
    Returns:
        The deployed Firebase URL if successful, None otherwise.
    """
    if not prepare_deployment(dashboard_html_path):
        return None
    
    url = deploy()
    
    # Restore placeholders for next deployment
    restore_index_html()
    
    return url
