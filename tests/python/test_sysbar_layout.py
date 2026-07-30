"""Regression: dòng HỆ THỐNG/MCP không được làm nở cockpit và đẩy cột chat ra ngoài."""
from _paths import ROOT, SERVER  # noqa: E402,F401


STYLE = (ROOT / "dashboard" / "style.css").read_text(encoding="utf-8")
CONSOLE_CSS = (ROOT / "dashboard" / "console.css").read_text(encoding="utf-8")
APP = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

fails = []


def check(name: str, condition: bool) -> None:
    print(("PASS: " if condition else "FAIL: ") + name)
    if not condition:
        fails.append(name)


track_block = APP.split("function trackMCP(toolName)", 1)[1].split(
    "// ============================================", 1
)[0]

check("cột graph được phép co dưới min-content của canvas",
      "grid-template-columns: 260px minmax(0, 1fr) 320px;" in STYLE)
check("mọi hàng trực tiếp của HUD không ép rộng grid", ".hud > * { min-width: 0; }" in STYLE)
check("model bar tự chặn tràn ngang",
      ".model-bar {" in STYLE and "width: 100%; max-width: 100%; min-width: 0;" in STYLE
      and "padding: 8px 18px 6px; overflow: hidden;" in STYLE)
check("sysbar co theo phần rộng còn lại",
      "flex: 1 1 0; width: 0; min-width: 0; max-width: 100%;" in STYLE)
check("danh sách MCP tự cắt trong vùng của nó",
      ".sysbar .mcp-list {" in STYLE and "flex: 1 1 0; width: 0; min-width: 0;" in STYLE
      and "text-overflow: ellipsis;" in STYLE)
check("câu lệnh shell chỉ hiện nhãn Terminal", 'label: "Terminal", cat: "Local"' in APP)
check("status chỉ giữ tối đa bốn loại tool", "while (usedMCPs.size > 4)" in track_block)
check("nhãn tool không chèn HTML thô", "div.innerHTML" not in track_block)
check("sysbar trong drawer mobile lấy lại đủ chiều rộng",
      ".rail-sys .sysbar {" in CONSOLE_CSS
      and "display: flex; flex: none; width: 100%; min-width: 0; max-width: 100%;" in CONSOLE_CSS)
check("cache bust CSS và app đã tăng",
      'style.css?v=52' in INDEX and 'console.css?v=31' in INDEX and 'app.js?v=73' in INDEX)

if fails:
    raise SystemExit(f"\nFAIL - test_sysbar_layout: {len(fails)} lỗi")
print("\nOK - test_sysbar_layout: tất cả pass")
