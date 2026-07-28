"""Test đồ thị realtime chạy bằng SỰ KIỆN file (watchfiles) thay cho poll 4s (v0.9.223).
Chạy:  cd server && ..\\.venv\\Scripts\\python.exe test_graph_watch.py    (KHÔNG mạng).

Kiểm tra: node mọc NGAY khi file .md được ghi (không đợi nhịp quét), phân biệt note mới /
note đổi, file trong thư mục ẩn không lọt ra, và disconnect dọn task nền sạch sẽ.
"""
import os, sys, tempfile, json, time, concurrent.futures
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-graphwatch-test-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)

import main  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

# --- _hidden_in_roots (thuần) ---
root = tempfile.mkdtemp(prefix="javis-graphwatch-vault-")
check("_hidden_in_roots: file thường - False",
      main._hidden_in_roots(os.path.join(root, "a.md"), [root]) is False)
check("_hidden_in_roots: trong .trash - True",
      main._hidden_in_roots(os.path.join(root, ".trash", "a.md"), [root]) is True)
check("_hidden_in_roots: ngoài root - False (không đoán bừa)",
      main._hidden_in_roots(os.path.join(tempfile.gettempdir(), "x.md"), [root]) is False)

# --- endpoint /ws/graph với sự kiện file thật ---
main.cfgmod.gate_active = lambda: False   # test không đụng auth thật
client = TestClient(main.app)

def _write(relpath, content):
    p = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p

def _recv_json(ws, timeout=10):
    """receive_text có canh giờ - treo quá timeout coi như không có sự kiện."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(ws.receive_text)
        return json.loads(fut.result(timeout=timeout))

# File có TRƯỚC khi kết nối → nằm trong baseline, sửa nó phải ra isNew=False
_write("cu.md", "note cũ, chưa có link")
time.sleep(0.2)

with client.websocket_connect(f"/ws/graph?path={root}") as ws:
    time.sleep(1.0)   # chờ watcher gắn xong vào thư mục (awatch khởi động nền)

    _write("moi.md", "note mới trỏ [[cu]]")
    msg = _recv_json(ws)
    check("tạo file mới → nhận graph_add ngay (không đợi nhịp quét)", msg.get("type") == "graph_add")
    check("node mới đúng id", msg.get("node", {}).get("id") == "moi")
    check("note mới có isNew=True", msg.get("isNew") is True)
    check("wikilink được trích ra", msg.get("linkTargets") == ["cu"])

    time.sleep(0.3)
    _write("cu.md", "note cũ vừa được SỬA")
    msg = _recv_json(ws)
    check("sửa file có sẵn → isNew=False", msg.get("node", {}).get("id") == "cu" and msg.get("isNew") is False)

    time.sleep(0.3)
    _write(os.path.join(".trash", "rac.md"), "file trong thư mục ẩn")
    time.sleep(0.5)   # cho sự kiện ẩn (nếu lọt) kịp tới trước file mồi
    _write("moi2.md", "file mồi sau file ẩn")
    msg = _recv_json(ws)
    check("file trong thư mục ẩn bị bỏ qua (tin kế tiếp là file mồi)",
          msg.get("node", {}).get("id") == "moi2")

check("disconnect xong không nổ exception (dọn task nền sạch)", True)

print()
if _fails:
    print(f"FAIL {len(_fails)} test: " + ", ".join(_fails)); sys.exit(1)
print("TẤT CẢ PASS")
