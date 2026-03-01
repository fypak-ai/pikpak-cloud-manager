import os, json, time, hashlib, uuid, re
from flask import Flask, request, jsonify
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# ── CORS: allow GitHub Pages and any origin ──────────────────────────────
try:
    from flask_cors import CORS
    CORS(app, origins="*", supports_credentials=False)
except ImportError:
    @app.after_request
    def add_cors(resp):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        return resp

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def preflight(path):
    from flask import Response
    r = Response()
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return r, 204
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pikpak_tokens.json')

# ======================== PikPak API Constants (from AList source) ========================
WEB_CLIENT_ID = "YUMx5nI8ZU8Ap8pm"
WEB_CLIENT_SECRET = "dbw2OtmVEeuUvIptb1Coyg"
WEB_CLIENT_VERSION = "2.0.0"
WEB_PACKAGE_NAME = "mypikpak.com"
WEB_SDK_VERSION = "8.0.3"
WEB_ALGORITHMS = [
    "C9qPpZLN8ucRTaTiUMWYS9cQvWOE",
    "+r6CQVxjzJV6LCV",
    "F",
    "pFJRC",
    "9WXYIDGrwTCz2OiVlgZa90qpECPD6olt",
    "/750aCr4lm/Sly/c",
    "RB+DT/gZCrbV",
    "",
    "CyLsf7hdkIRxRm215hl",
    "7xHvLi2tOYP0Y92b",
    "ZGTXXxu8E/MIWaEDB+Sm/",
    "1UI3",
    "E7fP5Pfijd+7K+t6Tg/NhuLq0eEUVChpJSkrKxpO",
    "ihtqpG6FMt65+Xk+tWUH2",
    "NhXXU9rg4XXdzo7u5o",
]

API_USER = "https://user.mypikpak.net"
API_DRIVE = "https://api-drive.mypikpak.net"

import requests as req_lib

def get_device_id():
    """Persistent device ID so captcha verification sticks"""
    did_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pikpak_device.json')
    try:
        with open(did_file, 'r') as f:
            return json.load(f)['device_id']
    except:
        did = str(uuid.uuid4()).replace('-', '')[:32]
        with open(did_file, 'w') as f:
            json.dump({'device_id': did}, f)
        return did

DEVICE_ID = get_device_id()

def get_captcha_sign():
    """Generate captcha_sign using the same algorithm as AList"""
    timestamp = str(int(time.time() * 1000))
    s = f"{WEB_CLIENT_ID}{WEB_CLIENT_VERSION}{WEB_PACKAGE_NAME}{DEVICE_ID}{timestamp}"
    for alg in WEB_ALGORITHMS:
        s = hashlib.md5((s + alg).encode()).hexdigest()
    sign = "1." + s
    return timestamp, sign

def captcha_init_for_login(username):
    """captcha/init for login: meta has email/phone/username only"""
    metas = {}
    if re.match(r'\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*', username):
        metas["email"] = username
    elif 11 <= len(username) <= 18:
        metas["phone_number"] = username
    else:
        metas["username"] = username

    body = {
        "action": "POST:/v1/auth/signin",
        "captcha_token": "",
        "client_id": WEB_CLIENT_ID,
        "device_id": DEVICE_ID,
        "meta": metas,
        "redirect_uri": "xlaccsdk01://xbase.cloud/callback?state=harbor",
    }

    r = req_lib.post(
        f"{API_USER}/v1/shield/captcha/init",
        json=body,
        params={"client_id": WEB_CLIENT_ID},
        headers={"User-Agent": "Mozilla/5.0", "X-Device-ID": DEVICE_ID}
    )
    data = r.json()
    captcha_token = data.get("captcha_token", "")
    url = data.get("url", "")
    return captcha_token, url

def captcha_init_for_action(action, user_id="", existing_captcha_token=""):
    """captcha/init for post-login actions: meta has captcha_sign, timestamp, etc."""
    timestamp, captcha_sign = get_captcha_sign()
    metas = {
        "client_version": WEB_CLIENT_VERSION,
        "package_name": WEB_PACKAGE_NAME,
        "user_id": user_id,
        "timestamp": timestamp,
        "captcha_sign": captcha_sign,
    }

    body = {
        "action": action,
        "captcha_token": existing_captcha_token,
        "client_id": WEB_CLIENT_ID,
        "device_id": DEVICE_ID,
        "meta": metas,
        "redirect_uri": "xlaccsdk01://xbase.cloud/callback?state=harbor",
    }

    r = req_lib.post(
        f"{API_USER}/v1/shield/captcha/init",
        json=body,
        params={"client_id": WEB_CLIENT_ID},
        headers={"User-Agent": "Mozilla/5.0", "X-Device-ID": DEVICE_ID}
    )
    data = r.json()
    return data.get("captcha_token", ""), data.get("url", "")

# ======================== Token Persistence ========================
def load_tokens():
    try:
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

# ======================== Auth Routes ========================
# Store pending captcha state for the 2-step flow
pending_captcha = {}

@app.route('/api/login', methods=['POST'])
def login():
    global pending_captcha
    data = request.json
    method = data.get('method', 'password')

    if method == 'token':
        access_token = data.get('access_token', '').strip()
        if not access_token:
            return jsonify({"error": "Access token vazio"}), 400
        # Strip common mistakes: "Bearer " prefix, quotes, whitespace
        if access_token.lower().startswith('bearer '):
            access_token = access_token[7:].strip()
        access_token = access_token.strip('"').strip("'").strip()

        # Get a captcha token for the validation request
        ct, _ = captcha_init_for_action("GET:/drive/v1/about", "")

        r = req_lib.get(
            f"{API_DRIVE}/drive/v1/about",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Device-ID": DEVICE_ID,
                "X-Captcha-Token": ct or "",
                "User-Agent": "Mozilla/5.0",
            }
        )
        if r.status_code == 200:
            resp_data = r.json()
            tokens = load_tokens()
            tokens['access_token'] = access_token
            tokens['user_id'] = resp_data.get('sub', '')
            save_tokens(tokens)
            return jsonify({"success": True, "message": "Login via token OK"})
        elif r.status_code in (401, 403):
            return jsonify({"error": f"Token expirado ou invalido (HTTP {r.status_code}). Copie novamente do Network tab."}), 401
        else:
            # Show detailed error for debugging
            try:
                err_body = r.json()
                detail = err_body.get('error_description') or err_body.get('error') or json.dumps(err_body)[:200]
            except:
                detail = r.text[:200]
            return jsonify({"error": f"HTTP {r.status_code}: {detail}. Tente salvar direto (sem validar)?", "can_force": True}), 400

    if method == 'captcha_retry':
        # Step 2: User completed captcha, retry with stored captcha_token
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        stored = pending_captcha.get(username, {})
        captcha_token = stored.get('captcha_token', '')

        if not captcha_token:
            # Try calling captcha/init again - maybe it's verified now
            captcha_token, url = captcha_init_for_login(username)
            if url:
                # Extract captcha_token from the URL params
                parsed = parse_qs(urlparse(url).query)
                ct_from_url = parsed.get('captcha_token', [''])[0]
                if ct_from_url:
                    captcha_token = ct_from_url
                return jsonify({
                    "error": "Captcha ainda nao verificado. Complete o puzzle e tente de novo.",
                    "captcha_url": url,
                    "needs_captcha": True,
                }), 400

        # Try signin with the captcha token
        return do_signin(username, password, captcha_token)

    # method == 'password' - Step 1
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({"error": "Email e senha obrigatorios"}), 400

    # Get captcha token
    captcha_token, url = captcha_init_for_login(username)

    if url:
        # Need visual captcha - extract token from URL and store for retry
        parsed = parse_qs(urlparse(url).query)
        ct_from_url = parsed.get('captcha_token', [''])[0]
        if ct_from_url:
            captcha_token = ct_from_url

        pending_captcha[username] = {
            'captcha_token': captcha_token,
            'url': url,
        }

        return jsonify({
            "needs_captcha": True,
            "captcha_url": url,
            "message": "Complete o captcha no link abaixo, depois clique 'Ja verifiquei'",
        })

    # No captcha needed, proceed directly
    return do_signin(username, password, captcha_token)


def do_signin(username, password, captcha_token):
    signin_body = {
        "captcha_token": captcha_token or "",
        "client_id": WEB_CLIENT_ID,
        "client_secret": WEB_CLIENT_SECRET,
        "username": username,
        "password": password,
    }
    r = req_lib.post(
        f"{API_USER}/v1/auth/signin",
        json=signin_body,
        params={"client_id": WEB_CLIENT_ID},
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Device-ID": DEVICE_ID,
            "X-Captcha-Token": captcha_token or "",
        }
    )

    if r.status_code != 200:
        err_data = r.json() if 'application/json' in r.headers.get('content-type', '') else {}
        err_desc = err_data.get('error_description') or err_data.get('error') or f"HTTP {r.status_code}"

        # If captcha error, try getting a new captcha
        if err_data.get('error_code') == 9 or 'captcha' in str(err_desc).lower():
            captcha_token2, url2 = captcha_init_for_login(username)
            if url2:
                parsed = parse_qs(urlparse(url2).query)
                ct2 = parsed.get('captcha_token', [''])[0]
                pending_captcha[username] = {'captcha_token': ct2 or captcha_token2, 'url': url2}
                return jsonify({
                    "needs_captcha": True,
                    "captcha_url": url2,
                    "message": "Captcha necessario. Complete e clique 'Ja verifiquei'",
                })
            return jsonify({"error": f"{err_desc} - Use o metodo Access Token"}), 400

        return jsonify({"error": str(err_desc)}), 400

    resp = r.json()
    tokens = load_tokens()
    tokens['access_token'] = resp.get('access_token', '')
    tokens['refresh_token'] = resp.get('refresh_token', '')
    tokens['user_id'] = resp.get('sub', '')
    tokens['username'] = username
    save_tokens(tokens)

    # Clear pending captcha
    pending_captcha.pop(username, None)

    return jsonify({"success": True, "message": "Login OK!", "auto_login": False})



@app.route('/api/force-token', methods=['POST'])
def force_token():
    """Save token without validation - for when /about endpoint rejects but file endpoints work"""
    data = request.json
    access_token = data.get('access_token', '').strip()
    if access_token.lower().startswith('bearer '):
        access_token = access_token[7:].strip()
    access_token = access_token.strip('"').strip("'").strip()

    tokens = load_tokens()
    tokens['access_token'] = access_token
    save_tokens(tokens)
    return jsonify({"success": True, "message": "Token salvo! Testando ao listar arquivos..."})

@app.route('/api/auto-login', methods=['POST'])
def auto_login():
    tokens = load_tokens()
    refresh_token = tokens.get('refresh_token')
    if not refresh_token:
        return jsonify({"error": "Nenhum refresh_token salvo"}), 401

    r = req_lib.post(
        f"{API_USER}/v1/auth/token",
        json={
            "client_id": WEB_CLIENT_ID,
            "client_secret": WEB_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        params={"client_id": WEB_CLIENT_ID},
        headers={"User-Agent": "", "X-Device-ID": DEVICE_ID}
    )

    if r.status_code != 200:
        return jsonify({"error": "Refresh token expirado"}), 401

    resp = r.json()
    if resp.get('error_code', 0) != 0:
        return jsonify({"error": resp.get('error_description', 'Erro')}), 401

    tokens['access_token'] = resp.get('access_token', '')
    tokens['refresh_token'] = resp.get('refresh_token', tokens.get('refresh_token', ''))
    tokens['user_id'] = resp.get('sub', tokens.get('user_id', ''))
    save_tokens(tokens)

    return jsonify({"success": True, "message": "Auto-login OK", "auto_login": True})


def get_headers():
    tokens = load_tokens()
    at = tokens.get('access_token', '')
    uid = tokens.get('user_id', '')
    # Get a captcha token for API actions
    ct, _ = captcha_init_for_action("GET:/drive/v1/files", uid)
    return {
        "Authorization": f"Bearer {at}",
        "User-Agent": "Mozilla/5.0",
        "X-Device-ID": DEVICE_ID,
        "X-Captcha-Token": ct,
    }

def refresh_if_needed(r):
    if r.status_code in (401, 403):
        tokens = load_tokens()
        rt = tokens.get('refresh_token')
        if rt:
            rr = req_lib.post(
                f"{API_USER}/v1/auth/token",
                json={
                    "client_id": WEB_CLIENT_ID,
                    "client_secret": WEB_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": rt,
                },
                params={"client_id": WEB_CLIENT_ID},
                headers={"User-Agent": "", "X-Device-ID": DEVICE_ID}
            )
            if rr.status_code == 200:
                resp = rr.json()
                if resp.get('error_code', 0) == 0:
                    tokens['access_token'] = resp.get('access_token', '')
                    tokens['refresh_token'] = resp.get('refresh_token', rt)
                    save_tokens(tokens)
                    return get_headers()
    return None

# ======================== Cloud Browse Routes ========================
@app.route('/api/files', methods=['GET'])
def list_files():
    parent_id = request.args.get('parent_id', '')
    page_token = request.args.get('page_token', '')

    params = {
        "parent_id": parent_id,
        "thumbnail_size": "SIZE_LARGE",
        "with_audit": "true",
        "limit": "100",
        "filters": json.dumps({"phase": {"eq": "PHASE_TYPE_COMPLETE"}, "trashed": {"eq": False}}),
    }
    if page_token:
        params["page_token"] = page_token

    headers = get_headers()
    r = req_lib.get(f"{API_DRIVE}/drive/v1/files", params=params, headers=headers)

    if r.status_code in (401, 403):
        new_h = refresh_if_needed(r)
        if new_h:
            r = req_lib.get(f"{API_DRIVE}/drive/v1/files", params=params, headers=new_h)

    if r.status_code != 200:
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code

    return jsonify(r.json())

@app.route('/api/file-link', methods=['GET'])
def get_file_link():
    file_id = request.args.get('file_id', '')
    headers = get_headers()
    r = req_lib.get(f"{API_DRIVE}/drive/v1/files/{file_id}", params={"thumbnail_size": "SIZE_LARGE"}, headers=headers)

    if r.status_code in (401, 403):
        new_h = refresh_if_needed(r)
        if new_h:
            r = req_lib.get(f"{API_DRIVE}/drive/v1/files/{file_id}", params={"thumbnail_size": "SIZE_LARGE"}, headers=new_h)

    if r.status_code != 200:
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code

    data = r.json()
    links = []
    for m in data.get('medias', []):
        link = m.get('link', {})
        if link.get('url'):
            links.append({"url": link['url'], "type": m.get('media_name', ''), "expires": link.get('expire_time', '')})

    web_link = data.get('web_content_link', '')
    if web_link and not links:
        links.append({"url": web_link, "type": "web_content_link"})

    return jsonify({"name": data.get('name', ''), "links": links})

# ======================== Share Link Routes ========================
@app.route('/api/list', methods=['POST'])
def list_share():
    data = request.json
    share_url = data.get('url', '')

    m = re.search(r'/s/([^/?#]+)', share_url)
    if not m:
        return jsonify({"error": "URL invalida"}), 400
    share_id = m.group(1)

    pass_code = data.get('pass_code', '')
    parent_id = data.get('parent_id', '')

    headers = {"X-Device-ID": DEVICE_ID, "X-Client-ID": WEB_CLIENT_ID, "X-Client-Version": WEB_CLIENT_VERSION}

    all_files = []
    page_token = ""
    first_request = True

    while True:
        params = {"share_id": share_id, "limit": "100", "thumbnail_size": "SIZE_LARGE"}
        if parent_id:
            params["parent_id"] = parent_id
        if pass_code:
            params["pass_code_token"] = pass_code
        if page_token:
            params["page_token"] = page_token

        r = req_lib.get(f"{API_DRIVE}/drive/v1/share/detail", params=params, headers=headers)
        if r.status_code != 200:
            err_msg = "Erro ao acessar link"
            try:
                err_msg = r.json().get("error_description") or r.json().get("error") or err_msg
            except:
                pass
            return jsonify({"error": f"HTTP {r.status_code}: {err_msg}"}), r.status_code

        resp = r.json()

        if first_request:
            first_request = False
            file_info = resp.get('file_info')
            if file_info:
                kind = file_info.get('kind', '')
                if kind == 'drive#folder':
                    # It's a folder — set parent_id and re-fetch to list children
                    parent_id = file_info.get('id', '')
                    continue
                else:
                    # It's a single file — return it directly
                    result_file = {
                        "id": file_info.get("id", ""),
                        "name": file_info.get("name", ""),
                        "kind": kind,
                        "size": int(file_info.get("size", 0) or 0),
                        "mime_type": file_info.get("mime_type", ""),
                        "single_file": True,
                    }
                    return jsonify({"files": [result_file], "share_id": share_id, "single_file": True})

        files = resp.get('files', [])
        if not files:
            break
        all_files.extend(files)
        page_token = resp.get('next_page_token', '')
        if not page_token:
            break

    result = []
    for f in all_files:
        result.append({
            "id": f.get("id", ""),
            "name": f.get("name", ""),
            "kind": f.get("kind", ""),
            "size": int(f.get("size", 0) or 0),
            "mime_type": f.get("mime_type", ""),
        })

    return jsonify({"files": result, "share_id": share_id})

@app.route('/api/links', methods=['POST'])
def get_share_links():
    data = request.json
    share_id = data.get('share_id', '')
    file_ids = data.get('file_ids', [])
    pass_code = data.get('pass_code', '')

    results = []
    for fid in file_ids:
        params = {"share_id": share_id, "file_id": fid, "thumbnail_size": "SIZE_LARGE"}
        if pass_code:
            params["pass_code_token"] = pass_code

        r = req_lib.get(
            f"{API_DRIVE}/drive/v1/share/file_info",
            params=params,
            headers={"X-Device-ID": DEVICE_ID, "X-Client-ID": WEB_CLIENT_ID, "X-Client-Version": WEB_CLIENT_VERSION}
        )

        if r.status_code == 200:
            fi = r.json().get('file_info', r.json())
            links = []
            for m in fi.get('medias', []):
                link = m.get('link', {})
                if link.get('url'):
                    links.append(link['url'])
            wcl = fi.get('web_content_link', '')
            if wcl and not links:
                links.append(wcl)
            results.append({"id": fid, "name": fi.get("name", ""), "links": links})
        else:
            results.append({"id": fid, "name": "", "links": [], "error": f"HTTP {r.status_code}"})

    return jsonify({"results": results})


@app.route('/api/fetch-text', methods=['POST'])
def fetch_text():
    """Proxy: download a URL and return its text content (for viewing .txt/magnet files)"""
    data = request.json
    url = data.get('url', '')
    if not url:
        return jsonify({"error": "URL vazia"}), 400
    try:
        r = req_lib.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}, stream=False)
        if r.status_code != 200:
            return jsonify({"error": f"HTTP {r.status_code}"}), 400
        # Limit to 512KB
        content = r.content[:524288].decode('utf-8', errors='replace')
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ======================== Dropbox Routes ========================
@app.route('/api/dropbox-test', methods=['POST'])
def dropbox_test():
    token = request.json.get('token', '')
    r = req_lib.post(
        "https://api.dropboxapi.com/2/users/get_current_account",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r.status_code == 200:
        d = r.json()
        return jsonify({"success": True, "name": d.get('name', {}).get('display_name', ''), "email": d.get('email', '')})
    return jsonify({"error": f"HTTP {r.status_code}: {r.text[:200]}"}), 400

@app.route('/api/dropbox-send', methods=['POST'])
def dropbox_send():
    data = request.json
    token = data.get('dropbox_token', '')
    file_url = data.get('file_url', '')
    file_name = data.get('file_name', '')
    folder = data.get('folder', '/PikPak')

    import tempfile

    r = req_lib.get(file_url, stream=True)
    if r.status_code != 200:
        return jsonify({"error": f"Download falhou: HTTP {r.status_code}"}), 400

    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        for chunk in r.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()

        file_size = os.path.getsize(tmp.name)
        path = f"{folder}/{file_name}"
        if file_size < 150 * 1024 * 1024:
            with open(tmp.name, 'rb') as f:
                rr = req_lib.post(
                    "https://content.dropboxapi.com/2/files/upload",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Dropbox-API-Arg": json.dumps({"path": path, "mode": "add", "autorename": True}),
                        "Content-Type": "application/octet-stream",
                    },
                    data=f
                )
            if rr.status_code == 200:
                return jsonify({"success": True, "path": rr.json().get('path_display', path)})
            return jsonify({"error": f"Upload Dropbox falhou: {rr.text[:300]}"}), 400
        else:
            return jsonify({"error": "Arquivo > 150MB. Use upload_session (nao implementado)."}), 400
    finally:
        os.unlink(tmp.name)



# ===================== Generic CORS Proxy =====================
@app.route('/api/proxy', methods=['POST'])
def cors_proxy():
    """Pass-through proxy: browser sends {url, method, headers, body} → we forward to PikPak → return response"""
    data = request.json
    url = data.get('url', '')
    method = data.get('method', 'GET').upper()
    headers = data.get('headers', {})
    body = data.get('body')

    if not url:
        return jsonify({"error": "URL vazia"}), 400

    # Security: only allow PikPak domains
    allowed = ['mypikpak.net', 'mypikpak.com', 'dropboxapi.com', 'dropbox.com']
    from urllib.parse import urlparse as _urlparse
    host = _urlparse(url).netloc.lower()
    if not any(a in host for a in allowed):
        return jsonify({"error": f"Domínio não permitido: {host}"}), 403

    # Remove hop-by-hop headers
    for h in ['host', 'content-length', 'transfer-encoding', 'connection']:
        headers.pop(h, None)
        headers.pop(h.title(), None)

    try:
        if method == 'GET':
            r = req_lib.get(url, headers=headers, timeout=30, stream=False)
        elif method == 'POST':
            if body and isinstance(body, str):
                r = req_lib.post(url, data=body.encode('utf-8'), headers=headers, timeout=30)
            elif body:
                r = req_lib.post(url, json=body, headers=headers, timeout=30)
            else:
                r = req_lib.post(url, headers=headers, timeout=30)
        else:
            r = req_lib.request(method, url, headers=headers, timeout=30)

        # Forward response
        try:
            resp_data = r.json()
            return jsonify(resp_data), r.status_code
        except Exception:
            return r.text, r.status_code, {'Content-Type': r.headers.get('Content-Type', 'text/plain')}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================== Main ========================
@app.route('/')
def index():
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v7_template.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>PikPak Cloud Manager v7</h1><p>Template v7_template.html nao encontrado.</p>"

if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  PikPak Cloud Manager v7 (Railway/Local)")
    print(f"  Device ID: {DEVICE_ID}")
    print(f"  Listening on port {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
