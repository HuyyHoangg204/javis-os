"""Sức khoẻ kết nối - vòng check nền cho trang Kết nối.

Mỗi HEALTH_INTERVAL giây, ping từng connection đang bật bằng tools/list qua session
pool (rẻ, không gọi tool thật, không tốn quota dịch vụ). Kết quả giữ IN-MEMORY:
sau restart quét lại sớm (delay ngắn) thay vì persist - trạng thái sống mới có giá trị.

Lỗi được PHÂN LOẠI SANG TIẾNG NGƯỜI ngay tại server (classify_error) để UI chỉ việc
hiển thị, và để nhóm `auth` (hết phiên đăng nhập) kích hoạt nút "Kết nối lại" một chạm.
Bài học vụ 0.9.189: thông điệp lỗi mù mờ làm cả agent lẫn người dùng chẩn đoán sai -
nói thẳng nguyên nhân là một tính năng, không phải trang trí.
"""
import asyncio
import sys
import time

import mcp_client
import mcp_store

HEALTH_INTERVAL = 600     # giây giữa hai vòng quét
_STARTUP_DELAY = 25       # chờ server ổn định rồi mới quét vòng đầu
_CHECK_TIMEOUT = 60       # trần một lần ping (stdio spawn nguội trên Windows có thể chậm)

_state: dict = {}         # conn_id -> {ok, kind, message, checked_at, tools}
_task = None


# Thứ tự các nhánh CÓ Ý NGHĨA: auth soi trước (chuỗi 401/unauthorized đặc trưng),
# spawn trước net (lỗi spawn stdio hay kèm chữ chung chung như "connection closed").
_AUTH_HINTS = ("401", "unauthorized", "invalid_grant", "oauth session expired",
               "token expired", "invalid token", "invalid_token", "authentication",
               "hết phiên đăng nhập")
_SPAWN_HINTS = ("filenotfounderror", "no such file", "not recognized", "enoent",
                "spawn", "exited with", "exit code", "notimplementederror")
_NET_HINTS = ("timeout", "timed out", "getaddrinfo", "connection refused",
              "connecterror", "connectionerror", "ssl", "network", "unreachable",
              "connection closed", "server disconnected", "502", "503", "504")


def classify_error(err: str) -> tuple[str, str]:
    """Chuỗi lỗi kỹ thuật -> (kind, thông điệp tiếng người).

    kind: auth | spawn | net | unknown. Nhóm `auth` là nhóm duy nhất UI gắn hành động
    (nút Kết nối lại) nên thà bỏ sót (rơi vào unknown) còn hơn bắt nhầm."""
    low = (err or "").lower()
    if any(s in low for s in _AUTH_HINTS):
        return "auth", "Hết phiên đăng nhập - bấm Kết nối lại để đăng nhập lại."
    if any(s in low for s in _SPAWN_HINTS):
        return "spawn", "Không khởi động được trình kết nối trên máy chạy Javis."
    if any(s in low for s in _NET_HINTS):
        return "net", "Dịch vụ không phản hồi - có thể do mạng hoặc máy chủ dịch vụ."
    return "unknown", (err or "Lỗi không rõ").strip()[:160]


async def check_one(conn, pool=None) -> dict:
    """Ping MỘT connection, cập nhật _state và trả bản ghi kết quả."""
    pool = pool or mcp_client.pool
    rec = {"ok": False, "kind": "", "message": "", "checked_at": time.time(), "tools": 0}
    # Connection OAuth CHƯA TỪNG có token (đăng nhập bỏ dở giữa chừng) → đỏ với lý do
    # thật, khỏi dial cho tốn công. Soi TRƯỚC nhánh connector ảo: meta-ads-graph/facebook-
    # pages cũng là oauth ảo, chưa đăng nhập mà báo xanh là nói dối.
    if (conn.get("auth") == "oauth"):
        try:
            import oauth_mcp
            if not oauth_mcp.status(conn["id"]).get("connected"):
                rec.update(kind="auth",
                           message="Chưa hoàn tất đăng nhập - bấm Kết nối lại để đăng nhập.")
                _state[conn["id"]] = rec
                return rec
        except Exception:
            pass
    # Connector ẢO (không URL, không command): tool do plugin phục vụ (vd Meta Ads Graph),
    # không có server nào để dial - coi là sống, khỏi báo đỏ oan.
    if not (conn.get("url") or "").strip() and not (conn.get("command") or "").strip():
        rec["ok"] = True
        _state[conn["id"]] = rec
        return rec
    spec = mcp_client._conn_spec(conn)
    try:
        spec["headers"].update(await mcp_client._oauth_headers(conn))
        tools = await asyncio.wait_for(pool.list_tools(spec), timeout=_CHECK_TIMEOUT)
        rec.update(ok=True, tools=len(tools))
    except Exception as e:
        kind, msg = classify_error(f"{type(e).__name__}: {e}")
        rec.update(kind=kind, message=msg)
    _state[conn["id"]] = rec
    return rec


async def check_by_id(conn_id, pool=None) -> dict:
    """Ép check ngay một connection theo id (nút test trên UI)."""
    conn = next((c for c in mcp_store.resolved(enabled_only=False)
                 if c["id"] == conn_id), None)
    if not conn:
        return {"ok": False, "kind": "unknown", "message": "Không tìm thấy kết nối",
                "checked_at": time.time(), "tools": 0}
    return await check_one(conn, pool)


async def sweep(pool=None) -> int:
    """Quét mọi connection đang bật. Trả số connection đã check."""
    n = 0
    for conn in mcp_store.resolved(enabled_only=True):
        try:
            await check_one(conn, pool)
            n += 1
        except Exception as e:   # lỗi 1 connection không được giết cả vòng
            print(f"[connect health] {conn.get('label')}: {type(e).__name__}: {e}",
                  file=sys.stderr)
    return n


def snapshot() -> dict:
    """Trạng thái hiện có cho GET /connect/health. Connection chưa check thì vắng mặt
    (UI hiểu là 'chưa rõ' - chấm vàng)."""
    return {cid: dict(rec) for cid, rec in _state.items()}


def forget(conn_id) -> None:
    """Xoá trạng thái khi connection bị xoá (khỏi hiện ma)."""
    _state.pop(conn_id, None)


# ─────────────── Đèn báo não (engine health) ───────────────
# Não chết thì chính não KHÔNG tự báo được (mọi thông báo thông minh đều đi qua engine),
# nên tín hiệu phải do server tự thắp: (1) probe hạn token định kỳ trong sweep,
# (2) cờ phản ứng khi một lượt chạy engine trả lỗi đăng nhập (flag_engine_auth_error).

_engines: dict = {}       # name -> {ok, message, source, ts, notified}
on_engine_down = None     # main.py gắn: async fn(text) gửi Telegram MỘT lần khi não chuyển chết

# Mẫu lỗi đăng nhập trong OUTPUT một lượt chạy engine (vụ 2026-07-27: Claude CLI hết phiên,
# mọi task trả "Failed to authenticate: OAuth session expired and could not be refreshed").
_ENGINE_AUTH_PATTERNS = ("failed to authenticate", "oauth session expired",
                         "oauth token has expired", "please run /login",
                         "api key not found", "not logged in", "invalid api key")

ENGINE_FIX = {
    "claude": "Mở terminal chạy claude rồi gõ /login để đăng nhập lại.",
    "codex": "Vào trang Models bấm kết nối lại ChatGPT, hoặc chạy codex login trong terminal.",
}


def _set_engine(name, ok, message="", source="probe"):
    prev = _engines.get(name) or {}
    rec = {"ok": ok, "message": message, "source": source, "ts": time.time(),
           "notified": bool(prev.get("notified"))}
    if ok:
        rec["notified"] = False   # hồi sinh → lần chết sau lại được báo
    _engines[name] = rec
    if not ok and not rec["notified"] and on_engine_down:
        rec["notified"] = True
        try:
            coro = on_engine_down(f"⚠ Bộ não {name} của Javis đang mất đăng nhập: {message} "
                                  + ENGINE_FIX.get(name, ""))
            if asyncio.iscoroutine(coro):
                asyncio.ensure_future(coro)
        except Exception as e:
            print(f"[engine health] notify lỗi: {e}", file=sys.stderr)


def flag_engine_auth_error(name, raw) -> bool:
    """Gọi từ engine khi một lượt chạy kết thúc: text khớp mẫu lỗi đăng nhập thì bật đèn đỏ.
    Trả True nếu đã bật (caller khỏi phân tích lại)."""
    low = (raw or "").lower()
    if not any(p in low for p in _ENGINE_AUTH_PATTERNS):
        return False
    _set_engine(name, False, "Hết phiên đăng nhập (phát hiện khi chạy).", "run")
    return True


def engine_run_ok(name) -> None:
    """Một lượt chạy thành công → não sống, tắt đèn (rẻ, chỉ ghi khi đang đỏ)."""
    rec = _engines.get(name)
    if rec and not rec.get("ok"):
        _set_engine(name, True, "", "run")


def _mac_keychain_creds() -> tuple[dict | None, bool]:
    """macOS: Claude Code KHÔNG ghi ~/.claude/.credentials.json mà cất OAuth trong Keychain
    (generic password, service 'Claude Code-credentials'). Đọc CHỈ-ĐỌC qua CLI `security`.
    Trả (creds, known): known=False = KHÔNG XÁC ĐỊNH ĐƯỢC (security bị chặn/treo/JSON hỏng)
    - caller phải coi như não sống, thà bỏ sót còn hơn báo đỏ oan (vụ Mac 0.9.229: banner
    'mất đăng nhập' treo vĩnh viễn dù đã đăng nhập)."""
    import json as _json
    import subprocess
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5)
    except Exception:
        return None, False
    if r.returncode != 0:
        # errSecItemNotFound: keychain khẳng định KHÔNG có item → thật sự chưa đăng nhập.
        if "could not be found" in (r.stderr or "").lower():
            return None, True
        return None, False   # bị từ chối quyền / lỗi lạ → không kết luận
    try:
        return _json.loads(r.stdout.strip()), True
    except Exception:
        return None, False


def probe_claude_credentials(path=None) -> tuple[bool, str]:
    """Đọc hạn token Claude CLI (~/.claude/.credentials.json; macOS rơi về Keychain).
    CHỈ ĐỌC - tuyệt đối không tự refresh (tự refresh làm user bị đăng xuất, xem bài học cũ).
    Có refreshToken → CLI tự làm mới được, coi là sống dù access token đã quá hạn."""
    from pathlib import Path
    p = Path(path) if path else Path.home() / ".claude" / ".credentials.json"
    data = None
    try:
        import json as _json
        data = _json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if sys.platform == "darwin":
            creds, known = _mac_keychain_creds()
            if not known:
                return True, ""   # không xác định được → coi là sống; đèn do lượt chạy thật lo
            if not creds:
                return False, "Chưa đăng nhập Claude Code trên máy này."
            data = creds
        else:
            return False, "Chưa đăng nhập Claude Code trên máy này."
    except Exception:
        return False, "Không đọc được thông tin đăng nhập Claude Code."
    oa = (data or {}).get("claudeAiOauth") or {}
    if not oa:
        return False, "Chưa đăng nhập Claude Code trên máy này."
    if oa.get("refreshToken"):
        return True, ""
    exp = oa.get("expiresAt") or 0
    if exp / 1000 > time.time():
        return True, ""
    return False, "Phiên đăng nhập Claude Code đã hết hạn và không tự làm mới được."


def probe_engines() -> None:
    """Probe định kỳ (gọi trong sweep). Chỉ soi engine đang là Main Model để khỏi báo
    đỏ oan máy không dùng Claude. Đèn do lượt chạy bật (source=run) không bị probe đè
    sang xanh - lỗi lúc chạy là bằng chứng mạnh hơn suy đoán từ file token."""
    try:
        import config as _cfg
        provider = (((_cfg.read_settings().get("model") or {}).get("main") or {})
                    .get("provider") or "anthropic-cli")
    except Exception:
        provider = "anthropic-cli"
    if provider == "anthropic-cli":
        ok, msg = probe_claude_credentials()
        cur = _engines.get("claude") or {}
        if ok and cur.get("source") == "run" and not cur.get("ok"):
            return   # đèn đỏ do lượt chạy thật - chờ engine_run_ok tắt, probe không đè
        _set_engine("claude", ok, msg, "probe")


def engines_snapshot() -> dict:
    return {n: dict(r) for n, r in _engines.items()}


async def _loop():
    await asyncio.sleep(_STARTUP_DELAY)
    while True:
        try:
            probe_engines()
            await sweep()
        except Exception as e:
            print(f"[connect health] vòng quét lỗi: {type(e).__name__}: {e}",
                  file=sys.stderr)
        await asyncio.sleep(HEALTH_INTERVAL)


def start() -> None:
    """Gọi từ startup của app. Idempotent."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
