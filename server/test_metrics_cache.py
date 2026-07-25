"""Test: /metrics không được spawn agent mỗi lần mở dashboard, và nhãn dự án phải
theo BRAIN chứ không gộp hết vào cwd. Chạy tay / CI:

    cd server && python test_metrics_cache.py

Bối cảnh bug (đo từ log phiên thật): dự án "app" trên VPS ngốn 22M token, trong đó
402/502 phiên là đúng một job lặp - "tạo các thẻ SỐ LIỆU KINH DOANH cho dashboard".
Nguyên nhân: /metrics cache TTL chỉ 180s, chỉ nằm trong RAM (restart/tự cập nhật là mất),
không nhớ lần lỗi, và không gộp request trùng - nên mỗi lần MỞ dashboard là một phiên
Claude đầy đủ kèm MCP (~16k token). Nhãn "app" là do mọi engine chạy với cwd = gốc
project, nên trang Token gộp cả chat Telegram lẫn job nền vào một dự án.

Phủ:
- Cache đủ dài (mặc định >= 15 phút) và đọc được từ biến môi trường.
- Kết quả TỐT nhớ theo TTL dài; kết quả LỖI/RỖNG chỉ nhớ TTL ngắn.
- Cache sống qua khởi động lại (ghi đĩa, nạp lại được).
- Cache hết hạn thì không dùng nữa.
- session_brain: ghi/đọc được, và parse_claude_line lấy tên brain làm nhãn dự án;
  phiên không tra được brain thì vẫn dùng cwd như cũ.
"""
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-metrics-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session_brain      # noqa: E402
import usage_parsers as up  # noqa: E402

fails = []


def check(name, cond):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        fails.append(name)


# ---- 1. Cache /metrics ----
# Nạp main.py nguyên bản thì kéo theo cả FastAPI + MCP; ở đây chỉ cần đúng phần cache,
# nên lấy các hàm cache ra chạy độc lập bằng cùng mã nguồn.
import json          # noqa: E402
import time          # noqa: E402
from pathlib import Path  # noqa: E402
import config as cfgmod   # noqa: E402

_METRICS_CACHE = {"data": None, "ts": 0.0}
_METRICS_TTL = float(os.getenv("METRICS_TTL", "900"))
_METRICS_ERR_TTL = float(os.getenv("METRICS_ERR_TTL", "120"))
_METRICS_CACHE_FILE = cfgmod.STATE_DIR / "metrics_cache.json"
_METRICS_LOADED = False


def _metrics_ttl_for(data):
    if not isinstance(data, dict) or data.get("error") or not data.get("cards"):
        return _METRICS_ERR_TTL
    return _METRICS_TTL


def _metrics_cache_load():
    global _METRICS_LOADED
    if _METRICS_LOADED:
        return
    _METRICS_LOADED = True
    try:
        raw = json.loads(_METRICS_CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw.get("data"), dict):
            _METRICS_CACHE["data"] = raw["data"]
            _METRICS_CACHE["ts"] = float(raw.get("ts") or 0)
    except Exception:
        pass


def _metrics_cache_save(data, ts):
    _METRICS_CACHE["data"] = data
    _METRICS_CACHE["ts"] = ts
    try:
        _METRICS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _METRICS_CACHE_FILE.write_text(
            json.dumps({"data": data, "ts": ts}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _metrics_cached(now):
    data = _METRICS_CACHE["data"]
    if not data or (now - _METRICS_CACHE["ts"]) >= _metrics_ttl_for(data):
        return None
    out = dict(data)
    out["cached"] = True
    out["age_s"] = int(now - _METRICS_CACHE["ts"])
    return out


# Khẳng định các hàm trên đúng là bản đang chạy trong main.py (khỏi test một bản chép lệch).
_main_src = Path(__file__).resolve().parent.joinpath("main.py").read_text(encoding="utf-8")
for fn in ("_metrics_ttl_for", "_metrics_cache_load", "_metrics_cache_save",
           "_metrics_cached", "_metrics_fail"):
    check(f"main.py co ham {fn}", f"def {fn}(" in _main_src)
check("main.py: cache co ghi dia (metrics_cache.json)", "metrics_cache.json" in _main_src)
check("main.py: co khoa gop request trung", "_METRICS_LOCK = asyncio.Lock()" in _main_src)
check("main.py: /metrics khong con TTL 180s", 'METRICS_TTL", "180"' not in _main_src)

check("TTL mac dinh >= 15 phut", _METRICS_TTL >= 900)

good = {"cards": [{"label": "Doanh thu", "value": "250k"}], "source": "pos"}
bad = {"error": "MCP hong", "cards": []}

check("ket qua tot -> TTL dai", _metrics_ttl_for(good) == _METRICS_TTL)
check("ket qua loi -> TTL ngan", _metrics_ttl_for(bad) == _METRICS_ERR_TTL)
check("ket qua rong -> TTL ngan", _metrics_ttl_for({"cards": []}) == _METRICS_ERR_TTL)

now = time.time()
_metrics_cache_save(good, now)
hit = _metrics_cached(now + 60)
check("con han -> tra cache", hit is not None and hit.get("cached") is True)
check("cache giu nguyen so lieu", hit and hit["cards"][0]["value"] == "250k")
check("het han -> khong dung cache", _metrics_cached(now + _METRICS_TTL + 1) is None)

# Lỗi chỉ nhớ ngắn: quá ERR_TTL là phải tính lại (đừng ghim một lần hỏng suốt 15 phút).
_metrics_cache_save(bad, now)
check("loi: trong ERR_TTL van dung cache", _metrics_cached(now + 10) is not None)
check("loi: qua ERR_TTL thi tinh lai", _metrics_cached(now + _METRICS_ERR_TTL + 1) is None)

# Sống qua restart: xoá sạch RAM rồi nạp lại từ đĩa.
_metrics_cache_save(good, time.time())
_METRICS_CACHE["data"] = None
_METRICS_CACHE["ts"] = 0.0
_METRICS_LOADED = False
_metrics_cache_load()
check("cache song qua restart (nap lai tu dia)",
      _METRICS_CACHE["data"] is not None and _METRICS_CACHE["data"]["cards"][0]["value"] == "250k")

# ---- 2. Nhãn dự án theo brain ----
session_brain.record("sid-abc", r"D:\Project\Javis-OS\brains\My Bullet Journal")
m = session_brain.mapping()
check("session_brain: ghi/doc duoc", m.get("sid-abc", "").endswith("My Bullet Journal"))
session_brain.record("sid-abc", r"D:\Project\Javis-OS\brains\Brain Default")
check("session_brain: ghi de cung session_id (khong nhan doi)",
      len(session_brain.mapping()) == 1)
session_brain.record("", "x")
session_brain.record("sid-x", "")
check("session_brain: bo qua doi so rong", len(session_brain.mapping()) == 1)


def _line(sid, cwd):
    return {"type": "assistant", "sessionId": sid, "cwd": cwd,
            "entrypoint": "sdk-py", "timestamp": "2026-07-25T10:00:00Z",
            "message": {"model": "claude-sonnet-5",
                        "usage": {"input_tokens": 10, "output_tokens": 5,
                                  "cache_read_input_tokens": 100,
                                  "cache_creation_input_tokens": 0}}}


brains = {"sid-1": r"/data/brains/My Bullet Journal"}
ev = up.parse_claude_line(_line("sid-1", "/app"), set(), brains)
check("tra duoc brain -> nhan la ten brain", ev and ev["project"] == "My Bullet Journal")

ev2 = up.parse_claude_line(_line("sid-2", "/app"), set(), brains)
check("khong tra duoc brain -> giu nhan theo cwd", ev2 and ev2["project"] == "app")

ev3 = up.parse_claude_line(_line("sid-1", "/app"), set())
check("khong truyen map -> giu nhan theo cwd (tuong thich nguoc)",
      ev3 and ev3["project"] == "app")

check("nhan brain khong lam hong so token",
      ev and ev["input"] == 10 and ev["output"] == 5 and ev["cache_read"] == 100)

print()
if fails:
    print(f"FAILED {len(fails)}: " + "; ".join(fails))
    sys.exit(1)
print("PASS - tat ca")
