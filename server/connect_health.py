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


async def _loop():
    await asyncio.sleep(_STARTUP_DELAY)
    while True:
        try:
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
