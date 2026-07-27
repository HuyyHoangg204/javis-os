"""Test image_gen (tạo ảnh qua ChatGPT). Chạy tay / CI:

    cd server && JAVIS_STATE_DIR=<temp> python test_image_gen.py

Không chạm mạng: phần gọi thật được mock (fake httpx + fake creds) để kiểm payload → parse SSE → lưu.
"""
import asyncio
import base64
import json
import os
import sys
import tempfile
import zlib

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-imgtest-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config           # noqa: E402
import image_gen        # noqa: E402
import openai_oauth     # noqa: E402


def _cfg_default_strip():
    """Giá trị MẶC ĐỊNH của image.strip_c2pa trong config._DEFAULT (không đọc settings.json
    của máy đang chạy, vì máy đó có thể đã bật tay)."""
    return (config._DEFAULT.get("image") or {}).get("strip_c2pa")

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# PNG 1x1 hợp lệ (base64)
_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")

# ---- 1. resolve_size ----
check("size square", image_gen.resolve_size("square") == "1024x1024")
check("size landscape", image_gen.resolve_size("landscape") == "1536x1024")
check("size portrait", image_gen.resolve_size("portrait") == "1024x1536")
check("size lạ → square", image_gen.resolve_size("weird") == "1024x1024")

# ---- 2. build_payload đúng cấu trúc image_generation ----
p = image_gen.build_payload("con mèo", "1024x1024", "medium")
check("payload stream", p["stream"] is True)
check("payload có tool image_generation", p["tools"][0]["type"] == "image_generation")
check("payload model ảnh", p["tools"][0]["model"] == image_gen.IMAGE_MODEL)
check("payload size/quality", p["tools"][0]["size"] == "1024x1024" and p["tools"][0]["quality"] == "medium")
check("payload tool_choice required", p["tool_choice"]["mode"] == "required")
check("payload prompt trong input", p["input"][0]["content"][0]["text"] == "con mèo")

# ---- 3. extract_image_b64 các hình dạng ----
ev_final = {"type": "response.completed", "response": {"output": [
    {"type": "image_generation_call", "result": _PNG_B64}]}}
check("extract từ response.completed", image_gen.extract_image_b64(ev_final) == _PNG_B64)
check("extract từ partial", image_gen.extract_image_b64({"partial_image_b64": "ABC"}) == "ABC")
check("extract không có ảnh → None", image_gen.extract_image_b64({"type": "response.created"}) is None)
# final ghi đè partial (b64 mới nhất thắng khi đi qua nhiều event trong generate_chatgpt)
check("extract list", image_gen.extract_image_b64([{"x": 1}, {"partial_image_b64": "Z"}]) == "Z")

# ---- 4. save_png_b64 lưu đúng chỗ ----
vault = tempfile.mkdtemp(prefix="javis-vault-")
saved = image_gen.save_png_b64(_PNG_B64, vault)
check("save ok", saved.get("ok") is True)
check("rel_path vào attachments/", saved["rel_path"].startswith("attachments/") and saved["rel_path"].endswith(".png"))
check("file thật tồn tại", os.path.isfile(saved["abs_path"]))
_raw_goc = base64.b64decode(_PNG_B64)
_raw_luu = open(saved["abs_path"], "rb").read()
_IHDR_END = 8 + 12 + int.from_bytes(_raw_goc[8:12], "big")   # hết chunk IHDR

check("ảnh lưu ra có gắn nhãn javisos.com", b"javisos.com" in _raw_luu and b"Javis OS" in _raw_luu)
# Gắn nhãn = CHỈ CHÈN chunk giữa IHDR và phần còn lại. Đầu và đuôi file phải y nguyên,
# tức pixel không bị đụng vào và không chunk nào bị gỡ.
check("phần đầu (chữ ký PNG + IHDR) y nguyên", _raw_luu[:_IHDR_END] == _raw_goc[:_IHDR_END])
check("toàn bộ phần sau IHDR (pixel + IEND) còn nguyên vẹn", _raw_goc[_IHDR_END:] in _raw_luu)
check("nhãn chèn ngay sau IHDR, ở chunk tEXt", _raw_luu[_IHDR_END + 4:_IHDR_END + 8] == b"tEXt")


# ---- 4b. brand_png: gắn nhãn tác giả, KHÔNG gỡ chunk sẵn có ----
# Ảnh nhà cung cấp mang sẵn Content Credentials (C2PA, nằm ở chunk caBX). Javis CHỈ THÊM
# nhãn của mình, KHÔNG gỡ chunk đó - test này khoá hành vi ấy lại để sau không ai lặng lẽ
# đổi thành "gỡ nguồn gốc rồi ghi đè tên mình".
_gia_c2pa = (len(b"FAKE").to_bytes(4, "big") + b"caBX" + b"FAKE"
             + zlib.crc32(b"caBXFAKE").to_bytes(4, "big"))
_co_c2pa = _raw_goc[:_IHDR_END] + _gia_c2pa + _raw_goc[_IHDR_END:]
_sau = image_gen.brand_png(_co_c2pa)
check("brand_png KHÔNG gỡ chunk Content Credentials (caBX) có sẵn",
      b"caBX" in _sau and b"FAKE" in _sau)
check("brand_png vẫn gắn được nhãn khi ảnh đã có caBX", b"javisos.com" in _sau)
check("brand_png: không phải PNG → trả nguyên xi", image_gen.brand_png(b"khong-phai-png") == b"khong-phai-png")
check("brand_png: rỗng → không nổ", image_gen.brand_png(b"") == b"")


# ---- 4c. strip_c2pa_png: CHỈ chạy khi chủ workspace tự bật ----
_da_go = image_gen.strip_c2pa_png(_co_c2pa)
check("strip_c2pa_png: gỡ sạch chunk caBX", b"caBX" not in _da_go and b"FAKE" not in _da_go)
check("strip_c2pa_png: phần còn lại của ảnh y nguyên", _da_go == _raw_goc)
check("strip_c2pa_png: ảnh không có caBX → trả nguyên xi", image_gen.strip_c2pa_png(_raw_goc) == _raw_goc)
check("strip_c2pa_png: không phải PNG → trả nguyên xi", image_gen.strip_c2pa_png(b"xyz") == b"xyz")

# MẶC ĐỊNH PHẢI LÀ GIỮ DẤU. Đây là hành vi an toàn và là trạng thái mọi bản fork khởi đầu -
# test này khoá lại để không ai lỡ tay đổi mặc định thành gỡ.
check("mặc định: cấu hình image.strip_c2pa = False",
      _cfg_default_strip() is False)

# Bật/tắt phải thật sự đổi hành vi lúc lưu ảnh.
_goc_strip_on = image_gen._strip_c2pa_on
try:
    image_gen._strip_c2pa_on = lambda: False
    _giu = image_gen.save_png_b64(base64.b64encode(_co_c2pa).decode(), vault)
    _byte_giu = open(_giu["abs_path"], "rb").read()
    check("tắt (mặc định): dấu nguồn gốc caBX VẪN nằm trong ảnh", b"caBX" in _byte_giu)

    image_gen._strip_c2pa_on = lambda: True
    _go = image_gen.save_png_b64(base64.b64encode(_co_c2pa).decode(), vault)
    _byte_go = open(_go["abs_path"], "rb").read()
    check("bật: dấu nguồn gốc caBX bị gỡ khỏi ảnh", b"caBX" not in _byte_go)
    check("bật: nhãn tác giả javisos.com VẪN còn (không đánh tráo danh nghĩa)",
          b"javisos.com" in _byte_go)
finally:
    image_gen._strip_c2pa_on = _goc_strip_on


# ---- 5. generate_chatgpt end-to-end (mock mạng) ----
def _install_fake(lines, status=200):
    class FakeStream:
        status_code = status
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def aiter_lines(self):
            for ln in lines:
                yield ln
        async def aread(self): return b""

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, *a, **k): return FakeStream()

    image_gen.httpx.AsyncClient = FakeClient


openai_oauth.valid_creds = lambda: {"access_token": "faketoken", "account_id": "acc_1"}
sse = [
    "data: " + json.dumps({"type": "response.created"}),
    "data: " + json.dumps({"type": "response.image_generation_call.partial_image",
                           "partial_image_b64": "partialXYZ"}),
    "data: " + json.dumps({"type": "response.completed", "response": {"output": [
        {"type": "image_generation_call", "result": _PNG_B64}]}}),
    "data: [DONE]",
]
_install_fake(sse)
res = asyncio.run(image_gen.generate_chatgpt("một chú mèo cam", "landscape", "high", vault_root=vault))
check("generate ok", res.get("ok") is True)
check("generate rel_path attachments", res.get("rel_path", "").startswith("attachments/"))
check("generate size landscape", res.get("size") == "1536x1024")
check("generate lưu đúng ảnh cuối (không phải partial)",
      res.get("ok") and base64.b64decode(_PNG_B64)[_IHDR_END:] in open(res["abs_path"], "rb").read())

# ---- 6. lỗi HTTP surface rõ ----
_install_fake(["ignored"], status=401)
res_err = asyncio.run(image_gen.generate_chatgpt("x", vault_root=vault))
check("HTTP lỗi → ok False + báo mã", res_err.get("ok") is False and "401" in (res_err.get("error") or ""))

# ---- 7. chưa đăng nhập → báo rõ ----
openai_oauth.valid_creds = lambda: None
res_noauth = asyncio.run(image_gen.generate_chatgpt("x", vault_root=vault))
check("chưa OAuth → ok False", res_noauth.get("ok") is False and "ChatGPT" in (res_noauth.get("error") or ""))

print()
if _fails:
    print(f"THẤT BẠI {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_image_gen: tất cả pass")
