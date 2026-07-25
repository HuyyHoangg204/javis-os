"""Test lấy model Claude LIVE cho provider anthropic-cli. Chạy tay / CI:

    cd server && python test_claude_models.py

Không chạm mạng: chỉ kiểm phần đọc credential + suy alias + fallback khi không có token.
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import claude_models as cm   # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


def _write_creds(dirpath, token, expires_ms):
    p = Path(dirpath) / ".credentials.json"
    p.write_text(json.dumps({"claudeAiOauth": {"accessToken": token, "expiresAt": expires_ms}}),
                 encoding="utf-8")
    return p


# ---- 1. Suy alias từ danh sách live ----
IDS = ["claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-opus-4-8",
       "claude-haiku-4-5-20251001", "claude-opus-4-1-20250805"]
al = cm.aliases(IDS)
check("alias gồm đủ các dòng model", al == ["opus", "sonnet", "fable", "haiku"])
check("alias không trùng lặp", len(al) == len(set(al)))
check("bỏ qua id lạ", cm.aliases(["gpt-4o", "claude", "claude-", "x-opus-5"]) == [])

# ---- 2. Đọc credential ----
tmp = tempfile.mkdtemp(prefix="javis-cm-")
os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
os.environ["CLAUDE_CONFIG_DIR"] = tmp

check("chưa có file → không có token", cm.oauth_token() == "")

_write_creds(tmp, "tok-live", int((time.time() + 3600) * 1000))
check("token còn hạn → đọc được", cm.oauth_token() == "tok-live")

_write_creds(tmp, "tok-cu", int((time.time() - 60) * 1000))
check("token hết hạn → bỏ qua", cm.oauth_token() == "")

_write_creds(tmp, "", int((time.time() + 3600) * 1000))
check("token rỗng → bỏ qua", cm.oauth_token() == "")

(Path(tmp) / ".credentials.json").write_text("{ hỏng", encoding="utf-8")
check("file hỏng không làm vỡ", cm.oauth_token() == "")

os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "tok-env"
check("env đè file", cm.oauth_token() == "tok-env")
os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN")

# ---- 3. Không có credential nào → None để caller fallback catalog ----
if sys.platform == "darwin":
    cm.oauth_token = lambda: ""      # máy Mac có Keychain thật, ép rỗng cho nhánh này
check("không token, không key → None", asyncio.run(cm.fetch_models("")) is None)

print()
if _fails:
    print(f"{len(_fails)} test HỎNG: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test claude_models đã qua.")
