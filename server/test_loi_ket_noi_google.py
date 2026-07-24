"""Nút Test của kết nối MCP phải BÁO ĐÚNG BỆNH với các lỗi Google hay gặp, không đổ chung
một câu "Key chưa đúng hoặc chưa đủ quyền".

    cd server && ../.venv/Scripts/python.exe test_loi_ket_noi_google.py

Không cần pytest, không chạm mạng.

Bối cảnh: server MCP hosted của Google (calendarmcp/gmailmcp.googleapis.com) là API RIÊNG,
phải bật THÊM bên cạnh API thường và phải ghi danh Google Workspace Developer Preview Program.
Người dùng theo guide cũ chỉ bật Google Calendar API nên OAuth xong vẫn bị 403 khi gọi tool,
và Javis chỉ báo "Key chưa đúng hoặc chưa đủ quyền" - khách hiểu nhầm là hỏng key, có người
còn nghi tại não OpenRouter free. Test này giữ cho thông báo lỗi chỉ đúng chỗ cần sửa.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_hub

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


f = mcp_hub._friendly_tool_error

# ---- 1. API MCP chưa bật trong project (SERVICE_DISABLED) - lỗi phổ biến nhất ----
loi_disabled = (
    "Google Calendar MCP API has not been used in project 123456789 before or it is disabled. "
    "Enable it by visiting https://console.developers.google.com/apis/api/calendarmcp.googleapis.com/"
    "overview?project=123456789 then retry. If you enabled this API recently, wait a few minutes "
    "for the action to propagate to our systems and retry."
)
msg = f(loi_disabled)
check("API chưa bật -> nói rõ 'chưa được bật trong project'", "chưa được bật" in msg)
check("API chưa bật -> kèm đúng link bật API từ chính lỗi của Google",
      "https://console.developers.google.com/apis/api/calendarmcp.googleapis.com" in msg)
check("API chưa bật + là server *mcp.googleapis.com -> nhắc đây là API RIÊNG phải bật thêm",
      "riêng" in msg.lower())
check("API chưa bật + là server *mcp.googleapis.com -> nhắc ghi danh Developer Preview",
      "developers.google.com/workspace/preview" in msg)
check("API chưa bật -> KHÔNG còn câu chung chung đổ oan key", "Key chưa đúng" not in msg)

# API thường (không phải *mcp.googleapis.com) chưa bật -> vẫn báo bật API nhưng KHÔNG nhắc preview
loi_thuong = loi_disabled.replace("calendarmcp.googleapis.com", "calendar-json.googleapis.com")
msg2 = f(loi_thuong)
check("API thường chưa bật -> vẫn báo 'chưa được bật'", "chưa được bật" in msg2)
check("API thường chưa bật -> KHÔNG nhắc preview (không liên quan)",
      "workspace/preview" not in msg2)

# ---- 2. Token thiếu scope (người dùng bỏ tick lúc đồng ý) ----
msg3 = f('{"code": 403, "message": "Request had insufficient authentication scopes.", '
         '"status": "PERMISSION_DENIED"}')
check("thiếu scope -> khuyên đăng nhập lại và tick đủ quyền",
      "Đăng nhập lại" in msg3 and "tick" in msg3.lower())

# ---- 3. Token hỏng / hết hạn ----
msg4 = f("Request is missing required authentication credential. Expected OAuth 2 access token, "
         "login cookie or other valid authentication credential.")
check("token hỏng -> khuyên đăng nhập lại", "Đăng nhập lại" in msg4)
msg5 = f('{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}')
check("token hết hạn/thu hồi -> khuyên đăng nhập lại", "Đăng nhập lại" in msg5)

# ---- 4. Lỗi lạ -> giữ nguyên hành vi cũ (fallback), KHÔNG luôn-xanh ----
msg6 = f("something exploded: HTTP 500")
check("CANARY: lỗi lạ vẫn rơi về câu cũ kèm nguyên văn",
      msg6.startswith("Key chưa đúng hoặc chưa đủ quyền:") and "HTTP 500" in msg6)
check("CANARY: lỗi lạ không bị gán nhầm thành 'API chưa bật'", "chưa được bật" not in msg6)

# ---- 5. validate_connection phải THẬT SỰ đi qua bộ dịch này ----
src = Path(mcp_hub.__file__).read_text(encoding="utf-8")
m = re.search(r"async def validate_connection.*?(?=\nasync def |\ndef |\Z)", src, re.S)
check("validate_connection gọi _friendly_tool_error (không tự nối chuỗi cũ)",
      m is not None and "_friendly_tool_error" in m.group(0))

# ---- 6. Chuỗi UI phải có dấu tiếng Việt (quy tắc cứng của dự án) ----
check("thông báo có dấu tiếng Việt", "ậ" in msg3 or "ậ" in msg4)
for m_ in (msg, msg2, msg3, msg4, msg5, msg6):
    if "—" in m_ or "–" in m_:
        check("không có em/en dash trong thông báo", False)
        break
else:
    check("không có em/en dash trong thông báo", True)

if _fails:
    print(f"\nFAIL - test_loi_ket_noi_google: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_loi_ket_noi_google: tất cả pass")
