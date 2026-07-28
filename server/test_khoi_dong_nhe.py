"""Đường khởi động phải nhẹ: thư viện của tính năng tuỳ chọn KHÔNG được nạp lúc import main.

    cd server && python test_khoi_dong_nhe.py     (KHÔNG mạng)

Bối cảnh 0.9.238: `import edge_tts` nằm ở đầu main.py dù TTS là tính năng tuỳ chọn mà đa số
phiên không đụng tới. Đo bằng `python -X importtime`: 944ms trong tổng 2.263ms nạp main (41%),
cộng kéo cả chuỗi aiohttp 212ms vào đường khởi động. Trên VPS, khởi động chậm ăn thẳng vào
cửa sổ healthcheck lúc deploy.

Test này tồn tại vì lỗi kiểu đó rất dễ tái phát: ai đó thêm `import <thư viện nặng>` lên đầu
file cho tiện, không ai nhận ra, và app chậm dần từng chút một mà không có tín hiệu nào.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-khoidong-"))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# Thư viện chỉ phục vụ tính năng TUỲ CHỌN -> phải nạp lười.
# Thêm vào đây khi phát hiện thư viện nặng mới, đừng chờ ai đó tự nhận ra.
NANG_PHAI_LUOI = {
    "edge_tts": "TTS (giọng đọc) - 944ms, kéo theo cả aiohttp",
    "aiohttp": "chỉ đi kèm edge_tts, không code nào của Javis dùng trực tiếp",
}

import main  # noqa: E402,F401

for mod, ly_do in NANG_PHAI_LUOI.items():
    check(f"'{mod}' KHÔNG nạp lúc import main ({ly_do})", mod not in sys.modules)

# ---- Nạp lười phải thật sự nạp được, không phải chỉ hoãn lỗi sang lúc user bấm nói ----
# CỐ TÌNH không gọi main.tts_voices(): hàm đó đi mạng tới dịch vụ giọng đọc của Microsoft,
# mà test này phải chạy được offline. Chỉ kiểm hai điều tách bạch: (a) thư viện nạp được
# khi cần, (b) hai chỗ dùng đều có lệnh import cục bộ nên sẽ nạp được lúc chạy.
try:
    import edge_tts  # noqa: E402,F401
    nap_duoc = True
except Exception as e:
    nap_duoc = False
    print(f"     (nạp edge_tts lỗi: {type(e).__name__}: {e})")
check("edge_tts vẫn nạp được khi cần (không phải chỉ hoãn lỗi sang lúc dùng)", nap_duoc)

import inspect  # noqa: E402

for ten in ("_tts_edge", "tts_voices"):
    fn = getattr(main, ten, None)
    src = inspect.getsource(fn) if fn else ""
    check(f"{ten}() có lệnh import edge_tts cục bộ", "import edge_tts" in src)

# ---- Trần thời gian nạp, đo trong tiến trình con cho sạch ----
# Trần đặt rộng (3 giây) vì máy CI chậm và chia sẻ CPU. Mục đích KHÔNG phải bắt vài chục
# mili giây, mà bắt cú lùi lớn kiểu ai đó kéo lại một thư viện cả giây vào đường khởi động.
TRAN_MS = 3000


def do_nap(code):
    import time
    t = time.perf_counter()
    subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True)
    return (time.perf_counter() - t) * 1000


base = min(do_nap("pass") for _ in range(3))
full = min(do_nap("import main") for _ in range(3))
nap_ms = full - base
print(f"     (nạp main {nap_ms:.0f} ms, interpreter trần {base:.0f} ms)")
check(f"nạp main dưới {TRAN_MS} ms (đang {nap_ms:.0f} ms)", nap_ms < TRAN_MS)

# ---- Không ai lén thêm lại import ở mức module ----
src = Path(HERE, "main.py").read_text(encoding="utf-8", errors="replace")
for mod in NANG_PHAI_LUOI:
    o_cot_0 = [ln for ln in src.split("\n")
               if ln.startswith(f"import {mod}") or ln.startswith(f"from {mod} ")]
    check(f"main.py không có 'import {mod}' ở mức module", not o_cot_0)

print()
if _fails:
    print(f"FAIL {len(_fails)} test: " + ", ".join(_fails))
    sys.exit(1)
print("TẤT CẢ PASS")
