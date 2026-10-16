import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import server  # noqa: E402

TOKEN = "tok123"
H = {"X-Pesto-Token": TOKEN}


@pytest.fixture
def env(tmp_path):
    music, state = tmp_path / "Music", tmp_path / "state"
    app = server.create_app(str(music), str(state), token=TOKEN, min_free_mb=0, port=8080)
    return app.test_client(), music, state


def up(client, name, data=b"abc", headers=H):
    return client.post("/upload", headers=headers, content_type="multipart/form-data",
                       data={"files": (io.BytesIO(data), name)})


def test_allowed_extensions_match_app_config():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))
    import config
    assert tuple(sorted(e.lower() for e in config.SUPPORTED_FORMATS)) == tuple(
        sorted(server.ALLOWED_EXTENSIONS))


def test_requires_token_everywhere(env):
    c, music, _ = env
    assert c.get("/").status_code == 403
    assert c.get("/?t=wrong").status_code == 403
    assert c.get("/files").status_code == 403
    assert c.post("/upload").status_code == 403
    assert up(c, "a.mp3", headers={"X-Pesto-Token": "nope"}).status_code == 403
    assert up(c, "a.mp3", headers={}).status_code == 403
    assert c.post("/upload?t=" + TOKEN).status_code == 403   # POST needs the header
    assert not (music / "a.mp3").exists()


def test_page_and_status_with_token(env):
    c, _, _ = env
    r = c.get("/?t=" + TOKEN)
    assert r.status_code == 200 and b"Add music" in r.data and TOKEN.encode() in r.data
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert c.get("/status", headers=H).json["files"] == 0


def test_upload_ok_and_dirty_flag(env):
    c, music, state = env
    r = up(c, "Song One.MP3")
    assert r.json["saved"] == 1 and r.json["results"][0]["ok"]
    assert (music / "Song One.mp3").read_bytes() == b"abc"
    assert (state / "library.dirty").exists()
    assert os.listdir(music / ".incoming") == []          # no partials left behind
    assert [f["name"] for f in c.get("/files", headers=H).json["files"]] == ["Song One.mp3"]


def test_rejects_bad_extensions(env):
    c, music, state = env
    for bad in ("evil.exe", "a.txt", "noext", "x.mp3.sh", ".mp3", "a.php"):
        r = up(c, bad)
        assert r.json["saved"] == 0 and not r.json["results"][0]["ok"], bad
    assert [p for p in os.listdir(music) if not p.startswith(".")] == []
    assert not (state / "library.dirty").exists()


@pytest.mark.parametrize("name", ["../../etc/passwd.mp3", "..\\..\\x.mp3",
                                  "/abs/path/x.mp3", "a/b/../../../c.mp3", "..mp3.mp3"])
def test_path_traversal_names_stay_inside_music(env, name, tmp_path):
    c, music, _ = env
    r = up(c, name)
    for p in tmp_path.rglob("*.mp3"):
        assert str(p).startswith(str(music) + os.sep), p
        assert os.path.dirname(str(p)) == str(music)
    assert not (tmp_path / "x.mp3").exists() and not (tmp_path / "c.mp3").exists()


def test_duplicate_not_overwritten(env):
    c, music, _ = env
    up(c, "dup.mp3", b"first")
    r = up(c, "dup.mp3", b"second")
    assert r.json["saved"] == 0 and "Already" in r.json["results"][0]["error"]
    assert (music / "dup.mp3").read_bytes() == b"first"


def test_empty_file_rejected(env):
    c, music, _ = env
    assert up(c, "e.mp3", b"").json["saved"] == 0
    assert not (music / "e.mp3").exists()


def test_low_disk_space_refused(tmp_path, monkeypatch):
    app = server.create_app(str(tmp_path / "M"), str(tmp_path / "S"), token=TOKEN, min_free_mb=200)
    monkeypatch.setattr(server, "_free_bytes", lambda p: 10 * 1024 * 1024)
    c = app.test_client()
    r = up(c, "big.mp3")
    assert r.status_code == 507 and "space" in r.json["error"]
    assert not (tmp_path / "M" / "big.mp3").exists()


def test_oversize_request_rejected(tmp_path):
    app = server.create_app(str(tmp_path / "M"), str(tmp_path / "S"), token=TOKEN,
                            min_free_mb=0, max_upload_mb=1)
    r = up(app.test_client(), "big.mp3", b"x" * (2 * 1024 * 1024))
    assert r.status_code == 413
    assert os.listdir(tmp_path / "M" / ".incoming") == []


def test_stale_part_files_cleaned_at_start(tmp_path):
    inc = tmp_path / "M" / ".incoming"
    inc.mkdir(parents=True)
    (inc / "old.part").write_bytes(b"x")
    (inc / "keep.txt").write_bytes(b"x")
    server.create_app(str(tmp_path / "M"), str(tmp_path / "S"), token=TOKEN)
    assert sorted(os.listdir(inc)) == ["keep.txt"]


def test_token_file_private_and_unicode_names(env):
    c, music, state = env
    assert oct(os.stat(state / "uploader.json").st_mode & 0o777) == "0o600"
    assert up(c, "Ünï Sóng 日本.flac").json["saved"] == 1
    assert (music / "Ünï Sóng 日本.flac").exists()


def test_delete_only_audio_files_in_music_root(env, tmp_path):
    c, music, state = env
    up(c, "gone.mp3")
    (music / "note.txt").write_text("keep")
    outside = tmp_path / "secret.mp3"
    outside.write_text("x")

    def delete(name, hdr=H):
        return c.post("/delete", headers=hdr, json={"name": name})

    assert delete("gone.mp3", {}).status_code == 403
    assert delete("note.txt").status_code == 400
    assert delete("../secret.mp3").status_code == 400
    assert outside.exists() and (music / "note.txt").exists()
    (state / "library.dirty").unlink()
    assert delete("gone.mp3").json["ok"]
    assert not (music / "gone.mp3").exists() and (state / "library.dirty").exists()
    assert delete("gone.mp3").status_code == 404


def test_safe_name_unit():
    assert server.safe_name("a/b\\c.MP3") == "c.mp3"
    assert server.safe_name("..") is None and server.safe_name(None) is None
    assert server.safe_name("x\x00y.mp3") == "xy.mp3"
    assert server.safe_name("a" * 300 + ".mp3").endswith(".mp3")


def test_non_ascii_token_gets_403_not_500(env):
    c, _, _ = env
    assert c.get("/?t=%E2%82%AC%E2%82%AC").status_code == 403
    assert c.get("/files", headers={"X-Pesto-Token": "café"}).status_code == 403
    assert c.get("/?t=%ED%A0%80").status_code == 403


def test_name_limited_to_255_bytes_keeping_extension():
    n = server.safe_name("日" * 200 + ".FLAC")
    assert n.endswith(".flac") and len(n.encode("utf-8")) <= 255
    n.encode("utf-8")
    assert len(server.safe_name("a" * 400 + ".mp3").encode()) == 255


def test_access_log_redacts_token():
    import logging
    server.create_app.__globals__  # module loaded
    rec = logging.LogRecord("werkzeug", logging.INFO, "", 0,
                            '%s - - [x] "GET /?t=SECRETtok&x=1 HTTP/1.1" 200 -', ("1.2.3.4",), None)
    assert server._RedactToken().filter(rec)
    assert "SECRETtok" not in rec.getMessage() and "t=REDACTED&x=1" in rec.getMessage()


def test_upload_streams_once_and_leaves_no_parts_on_rejection(env):
    c, music, _ = env
    up(c, "ok.mp3", b"x" * 1000)
    up(c, "bad.exe", b"x" * 1000)
    assert os.listdir(music / ".incoming") == []
    assert (music / "ok.mp3").stat().st_size == 1000


def test_missing_content_length_rejected(env):
    c, music, _ = env
    r = c.post("/upload", headers={**H, "Transfer-Encoding": "chunked"},
               input_stream=io.BytesIO(b""), content_type="multipart/form-data; boundary=x")
    assert r.status_code in (411, 400)


def test_token_required_regardless_of_client_network(env):
    """Tailscale clients (100.64.0.0/10) get no special trust: the token is still required."""
    client, _, _ = env
    for path in ("/", "/files", "/status"):
        assert client.get(path, environ_overrides={"REMOTE_ADDR": "100.101.102.103"}).status_code == 403
    r = client.get("/files", headers=H, environ_overrides={"REMOTE_ADDR": "100.101.102.103"})
    assert r.status_code == 200


def test_default_bind_is_all_interfaces():
    """0.0.0.0 covers wlan0 and tailscale0; changing it would break remote upload."""
    assert os.environ.get("PESTO_UPLOAD_HOST", "0.0.0.0") == "0.0.0.0"
