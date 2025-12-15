"""Firebase Hosting deployment module."""

import base64
import os
import re
import subprocess
import json
from src.config import email as email_config
from src.logging_utils import log_info, log_verbose, log_error


def get_allowed_emails() -> list[str]:
    """Get list of allowed emails from RECIPIENT_EMAIL config.
    
    Returns:
        List of lowercase email addresses.
    """
    if not email_config.recipient_email:
        return []
    
    emails = [e.strip().lower() for e in email_config.recipient_email.split(",")]
    return [e for e in emails if e]  # Filter out empty strings


def prepare_deployment(dashboard_html_path: str) -> bool:
    """Prepare files for Firebase deployment.
    
    Security: The dashboard is embedded (base64 encoded) inside index.html,
    not deployed as a separate accessible file. This prevents direct URL access.
    
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
    
    # Read dashboard HTML and encode it
    try:
        with open(dashboard_html_path, "r", encoding="utf-8") as f:
            dashboard_content = f.read()
        dashboard_base64 = base64.b64encode(dashboard_content.encode("utf-8")).decode("ascii")
    except Exception as e:
        log_error("ERROR: Failed to read dashboard", str(e))
        return False
    
    # Get allowed emails
    allowed_emails = get_allowed_emails()
    if not allowed_emails:
        log_verbose("WARNING: No allowed emails configured (RECIPIENT_EMAIL)")
    
    # Read index.html and inject both dashboard data and allowed emails
    try:
        with open(index_html_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace placeholders
        emails_json = json.dumps(allowed_emails)
        content = content.replace("__ALLOWED_EMAILS_PLACEHOLDER__", emails_json)
        content = content.replace("__DASHBOARD_DATA_PLACEHOLDER__", dashboard_base64)
        
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
    
    # #region agent log
    log_info(f"[DEBUG-CI] deploy() called, has_token={bool(firebase_token)}")
    # #endregion
    
    # Build base command
    cmd_parts = ["firebase", "deploy", "--only", "hosting"]
    if firebase_token:
        cmd_parts.extend(["--token", firebase_token])
    
    result = None
    
    # Strategy 1: Try direct execution (works in GitHub Actions where firebase is in PATH)
    try:
        # #region agent log
        log_info("[DEBUG-CI] Trying direct firebase execution...")
        # #endregion
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=120
        )
        # #region agent log
        log_info(f"[DEBUG-CI] Direct exec result: returncode={result.returncode}")
        # #endregion
    except FileNotFoundError:
        # #region agent log
        log_info("[DEBUG-CI] Direct exec failed (FileNotFoundError), trying shell with nvm...")
        # #endregion
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
            # #region agent log
            log_info(f"[DEBUG-CI] Shell exec result: returncode={result.returncode}")
            # #endregion
        except Exception as e:
            log_info(f"ERROR: Firebase deploy failed - {type(e).__name__}")
            return None
    except subprocess.TimeoutExpired:
        log_info("ERROR: Firebase deploy timed out")
        return None
    except Exception as e:
        log_info(f"ERROR: Firebase deploy failed - {type(e).__name__}")
        return None
    
    if result is None:
        log_info("ERROR: Firebase deploy - no result")
        return None
    
    if result.returncode != 0:
        # #region agent log
        log_info(f"[DEBUG-CI] Deploy failed, stderr length: {len(result.stderr)}")
        # #endregion
        log_error("ERROR: Firebase deploy failed", result.stderr)
        return None
    
    # #region agent log
    log_info(f"[DEBUG-CI] Deploy succeeded, stdout length: {len(result.stdout)}")
    # #endregion
    
    # Extract URL from output
    # Firebase outputs something like: "Hosting URL: https://project-id.web.app"
    # Note: Firebase CLI may include ANSI escape codes in output, we need to strip them
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[[0-9;]*m')
    
    for line in result.stdout.split("\n"):
        if "Hosting URL:" in line:
            url = line.split("Hosting URL:")[-1].strip()
            # Strip ANSI escape codes from URL
            url = ansi_escape.sub('', url).strip()
            # #region agent log
            log_info(f"[DEBUG-CI] Found URL in output (cleaned): {url}")
            # #endregion
            return url
    
    # #region agent log
    log_info("[DEBUG-CI] No 'Hosting URL:' found in output, trying .firebaserc fallback")
    # #endregion
    
    # Try to construct URL from .firebaserc
    try:
        with open(".firebaserc", "r") as f:
            firebaserc_config = json.load(f)
            project_id = firebaserc_config.get("projects", {}).get("default")
            if project_id:
                url = f"https://{project_id}.web.app"
                # #region agent log
                log_info(f"[DEBUG-CI] Constructed URL from .firebaserc: {url}")
                # #endregion
                return url
    except Exception:
        pass
    
    log_info("[DEBUG-CI] Could not determine Firebase URL")
    return None


def restore_index_html() -> None:
    """Restore index.html to clean template state after deployment.
    
    This ensures the placeholders are back for the next deployment
    and no sensitive data remains in the local file.
    """
    index_html_path = "firebase_public/index.html"
    
    # Clean template content with placeholders
    template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Family Expenses Dashboard</title>
    <script defer src="/__/firebase/12.6.0/firebase-app-compat.js"></script>
    <script defer src="/__/firebase/12.6.0/firebase-auth-compat.js"></script>
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
        <h1>Family Expenses</h1>
        <p class="subtitle">Sign in to view your expense dashboard</p>
        <button id="sign-in-btn" onclick="signIn()">
            <svg class="google-icon" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Sign in with Google
        </button>
        <div id="error"></div>
        <div id="loading" class="hidden"><span class="spinner"></span>Checking authorization...</div>
    </div>
    <div id="dashboard-container"></div>
    <script id="dashboard-data" type="text/plain">__DASHBOARD_DATA_PLACEHOLDER__</script>
    <script>
        const ALLOWED_EMAILS = __ALLOWED_EMAILS_PLACEHOLDER__;
        function signIn() {
            const provider = new firebase.auth.GoogleAuthProvider();
            firebase.auth().signInWithPopup(provider).catch(error => { showError('Sign-in failed: ' + error.message); });
        }
        function showError(message) { const errorEl = document.getElementById('error'); errorEl.textContent = message; errorEl.style.display = 'block'; document.getElementById('loading').classList.add('hidden'); }
        function showDashboard() {
            const encodedData = document.getElementById('dashboard-data').textContent.trim();
            if (encodedData && !encodedData.includes('PLACEHOLDER')) {
                try {
                    const dashboardHtml = new TextDecoder().decode(Uint8Array.from(atob(encodedData), c => c.charCodeAt(0)));
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
                } catch (e) { showError('Failed to load dashboard: ' + e.message); }
            } else { showError('Dashboard content not available'); }
        }
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(() => {
                firebase.auth().onAuthStateChanged(user => {
                    if (user) {
                        document.getElementById('loading').classList.remove('hidden');
                        document.getElementById('sign-in-btn').classList.add('hidden');
                        if (ALLOWED_EMAILS.includes(user.email.toLowerCase())) { showDashboard(); }
                        else { showError('Access denied. Your email (' + user.email + ') is not authorized.'); firebase.auth().signOut(); }
                    } else {
                        document.body.classList.remove('authenticated');
                        document.getElementById('login-container').classList.remove('hidden');
                        document.getElementById('sign-in-btn').classList.remove('hidden');
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('error').style.display = 'none';
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
    # #region agent log
    log_info(f"[DEBUG-CI] deploy_dashboard() called with path: {dashboard_html_path}")
    # #endregion
    
    if not prepare_deployment(dashboard_html_path):
        # #region agent log
        log_info("[DEBUG-CI] prepare_deployment() returned False")
        # #endregion
        return None
    
    # #region agent log
    log_info("[DEBUG-CI] prepare_deployment() succeeded, calling deploy()")
    # #endregion
    
    url = deploy()
    
    # #region agent log
    log_info(f"[DEBUG-CI] deploy() returned: '{url}'")
    # #endregion
    
    # Restore placeholders for next deployment
    restore_index_html()
    
    # #region agent log
    log_info(f"[DEBUG-CI] deploy_dashboard() returning: '{url}'")
    # #endregion
    
    return url
