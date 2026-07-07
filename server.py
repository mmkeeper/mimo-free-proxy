#!/usr/bin/env python3
"""MiMo free channel -> standard OpenAI endpoint with optional SOCKS5 proxy.
Fingerprint -> bootstrap -> JWT (auto-refresh) -> /api/free-ai/openai/chat.
"""
import json, os, sys, time, base64, hashlib, threading, platform
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ===================== SETTINGS (edit here) =====================
UPSTREAM = "https://api.xiaomimimo.com"           # Base URL of the upstream API
CLIENT_FILE = r'C:\Projects\mimo_free_proxy\mimo-free-client'  # File to store fingerprint
LISTEN_HOST = "127.0.0.1"                         # Host to bind
LISTEN_PORT = 8788                                # Port
LOCAL_KEY = "sk-mimo-keeper-unique-key"            # API key to access this proxy

# ---------- SOCKS5 Proxy (optional) ----------
SOCKS5_HOST = None            # set to e.g. "127.0.0.1" to enable
SOCKS5_PORT = None            # e.g. 1080
SOCKS5_USERNAME = None        # if needed
SOCKS5_PASSWORD = None        # if needed
# ================================================================

BOOTSTRAP_URL = f"{UPSTREAM}/api/free-ai/bootstrap"
CHAT_URL = f"{UPSTREAM}/api/free-ai/openai/chat"
UPSTREAM_MODEL = "mimo-auto"
MAX_OUTPUT_TOKENS = 131072
REFRESH_MARGIN = 300

MIMO_GUARD_TEXT = (
    "You are MiMoCode, an interactive CLI tool that helps users with "
    "software engineering tasks. Use the instructions below and the tools "
    "available to you to assist the user.\n\n"
    "IMPORTANT: You must NEVER generate or guess URLs for the user unless you "
    "are confident that the URLs are for helping the user with programming. "
    "You may use URLs provided by the user in their messages or local files.\n\n"
    "IMPORTANT: Assist with authorized security testing, defensive security, "
    "CTF challenges, and educational contexts."
)

_jwt = None
_jwt_exp = 0
_lock = threading.Lock()

# ---------- Build proxy dict for requests ----------
_proxy_dict = None
if SOCKS5_HOST and SOCKS5_PORT:
    proto = "socks5"
    if SOCKS5_USERNAME and SOCKS5_PASSWORD:
        auth = f"{SOCKS5_USERNAME}:{SOCKS5_PASSWORD}@"
    else:
        auth = ""
    url = f"{proto}://{auth}{SOCKS5_HOST}:{SOCKS5_PORT}"
    _proxy_dict = {
        "http": url,
        "https": url
    }
    print(f"[*] Using SOCKS5 proxy: {SOCKS5_HOST}:{SOCKS5_PORT}", file=sys.stderr)
else:
    _proxy_dict = None
# -------------------------------------------------

def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)

def get_fp():
    try:
        v = open(CLIENT_FILE).read().strip()
        if v:
            return v
    except Exception:
        pass
    cpu = platform.processor() or "x86_64"
    try:
        user = os.getlogin()
    except Exception:
        user = os.environ.get("USER", "root")
    raw = "|".join([platform.node(), "linux", "x64", cpu, user])
    fp = hashlib.sha256(raw.encode()).hexdigest()
    try:
        os.makedirs(os.path.dirname(CLIENT_FILE), exist_ok=True)
        open(CLIENT_FILE, "w").write(fp)
        os.chmod(CLIENT_FILE, 0o600)
    except Exception as e:
        log("warn: cannot persist fingerprint", e)
    return fp

def _decode_exp(jwt):
    try:
        p = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "=="))
        if isinstance(p.get("exp"), (int, float)):
            return p["exp"] * 1000
    except Exception:
        pass
    return time.time() * 1000 + 3600 * 1000

def _bootstrap():
    body = json.dumps({"client": get_fp()})
    headers = {"Content-Type": "application/json"}
    resp = requests.post(BOOTSTRAP_URL, data=body, headers=headers,
                         proxies=_proxy_dict, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    jwt = data.get("jwt")
    if not jwt:
        raise RuntimeError("bootstrap missing jwt")
    return jwt, _decode_exp(jwt)

def get_jwt(force=False):
    global _jwt, _jwt_exp
    with _lock:
        now = time.time() * 1000
        if not force and _jwt and (_jwt_exp - now) > REFRESH_MARGIN * 1000:
            return _jwt
        _jwt, _jwt_exp = _bootstrap()
        log(f"JWT refreshed, exp in {int((_jwt_exp-now)/1000)}s")
        return _jwt

def upstream_chat(payload):
    payload = dict(payload)
    payload["model"] = UPSTREAM_MODEL
    # Inject the required official guard system prompt
    if MIMO_GUARD_TEXT:
        msgs = list(payload.get("messages") or [])
        already = (msgs and msgs[0].get("role") == "system" and
                   isinstance(msgs[0].get("content"), str) and
                   msgs[0]["content"].startswith(MIMO_GUARD_TEXT[:80]))
        if not already:
            msgs.insert(0, {"role": "system", "content": MIMO_GUARD_TEXT})
        payload["messages"] = msgs
    for f in ("max_tokens", "max_completion_tokens"):
        v = payload.get(f)
        if isinstance(v, int) and v > MAX_OUTPUT_TOKENS:
            log(f"clamp {f} {v} -> {MAX_OUTPUT_TOKENS}")
            payload[f] = MAX_OUTPUT_TOKENS

    def _do(jwt):
        headers = {
            "Authorization": f"Bearer {jwt}",
            "X-Mimo-Source": "mimocode-cli-free",
            "Content-Type": "application/json"
        }
        # Use stream=True so we can relay chunks
        return requests.post(CHAT_URL, json=payload, headers=headers,
                             proxies=_proxy_dict, stream=True, timeout=300)

    try:
        resp = _do(get_jwt())
        if resp.status_code in (401, 403):
            log("got", resp.status_code, "-> refresh JWT retry")
            resp.close()
            resp = _do(get_jwt(force=True))
        resp.raise_for_status()
        return resp
    except requests.exceptions.RequestException as e:
        # Convert to something we can raise as HTTPError-like
        raise RuntimeError(f"upstream request failed: {e}")

MODELS_RESP = {
    "object": "list",
    "data": [
        {"id": "mimo-auto", "object": "model", "created": 0, "owned_by": "xiaomi-mimo-free"}
    ]
}

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _auth_ok(self):
        if not LOCAL_KEY:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {LOCAL_KEY}"

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            if not self._auth_ok():
                return self._json(401, {"error": {"message": "invalid key"}})
            return self._json(200, MODELS_RESP)
        if self.path.rstrip("/").endswith("/health"):
            return self._json(200, {"status": "ok"})
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if "/chat/completions" not in self.path:
            return self._json(404, {"error": {"message": "not found"}})
        if not self._auth_ok():
            return self._json(401, {"error": {"message": "invalid key"}})
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n).decode())
        except Exception as e:
            return self._json(400, {"error": {"message": f"bad request: {e}"}})
        try:
            resp = upstream_chat(payload)
        except Exception as e:
            return self._json(502, {"error": {"message": str(e)}})

        self.send_response(200)
        self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception as e:
            log("stream relay ended", repr(e))
        finally:
            resp.close()

def main():
    get_fp()
    try:
        get_jwt()
        log("startup JWT ok")
    except Exception as e:
        log("startup bootstrap failed (will retry on request):", e)
    srv = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    log(f"MiMo Free Proxy on http://{LISTEN_HOST}:{LISTEN_PORT} auth={'ON' if LOCAL_KEY else 'OFF'}")
    srv.serve_forever()

if __name__ == "__main__":
    main()