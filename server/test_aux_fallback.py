"""Test fallback engine việc nền: engine phụ (Codex/API) lỗi lúc CHẠY → tự chạy lại bằng
Claude (ca thật: Codex hết quota ChatGPT làm nhắc hẹn chết, chỉ báo ⚠ về Telegram).
Chạy:  cd server && ..\\.venv\\Scripts\\python.exe test_aux_fallback.py    (KHÔNG mạng)."""
import os, sys, tempfile, asyncio
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-auxfb-test-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)

import aux_engine  # noqa: E402


class FakeEngine:
    """Engine giả theo hợp đồng ClaudeSDK: query() sinh dict sự kiện."""
    def __init__(self, events=None, available=True, raise_exc=None):
        self.events = events or []
        self.available = available
        self.raise_exc = raise_exc
        self.ran = 0
        self.session_id = None

    def is_available(self):
        return self.available

    def reset_session(self):
        self.session_id = None

    async def query(self, prompt):
        self.ran += 1
        if self.raise_exc:
            raise self.raise_exc
        for ev in self.events:
            yield ev


async def collect(engine, prompt="lam viec"):
    return [ev async for ev in engine.query(prompt)]


FB = aux_engine._FallbackToClaude
run = asyncio.run

# --- phụ chạy ngon → không đụng Claude ---
codex = FakeEngine([{"type": "tool_call", "name": "x"}, {"type": "final", "content": "xong"}])
claude = FakeEngine([{"type": "final", "content": "claude day"}])
evs = run(collect(FB(codex, claude)))
check("phụ ok: trả đúng sự kiện của phụ", evs[-1] == {"type": "final", "content": "xong"})
check("phụ ok: KHÔNG chạy Claude", claude.ran == 0)

# --- phụ trả error (ca Codex hết quota) → chạy lại bằng Claude ---
codex = FakeEngine([{"type": "error", "content": "Codex: You've hit your usage limit."}])
claude = FakeEngine([{"type": "final", "content": "claude cứu"}])
evs = run(collect(FB(codex, claude)))
check("phụ hết quota: final đến từ Claude", evs[-1]["content"] == "claude cứu")
check("phụ hết quota: error của phụ KHÔNG lọt ra ngoài", all(e.get("type") != "error" for e in evs))
check("phụ hết quota: Claude chạy đúng 1 lần", claude.ran == 1)

# --- phụ nổ exception → chạy lại bằng Claude ---
codex = FakeEngine(raise_exc=RuntimeError("codex chết"))
claude = FakeEngine([{"type": "final", "content": "van song"}])
evs = run(collect(FB(codex, claude)))
check("phụ nổ exception: Claude cứu", evs[-1]["content"] == "van song")

# --- phụ câm (kết thúc không final) → cũng coi là chết ---
codex = FakeEngine([{"type": "tool_call", "name": "y"}])
claude = FakeEngine([{"type": "final", "content": "co final"}])
evs = run(collect(FB(codex, claude)))
check("phụ câm: Claude cứu, final có mặt", evs[-1]["content"] == "co final")

# --- phụ không sẵn sàng → đi thẳng Claude ---
codex = FakeEngine(available=False)
claude = FakeEngine([{"type": "final", "content": "truc tiep"}])
evs = run(collect(FB(codex, claude)))
check("phụ unavailable: đi thẳng Claude, phụ không chạy", evs[-1]["content"] == "truc tiep" and codex.ran == 0)

# --- cả hai chết → trả error thật (không nuốt) ---
codex = FakeEngine([{"type": "error", "content": "quota"}])
claude = FakeEngine(available=False)
evs = run(collect(FB(codex, claude)))
check("cả hai chết: lộ error để nơi gọi báo user", evs[-1]["type"] == "error")

# --- hợp đồng attr: gán → cả hai, đọc → phụ; is_available OR hai bên ---
codex, claude = FakeEngine(), FakeEngine()
w = FB(codex, claude)
w.max_wall_s = 300
check("gán attr đặt cho CẢ HAI engine", codex.max_wall_s == 300 and claude.max_wall_s == 300)
codex.tag = "reminder"
check("đọc attr lấy từ engine phụ", w.tag == "reminder")
codex.available = False
check("is_available = OR hai bên", w.is_available() is True)
claude.available = False
check("cả hai tắt → is_available False", w.is_available() is False)

# --- swap() bọc fallback cho provider API (không cần CLI thật) ---
settings = {"model": {"openrouter_key": "sk-or-test", "auxiliary": {}}}
spec = {"provider": "openrouter", "model": "test/model"}
out = aux_engine.swap(FakeEngine(), spec=spec, settings=settings)
check("swap provider API → trả wrapper fallback", type(out).__name__ == "_FallbackToClaude")
spec_claude = {"provider": "anthropic-cli", "model": ""}
base = FakeEngine()
check("swap provider Claude → trả NGUYÊN engine, không bọc",
      aux_engine.swap(base, spec=spec_claude, settings=settings) is base)

print()
if _fails:
    print(f"FAIL {len(_fails)} test: " + ", ".join(_fails)); sys.exit(1)
print("TẤT CẢ PASS")
