"""Test sức khoẻ kết nối (connect_health) - phân loại lỗi + check + sweep + snapshot."""
import asyncio
import time

import connect_health


# ---- classify_error: đủ nhánh, ưu tiên đúng thứ tự ----

def test_classify_auth():
    for err in ("HTTP 401 Unauthorized",
                "TokenError: invalid_grant",
                "Failed to authenticate: OAuth session expired and could not be refreshed",
                "invalid token provided"):
        kind, msg = connect_health.classify_error(err)
        assert kind == "auth", err
        assert "Kết nối lại" in msg


def test_classify_spawn():
    for err in ("FileNotFoundError: uvx",
                "'uvx' is not recognized as an internal or external command",
                "process exited with code 1"):
        kind, msg = connect_health.classify_error(err)
        assert kind == "spawn", err
        assert "máy chạy Javis" in msg


def test_classify_net():
    for err in ("ReadTimeout: timed out",
                "ConnectError: getaddrinfo failed",
                "Server disconnected without response",
                "HTTP 503 Service Unavailable"):
        kind, msg = connect_health.classify_error(err)
        assert kind == "net", err


def test_classify_unknown_giu_thong_diep_goc():
    kind, msg = connect_health.classify_error("ValueError: something odd " + "x" * 300)
    assert kind == "unknown"
    assert msg.startswith("ValueError")
    assert len(msg) <= 160


def test_classify_auth_thang_net_khi_ca_hai_khop():
    # "401" + "timeout" trong cùng chuỗi: auth phải thắng vì có hành động gắn kèm
    kind, _ = connect_health.classify_error("401 unauthorized after timeout")
    assert kind == "auth"


# ---- check_one / sweep với pool giả ----

class _FakePool:
    def __init__(self, tools=None, raise_error=None):
        self.tools = tools if tools is not None else [{"name": "a"}, {"name": "b"}]
        self.raise_error = raise_error
        self.calls = 0

    async def list_tools(self, spec):
        self.calls += 1
        if self.raise_error:
            raise self.raise_error
        return self.tools


def _conn(cid="c1", **kw):
    base = {"id": cid, "label": "Test", "transport": "http",
            "url": "http://example.local/mcp", "headers": {}, "args": [],
            "env": {}, "secrets": {}, "config": {}, "auth": "apikey"}
    base.update(kw)
    return base


def test_check_one_song():
    connect_health._state.clear()
    rec = asyncio.run(connect_health.check_one(_conn(), _FakePool()))
    assert rec["ok"] is True and rec["tools"] == 2
    assert connect_health.snapshot()["c1"]["ok"] is True


def test_check_one_loi_auth():
    connect_health._state.clear()
    pool = _FakePool(raise_error=RuntimeError("HTTP 401 unauthorized"))
    rec = asyncio.run(connect_health.check_one(_conn(), pool))
    assert rec["ok"] is False and rec["kind"] == "auth"
    assert "Kết nối lại" in rec["message"]


def test_check_one_connector_ao_luon_song():
    """Connector ảo (không url/command, tool do plugin phục vụ) không được báo đỏ oan."""
    connect_health._state.clear()
    pool = _FakePool(raise_error=RuntimeError("would explode"))
    rec = asyncio.run(connect_health.check_one(_conn(url="", command=""), pool))
    assert rec["ok"] is True
    assert pool.calls == 0


def test_sweep_mot_conn_loi_khong_giet_ca_vong(monkeypatch):
    connect_health._state.clear()

    def fake_resolved(enabled_only=True):
        return [_conn("ok1"), _conn("die1"), _conn("ok2")]

    class _PickyPool(_FakePool):
        async def list_tools(self, spec):
            self.calls += 1
            if spec["key"] == "die1":
                raise RuntimeError("timed out")
            return self.tools

    import mcp_store
    monkeypatch.setattr(mcp_store, "resolved", fake_resolved)
    n = asyncio.run(connect_health.sweep(_PickyPool()))
    snap = connect_health.snapshot()
    assert n == 3
    assert snap["ok1"]["ok"] and snap["ok2"]["ok"]
    assert snap["die1"]["kind"] == "net"


def test_check_by_id_khong_thay(monkeypatch):
    import mcp_store
    monkeypatch.setattr(mcp_store, "resolved", lambda enabled_only=False: [])
    rec = asyncio.run(connect_health.check_by_id("ma"))
    assert rec["ok"] is False and "Không tìm thấy" in rec["message"]


def test_forget_xoa_trang_thai():
    connect_health._state.clear()
    asyncio.run(connect_health.check_one(_conn("gone"), _FakePool()))
    assert "gone" in connect_health.snapshot()
    connect_health.forget("gone")
    assert "gone" not in connect_health.snapshot()


def test_snapshot_tra_ban_sao():
    connect_health._state.clear()
    asyncio.run(connect_health.check_one(_conn("s1"), _FakePool()))
    snap = connect_health.snapshot()
    snap["s1"]["ok"] = False
    assert connect_health.snapshot()["s1"]["ok"] is True
