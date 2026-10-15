#!/usr/bin/env python3
"""
Pesto Player Wi-Fi uploader: a tiny LAN web page for adding songs from a phone.

Runs as its own process/unit (pesto-uploader.service) so uploads never share the
UI's memory. Safety rules (this is LAN-facing):
- Every request needs the per-session token (random, regenerated at each start,
  written 0600 to <state_dir>/uploader.json so the on-device Add-music screen can
  show it in a QR code). POSTs accept it ONLY in the X-Pesto-Token header, which a
  cross-site form cannot set.
- Filenames are reduced to a safe basename (no separators, no leading dots, no
  control chars) and must end in an allowed audio extension (case-insensitive).
- Files are streamed to <music>/.incoming/*.part and renamed into <music>/ only
  after the whole file arrived and passed checks, so a half-written file is never
  visible to the library scanner (which skips hidden dirs and non-audio names).
- Nothing is ever written or deleted outside <music>; existing files are never
  overwritten.
- Uploads are refused when free space would drop below PESTO_MIN_FREE_MB.

Environment (all optional): PESTO_MUSIC_DIR (~/Music), PESTO_STATE_DIR (~/.pesto),
PESTO_UPLOAD_PORT (8080), PESTO_UPLOAD_HOST (0.0.0.0), PESTO_MIN_FREE_MB (200),
PESTO_MAX_UPLOAD_MB (1024 per request), PESTO_TOKEN (tests only).
"""

import hmac
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import unicodedata

from flask import Flask, Request, jsonify, make_response, request

# Keep in sync with app/config.py SUPPORTED_FORMATS (test_server.py checks this).
ALLOWED_EXTENSIONS = (".mp3", ".flac", ".m4a", ".ogg", ".wav", ".opus")
_BAD_CHARS = re.compile(r"[^\w\-. ()&',]", re.UNICODE)


def safe_name(filename):
    """Return a safe basename or None if nothing usable / extension not allowed."""
    if not filename:
        return None
    name = unicodedata.normalize("NFC", str(filename))
    name = re.split(r"[\\/]", name)[-1]          # basename for both separators
    name = "".join(c for c in name if c.isprintable())
    name = _BAD_CHARS.sub("_", name).strip(" .")
    name = re.sub(r"\s+", " ", name)
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS or not stem.strip(" ._"):
        return None
    if len(stem) > 120:
        stem = stem[:120].rstrip(" .")
    return stem + ext


def _free_bytes(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def create_app(music_dir=None, state_dir=None, token=None, min_free_mb=None,
               max_upload_mb=None, port=None):
    music = os.path.abspath(os.path.expanduser(
        music_dir or os.environ.get("PESTO_MUSIC_DIR", "~/Music")))
    state = os.path.abspath(os.path.expanduser(
        state_dir or os.environ.get("PESTO_STATE_DIR", "~/.pesto")))
    incoming = os.path.join(music, ".incoming")
    min_free = int((min_free_mb if min_free_mb is not None
                    else os.environ.get("PESTO_MIN_FREE_MB", 200)) * 1024 * 1024)
    max_upload = int((max_upload_mb if max_upload_mb is not None
                      else os.environ.get("PESTO_MAX_UPLOAD_MB", 1024)) * 1024 * 1024)
    port = int(port or os.environ.get("PESTO_UPLOAD_PORT", 8080))
    token = token or os.environ.get("PESTO_TOKEN") or secrets.token_urlsafe(16)

    os.makedirs(incoming, exist_ok=True)
    os.makedirs(state, exist_ok=True)
    for fn in os.listdir(incoming):                    # stale partials from a crash
        if fn.endswith(".part"):
            try:
                os.remove(os.path.join(incoming, fn))
            except OSError:
                pass
    info_path = os.path.join(state, "uploader.json")
    fd = os.open(info_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"token": token, "port": port}, f)

    class SpoolRequest(Request):
        # Spool large multipart parts into .incoming (disk) rather than RAM/tmp.
        def _get_file_stream(self, total_content_length, content_type,
                             filename=None, content_length=None):
            return tempfile.NamedTemporaryFile(dir=incoming, suffix=".part")

    app = Flask(__name__)
    app.request_class = SpoolRequest
    app.config["MAX_CONTENT_LENGTH"] = max_upload
    app.config["PESTO_TOKEN"] = token
    app.config["PESTO_MUSIC"] = music
    lock = threading.Lock()

    def mark_dirty():
        try:
            with open(os.path.join(state, "library.dirty"), "a"):
                pass
            os.utime(os.path.join(state, "library.dirty"), None)
        except OSError:
            pass

    def authorised(post):
        supplied = request.headers.get("X-Pesto-Token")
        if supplied is None and not post:
            supplied = request.args.get("t")
        return bool(supplied) and hmac.compare_digest(str(supplied), token)

    @app.before_request
    def gate():
        if not authorised(request.method == "POST"):
            return make_response("Forbidden: missing or wrong token. Rescan the QR code "
                                 "on the player.\n", 403)

    @app.after_request
    def headers(resp):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:")
        return resp

    def list_files():
        out = []
        try:
            for fn in sorted(os.listdir(music), key=str.casefold):
                p = os.path.join(music, fn)
                if (not fn.startswith(".") and fn.lower().endswith(ALLOWED_EXTENSIONS)
                        and os.path.isfile(p)):
                    out.append({"name": fn, "size": os.path.getsize(p)})
        except OSError:
            pass
        return out

    @app.get("/")
    def index():
        page = PAGE.replace("__TOKEN__", json.dumps(token).replace("</", "<\\/"))
        page = page.replace("__EXTS__", ",".join(ALLOWED_EXTENSIONS))
        return page

    @app.get("/status")
    def status():
        return jsonify(free=_free_bytes(music), min_free=min_free, files=len(list_files()))

    @app.get("/files")
    def files():
        return jsonify(files=list_files(), free=_free_bytes(music))

    @app.post("/upload")
    def upload():
        clen = request.content_length or 0
        if clen and _free_bytes(music) - clen < min_free:
            return jsonify(error="Not enough free space on the player.", results=[]), 507
        results, saved = [], 0
        for up in request.files.getlist("files"):
            orig = up.filename or ""
            name = safe_name(orig)
            if name is None:
                results.append({"name": orig, "ok": False,
                                "error": "Not an allowed audio file (" +
                                         ", ".join(ALLOWED_EXTENSIONS) + ")"})
                continue
            part = os.path.join(incoming, secrets.token_hex(8) + ".part")
            dest = os.path.join(music, name)
            try:
                up.save(part)
                size = os.path.getsize(part)
                if size == 0:
                    raise ValueError("Empty file")
                if _free_bytes(music) - 0 < min_free:
                    raise OSError("Not enough free space on the player.")
                with lock:
                    if os.path.exists(dest):
                        raise FileExistsError("Already on the player")
                    os.replace(part, dest)
                saved += 1
                results.append({"name": name, "ok": True, "size": size})
            except FileExistsError as e:
                results.append({"name": name, "ok": False, "error": str(e)})
            except (OSError, ValueError) as e:
                results.append({"name": name, "ok": False, "error": str(e) or "Write failed"})
            finally:
                if os.path.exists(part):
                    try:
                        os.remove(part)
                    except OSError:
                        pass
        if saved:
            mark_dirty()
        return jsonify(saved=saved, results=results)

    @app.post("/delete")
    def delete():
        data = request.get_json(silent=True) or {}
        name = safe_name(data.get("name"))
        if name is None or name != data.get("name"):
            return jsonify(ok=False, error="Bad name"), 400
        p = os.path.join(music, name)
        if os.path.dirname(os.path.realpath(p)) != os.path.realpath(music) or not os.path.isfile(p):
            return jsonify(ok=False, error="Not found"), 404
        try:
            os.remove(p)
        except OSError as e:
            return jsonify(ok=False, error=str(e)), 500
        mark_dirty()
        return jsonify(ok=True)

    @app.errorhandler(413)
    def too_big(_e):
        return jsonify(error="Upload too large.", results=[]), 413

    return app


PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Add music to Pesto</title><style>
body{font:16px system-ui,sans-serif;background:#121212;color:#fff;margin:0;padding:16px;max-width:560px;margin:auto}
h1{font-size:20px}button,label.b{background:#8a2be2;color:#fff;border:0;border-radius:8px;padding:14px 18px;font-size:16px;display:inline-block}
button:disabled{opacity:.5}input[type=file]{display:none}li{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #333;word-break:break-all}
li button{background:#444;padding:6px 10px;font-size:14px}.ok{color:#2ed573}.err{color:#eb4d4b}#bar{height:6px;background:#333;border-radius:3px;margin:12px 0}
#fill{height:6px;background:#8a2be2;border-radius:3px;width:0}small{color:#aaa}</style></head><body>
<h1>Add music to Pesto</h1><p><small id=free></small></p>
<label class=b for=f>Choose songs</label><input id=f type=file multiple accept="__EXTS__,audio/*">
<button id=go disabled>Upload</button><div id=bar><div id=fill></div></div><div id=msg></div>
<h2>On the player</h2><ul id=list></ul>
<script>
const T=__TOKEN__,H={"X-Pesto-Token":T};
const $=i=>document.getElementById(i);
const fmt=n=>n>=1e9?(n/1e9).toFixed(1)+" GB":n>=1e6?(n/1e6).toFixed(1)+" MB":Math.round(n/1e3)+" KB";
function say(t,c){const d=document.createElement("div");d.textContent=t;d.className=c||"";$("msg").prepend(d)}
async function refresh(){try{const r=await fetch("/files",{headers:H});const j=await r.json();
$("free").textContent="Free space: "+fmt(j.free);const ul=$("list");ul.textContent="";
j.files.forEach(f=>{const li=document.createElement("li");const s=document.createElement("span");
s.textContent=f.name+" ("+fmt(f.size)+")";const b=document.createElement("button");b.textContent="Delete";
b.onclick=async()=>{if(!confirm("Delete "+f.name+" from the player?"))return;
await fetch("/delete",{method:"POST",headers:{...H,"Content-Type":"application/json"},body:JSON.stringify({name:f.name})});refresh()};
li.append(s,b);ul.append(li)})}catch(e){say("Can't reach the player","err")}}
$("f").onchange=()=>{$("go").disabled=!$("f").files.length;say($("f").files.length+" file(s) selected")};
$("go").onclick=()=>{const fd=new FormData();for(const f of $("f").files)fd.append("files",f);
const x=new XMLHttpRequest();x.open("POST","/upload");x.setRequestHeader("X-Pesto-Token",T);
x.upload.onprogress=e=>{if(e.lengthComputable)$("fill").style.width=(100*e.loaded/e.total)+"%"};
x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){}
(j.results||[]).forEach(r=>say(r.ok?"Added "+r.name:r.name+": "+r.error,r.ok?"ok":"err"));
if(j.error)say(j.error,"err");$("fill").style.width="0";$("f").value="";$("go").disabled=true;refresh()};
x.onerror=()=>{say("Upload interrupted - nothing partial was kept. Try again.","err");$("go").disabled=false};
$("go").disabled=true;x.send(fd)};
refresh();
</script></body></html>"""


def main():
    from werkzeug.serving import run_simple
    app = create_app()
    host = os.environ.get("PESTO_UPLOAD_HOST", "0.0.0.0")
    port = int(os.environ.get("PESTO_UPLOAD_PORT", 8080))
    print(f"Pesto uploader on {host}:{port}, music dir {app.config['PESTO_MUSIC']}")
    run_simple(host, port, app, threaded=True)


if __name__ == "__main__":
    main()
