"""Không code nội bộ nào được gọi thẳng một route handler như hàm Python thường.

    python tests/run.py handler_khong_goi_truc_tiep     (KHÔNG mạng)

Bối cảnh 0.9.243: khối Telegram gọi thẳng 5 handler (`await list_agents(brain)`,
`await provider_models(provider=pid)`, `await list_brains()`, `await list_skills(brain)`,
`await list_workflows(brain)` - 6 chỗ). Chạy được nên không ai thấy, nhưng đó là bom hẹn giờ:
tham số mặc định của handler là ĐỐI TƯỢNG `fastapi.params.Query`, không phải chuỗi. Ngày nào
có người gọi thiếu đối số thì `brain` thành một Query object, `_brain_root` nhận vào rồi
`os.path.isdir(Query)` ném TypeError - và nó nổ ở Telegram chứ không ở chỗ vừa sửa.

Cách chữa đã áp dụng: handler chỉ còn là lớp vỏ HTTP mỏng bọc quanh một hàm THUẦN
(`agents_index`, `workflows_index`, `skills_index`, `provider_models_index`,
`_list_brains_sync`), và nội bộ gọi hàm thuần đó.

Test này quét bằng AST nên bắt được cả các khối khác, không chỉ Telegram.
"""
import ast
import sys

from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


HTTP = {"get", "post", "put", "delete", "patch", "websocket"}


def quet(path):
    """(tên handler -> dòng khai báo, danh sách lời gọi nội bộ tới các tên đó)."""
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(path))
    handlers = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            f = dec.func if isinstance(dec, ast.Call) else dec
            # bắt cả @app.get(...) lẫn @router.get(...)
            if isinstance(f, ast.Attribute) and f.attr in HTTP:
                handlers[node.name] = node.lineno
    goi = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        ten = fn.id if isinstance(fn, ast.Name) else None
        if ten and ten in handlers:
            goi.append((ten, node.lineno))
    return handlers, goi


FILES = [SERVER / "main.py"] + sorted((SERVER / "routes").glob("*.py"))
tong_h = 0
vi_pham = []
for f in FILES:
    handlers, goi = quet(f)
    tong_h += len(handlers)
    for ten, dong in goi:
        vi_pham.append(f"{f.name}:{dong} gọi {ten}() (khai báo dòng {handlers[ten]})")

check(f"quét được {tong_h} route handler trong {len(FILES)} file", tong_h > 100)
check("không chỗ nào gọi route handler như hàm thường"
      + ("\n       " + "\n       ".join(vi_pham) if vi_pham else ""), not vi_pham)

# ---- Các hàm lõi phải tồn tại và gọi được KHÔNG cần đối số kiểu FastAPI ----
import main  # noqa: E402

for ten in ("agents_index", "workflows_index", "skills_index", "_list_brains_sync"):
    check(f"main.{ten} tồn tại (lõi thuần cho nội bộ dùng)", callable(getattr(main, ten, None)))
check("main.provider_models_index tồn tại", callable(getattr(main, "provider_models_index", None)))

# Gọi thật với chuỗi thường - đây chính là thứ trước đây sẽ nổ nếu ai đó gọi handler thiếu đối số.
for ten in ("agents_index", "workflows_index", "skills_index"):
    try:
        getattr(main, ten)("brain")
        ok = True
    except Exception as e:
        ok = False
        print(f"       {ten} lỗi: {type(e).__name__}: {e}")
    check(f"{ten}('brain') chạy được với chuỗi thường", ok)

print()
if _fails:
    print(f"FAIL {len(_fails)} test: " + ", ".join(_fails))
    sys.exit(1)
print("TẤT CẢ PASS")
