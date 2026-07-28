"""GET /brains: đếm note có TRẦN, chạy ngoài event loop, không đếm thư mục hệ thống.

    cd server && python test_brains_dem.py     (KHÔNG mạng)

Bối cảnh 0.9.239: list_brains() dùng `p.rglob("*.md")` cho TỪNG brain - đi hết cây, không
trần, không offload. Đo được 136ms mỗi request trên 4 brain / 837 file, tăng tuyến tính theo
vault, mà dashboard gọi nó lúc BOOT. Đúng lỗi này đã được chẩn cho /viec/all và ghi hẳn
comment tiếng Việt trong main.py, nhưng /brains thì để nguyên suốt từ đó.

Test quan trọng nhất ở đây là "event loop vẫn thở": đó là thứ đã làm VPS trả 404 toàn trang
(request nặng bỏ đói healthcheck -> Docker gắn unhealthy -> Traefik gỡ route).
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-braindem-")
os.environ.setdefault("JAVIS_STATE_DIR", _STATE)
_BRAINS = tempfile.mkdtemp(prefix="javis-braindem-brains-")
os.environ["BRAINS_DIR"] = _BRAINS       # main.py:432 đọc đúng tên này, KHÔNG có tiền tố JAVIS_
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import main  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


BASE = Path(main.BRAINS_DIR)

# CHỐT CHẶN - đừng gỡ. Test này TẠO brain giả, nên nếu BRAINS_DIR không phải thư mục tạm thì
# nó sẽ đẻ rác vào kho brain THẬT của người dùng. Đã xảy ra một lần: đặt nhầm tên biến môi
# trường (JAVIS_BRAINS_DIR thay vì BRAINS_DIR) làm 3019 file rác rơi vào brains/ thật.
# Chết ngay còn hơn ghi nhầm chỗ.
if BASE.resolve() != Path(_BRAINS).resolve():
    print(f"FAIL BRAINS_DIR không trỏ vào thư mục tạm: {BASE}\n"
          f"     (mong đợi {_BRAINS}). DỪNG để khỏi ghi rác vào brain thật.")
    sys.exit(1)

BASE.mkdir(parents=True, exist_ok=True)


def dung_brain(ten, n_note, n_an=0, sau=0):
    d = BASE / ten
    (d / "notes").mkdir(parents=True, exist_ok=True)
    for i in range(n_note):
        (d / "notes" / f"note-{i}.md").write_text(f"# ghi chú {i}\n", encoding="utf-8")
    for i in range(n_an):
        # .claude/skills = bản mirror do CHÍNH Javis sinh ra, không phải note của user
        p = d / ".claude" / "skills" / f"sk-{i}"
        p.mkdir(parents=True, exist_ok=True)
        (p / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    if sau:
        p = d
        for k in range(sau):
            p = p / f"tang{k}"
        p.mkdir(parents=True, exist_ok=True)
        (p / "that-sau.md").write_text("sâu\n", encoding="utf-8")
    return d


dung_brain("Brain A", 12, n_an=5)
dung_brain("Brain B", 3, sau=12)
(BASE / ".an-di").mkdir(exist_ok=True)          # thư mục ẩn ở mức brain -> phải bỏ qua


def goi():
    return asyncio.run(main.list_brains())


r = goi()
ten = {b["name"]: b for b in r["brains"]}
# "Brain Default" do _default_brain_dir() tự tạo (hành vi đúng: brain khởi đầu luôn có mặt).
check(f"liệt kê 2 brain vừa dựng + Brain Default tự sinh, bỏ qua thư mục ẩn ({sorted(ten)})",
      sorted(ten) == ["Brain A", "Brain B", "Brain Default"])
check("thư mục ẩn '.an-di' KHÔNG lọt vào danh sách brain", ".an-di" not in ten)
check("đúng một brain được đánh dấu mặc định",
      sum(1 for b in r["brains"] if b["is_default"]) == 1)

# ---- 1. Không đếm .md trong thư mục hệ thống (.claude/skills là mirror Javis tự sinh) ----
check(f"Brain A đếm 12 note, KHÔNG cộng 5 file trong .claude (được {ten['Brain A']['notes']})",
      ten["Brain A"]["notes"] == 12)
tat_ca = len(list((BASE / "Brain A").rglob("*.md")))
check(f"đối chiếu: rglob đếm tất cả là {tat_ca}, tức đã loại đúng 5 file hệ thống",
      tat_ca == 17)

# ---- 2. Trần độ sâu: file quá sâu không tính, nhưng cũng không làm hỏng lần đếm ----
check(f"Brain B đếm 3 note, file ở tầng 12 nằm ngoài trần độ sâu (được {ten['Brain B']['notes']})",
      ten["Brain B"]["notes"] == 3)

# ---- 3. Trần số lượng + cờ notes_capped ----
that = main._BRAINS_MD_CAP
try:
    main._BRAINS_MD_CAP = 5
    r2 = goi()
    a = [b for b in r2["brains"] if b["name"] == "Brain A"][0]
    b = [b for b in r2["brains"] if b["name"] == "Brain B"][0]
    check(f"chạm trần thì dừng đúng ở trần (được {a['notes']}, trần 5)", a["notes"] == 5)
    check("chạm trần thì gắn cờ notes_capped=True", a["notes_capped"] is True)
    check("chưa chạm trần thì notes_capped=False", b["notes_capped"] is False)
finally:
    main._BRAINS_MD_CAP = that

# ---- 4. Event loop vẫn thở trong lúc quét (đây là thứ đã gây 404 toàn trang trên VPS) ----
dung_brain("Brain To", 3000)


async def do_do_tre():
    tre = []

    async def nhip():
        while True:
            t = time.perf_counter()
            await asyncio.sleep(0.005)
            tre.append((time.perf_counter() - t) * 1000)

    t_nhip = asyncio.create_task(nhip())
    await asyncio.sleep(0.05)          # cho nhịp chạy ổn định
    await main.list_brains()
    t_nhip.cancel()
    try:
        await t_nhip
    except asyncio.CancelledError:
        pass
    return max(tre) if tre else 0.0


tre_max = asyncio.run(do_do_tre())
print(f"     (độ trễ nhịp tim lớn nhất trong lúc quét: {tre_max:.0f} ms)")
check(f"event loop không bị khoá quá 150ms khi quét brain 3000 note ({tre_max:.0f} ms)",
      tre_max < 150)

# ---- 5. Một brain hỏng không giết cả danh sách ----
that_count = main._count_md


def _count_no(root, cap):
    if "Brain A" in str(root):
        raise OSError("giả lập ổ đĩa lỗi")
    return that_count(root, cap)


try:
    main._count_md = _count_no
    r3 = goi()
    ten3 = {b["name"]: b for b in r3["brains"]}
    check("một brain lỗi khi đếm vẫn được liệt kê (notes=0)",
          "Brain A" in ten3 and ten3["Brain A"]["notes"] == 0)
    check("các brain khác vẫn đếm bình thường", ten3["Brain B"]["notes"] == 3)
finally:
    main._count_md = that_count

print()
if _fails:
    print(f"FAIL {len(_fails)} test: " + ", ".join(_fails))
    sys.exit(1)
print("TẤT CẢ PASS")
