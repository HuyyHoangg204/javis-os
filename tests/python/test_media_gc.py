"""Test media_gc (dọn media quá hạn trong vùng cache của brain). Chạy tay / CI:

    python tests/run.py media_gc

plan_deletions là hàm THUẦN nên phần lớn test không chạm đĩa; phần quét/xoá dùng thư mục tạm.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path
import sys
import time

import media_gc   # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


NOW = 1_800_000_000.0
DAY = 86400.0
MB = 1024 * 1024


def muc(path, mb, tuoi_ngay):
    """Một mục (path, size, mtime) với mtime cách NOW đúng tuoi_ngay ngày."""
    return (path, int(mb * MB), NOW - tuoi_ngay * DAY)


# ---- 1. Còn mới và tổng dưới trần: không xoá gì ----
r = media_gc.plan_deletions([muc("a.png", 1, 1), muc("b.png", 2, 5)], NOW, 30, 300)
check("moi + duoi tran -> khong xoa gi", r == [])

# ---- 2. Quá hạn tuổi thì xoá, trong hạn thì giữ ----
r = media_gc.plan_deletions([muc("cu.png", 1, 40), muc("moi.png", 1, 5)], NOW, 30, 300)
check("qua han tuoi -> chi xoa file cu", r == ["cu.png"])

# ---- 3. Vượt trần dù mọi file còn trong hạn: xoá từ cũ tới mới, dừng đúng lúc ----
r = media_gc.plan_deletions(
    [muc("x3.png", 200, 3), muc("x2.png", 200, 2), muc("x1.png", 200, 1)], NOW, 30, 300)
check("vuot tran -> xoa cu truoc, dung khi du", r == ["x3.png", "x2.png"])

# ---- 4. Vừa quá hạn vừa vượt trần: cộng dồn, không đếm trùng ----
r = media_gc.plan_deletions(
    [muc("cu.png", 10, 40), muc("y2.png", 200, 3), muc("y1.png", 200, 1)], NOW, 30, 300)
check("qua han + vuot tran -> cong don, khong trung",
      r == ["cu.png", "y2.png"] and len(r) == len(set(r)))

# ---- 5. File .md không bao giờ bị xoá ----
r = media_gc.plan_deletions([muc("ghi-chu.md", 400, 99), muc("anh.png", 1, 40)], NOW, 30, 300)
check("chua file .md", r == ["anh.png"])

# ---- 6. Tắt từng luật bằng 0 / số âm ----
check("max_age_days=0 -> tat luat tuoi",
      media_gc.plan_deletions([muc("cu.png", 1, 999)], NOW, 0, 300) == [])
check("max_mb=0 -> tat luat tran",
      media_gc.plan_deletions([muc("to.png", 999, 1)], NOW, 30, 0) == [])
check("tat ca hai -> khong xoa gi",
      media_gc.plan_deletions([muc("cu-va-to.png", 999, 999)], NOW, -1, -1) == [])

# ---- 7. Danh sách rỗng ----
check("danh sach rong", media_gc.plan_deletions([], NOW, 30, 300) == [])

print()
if _fails:
    print(f"{len(_fails)} test ĐỎ: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test media_gc xanh.")
