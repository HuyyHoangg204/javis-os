"""Danh sách model Claude LIVE cho provider `anthropic-cli` (Claude Code OAuth).

Trước đây provider này không list được model nên picker rơi về catalog tĩnh trong
config.py (4 alias opus/sonnet/haiku/fable) - Anthropic ra bản mới (Opus 4.8, 4.7,
Sonnet 4.6...) thì Javis không thấy. Ở đây MƯỢN chính access token OAuth mà Claude
Code đã lưu sẵn để hỏi https://api.anthropic.com/v1/models, nên có model mới là
picker thấy ngay, không cần sửa code.

Không refresh token (tránh xoay refresh_token làm CLI của user bị đăng xuất): token
hết hạn thì trả None để caller fallback catalog - và catalog đã được /provider/models
ghi đè bằng danh sách live gần nhất nên vẫn mới.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MODELS_URL = "https://api.anthropic.com/v1/models"
OAUTH_BETA = "oauth-2025-04-20"          # header bắt buộc khi gọi API bằng token OAuth
_KEYCHAIN_SERVICE = "Claude Code-credentials"   # macOS lưu credential trong Keychain, không ra file


def _config_dirs():
    """Các thư mục có thể chứa .credentials.json của Claude Code."""
    env = (os.getenv("CLAUDE_CONFIG_DIR") or "").strip()
    if env:
        return [Path(env)]        # đặt biến này là ĐÈ hẳn, giống hành vi của Claude Code
    return [Path.home() / ".claude"]


def _from_blob(raw):
    """Bóc access token còn hạn từ nội dung .credentials.json. '' nếu không có/hết hạn."""
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    o = (data or {}).get("claudeAiOauth") or {}
    tok = (o.get("accessToken") or "").strip()
    if not tok:
        return ""
    exp = o.get("expiresAt") or 0                 # milli giây
    if exp and float(exp) / 1000 <= time.time() + 30:
        return ""                                 # hết hạn -> caller fallback
    return tok


def oauth_token():
    """Access token OAuth của Claude Code (env → file → Keychain macOS). '' nếu không có."""
    tok = (os.getenv("CLAUDE_CODE_OAUTH_TOKEN") or "").strip()
    if tok:
        return tok
    for d in _config_dirs():
        try:
            raw = (d / ".credentials.json").read_text(encoding="utf-8")
        except Exception:
            continue
        tok = _from_blob(raw)
        if tok:
            return tok
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, timeout=10)
            if out.returncode == 0:
                return _from_blob(out.stdout.strip())
        except Exception:
            pass
    return ""


def aliases(ids):
    """Alias 'luôn bản mới nhất' mà CLI nhận (opus, sonnet, haiku, fable...).

    Suy ra từ chính danh sách live - dòng model mới xuất hiện là tự có alias, khỏi sửa code.
    """
    out = []
    for i in ids:
        parts = (i or "").split("-")
        if len(parts) < 3 or parts[0] != "claude":
            continue
        fam = parts[1]
        if fam.isalpha() and fam not in out:
            out.append(fam)
    return out


async def fetch_models(api_key=""):
    """Danh sách model id (alias đứng trước, rồi tên đầy đủ). None = không lấy được."""
    import httpx
    tok = oauth_token()
    if tok:
        headers = {"Authorization": f"Bearer {tok}", "anthropic-beta": OAUTH_BETA}
    elif api_key:
        headers = {"x-api-key": api_key}          # chưa đăng nhập CLI nhưng có key API thì dùng tạm
    else:
        return None
    headers["anthropic-version"] = "2023-06-01"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(MODELS_URL, params={"limit": 100}, headers=headers)
        r.raise_for_status()
        data = r.json().get("data", [])
    ids = [x.get("id") for x in data if x.get("id")]
    return (aliases(ids) + ids) or None
