"""Bộ icon Lucide: chặn icon vô hình và chặn emoji bò trở lại giao diện.

Hai lỗi test này canh, đều là loại KHÔNG thấy bằng mắt khi review code:

1. Gõ sai tên icon -> ic() trả về dấu hỏi và chỉ cảnh báo trong console. Trên
   máy thật thì lọt qua rất dễ, nên đối chiếu mọi tên gọi trong nguồn với bộ
   icon đã vendor.

2. Emoji bò trở lại. Cả dashboard đã bỏ emoji để icon tự đổi màu theo tông
   SÁNG/TỐI và vẽ giống nhau trên mọi máy. Một lần thêm "canh bao ..." kèm
   emoji cho nhanh là phá lại thành quả đó, nên quét thẳng vào nguồn.

3. Nhét chuỗi icon vào .textContent. Emoji thì textContent hiện ra bình thường,
   còn icon là thẻ <svg> nên user đọc nguyên mã nguồn trên màn hình. Đây là cái
   bẫy riêng của đợt di trú: đổi nội dung sang icon mà quên đổi textContent
   thành innerHTML. Mắt người review rất khó thấy, nên quét bằng test.
"""
import bisect
import json
import re

from _paths import ROOT  # noqa: E402,F401

DASH = ROOT / "dashboard"
MANIFEST = json.loads((DASH / "icons.manifest.json").read_text(encoding="utf-8"))
VENDOR = (DASH / "vendor" / "lucide-icons.js").read_text(encoding="utf-8")
VENDOR_CSS = (DASH / "vendor" / "lucide-icons.css").read_text(encoding="utf-8")
ICONS_JS = (DASH / "icons.js").read_text(encoding="utf-8")
INDEX = (DASH / "index.html").read_text(encoding="utf-8")
STYLE = (DASH / "style.css").read_text(encoding="utf-8")

fails = []


def check(name: str, condition: bool) -> None:
    print(("PASS: " if condition else "FAIL: ") + name)
    if not condition:
        fails.append(name)


# --- Nguồn cần quét: đúng những file dựng nên giao diện app. ------------------
# Bỏ vendor/ (mã của người khác), bỏ docs/ và voice-test.html (trang lẻ đứng
# riêng, không phải giao diện Javis).
SCAN = sorted(p for p in DASH.glob("*.js")) + [INDEX and DASH / "index.html"]
SCAN += [DASH / "style.css", DASH / "console.css"]
SCAN = [p for p in SCAN if p.is_file() and p.name != "icons.js"]

# Emoji màu + ký hiệu đang đóng vai icon. Không gồm mũi tên -> dùng trong câu
# văn ("Hostinger -> App terminal") và dấu gạch/chấm đầu dòng.
EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # emoji màu
    "☀-➿"          # ký hiệu lặt vặt + dingbat
    "⬀-⯿"          # mũi tên/hình khối bổ sung
    "⌀-⏿"          # ký hiệu kỹ thuật
    "️"                 # bộ chọn biến thể màu
    "]"
)

# Ngoại lệ có lý do, ghi rõ từng cái. Danh sách này phải NGẮN và không được
# phình ra: mỗi dòng thêm vào là một chỗ giao diện lệch máy.
#
# CHỈ có một lý do được chấp nhận: ký tự đó là ĐỊNH DẠNG DỮ LIỆU chứ không phải
# icon. task-suggest.js chèn thẳng các dấu này vào file .md theo cú pháp
# Obsidian Tasks, nên đổi là Obsidian không đọc được nữa và
# test_dataview_tasks.py sẽ đổ. Phần HIỂN THỊ của chính bảng đó đã dùng icon
# Lucide (trường menuIcon) - hai thứ tách bạch, đúng như thiết kế.
ALLOW = {
    ("task-suggest.js", "\U0001F4C5"),   # ngày hạn chót
    ("task-suggest.js", "⏳"),       # ngày dự kiến
    ("task-suggest.js", "\U0001F6EB"),   # ngày bắt đầu
    ("task-suggest.js", "⏫"),       # ưu tiên cao
    ("task-suggest.js", "\U0001F53C"),   # ưu tiên vừa
    ("task-suggest.js", "\U0001F53D"),   # ưu tiên thấp
}


# Chuỗi trả về từ tầng icon: ic(...), Icons.msg/warn/ok, và các hằng *_ICON
# dựng sẵn ở đầu console.js. Tất cả đều là HTML.
ICON_EXPR = re.compile(r"\bic\(|\bIcons\.(?:msg|warn|ok)\(|\b[A-Z][A-Z0-9_]*_ICON\b")
ASSIGN_TEXT = re.compile(r"\.textContent\s*\+?=\s*")
# Bắt buộc có khoảng trắng hai bên dấu "=" để không nhặt phải thuộc tính HTML
# nằm trong chuỗi (vd rel="noopener") - thứ luôn viết liền không có khoảng trắng.
ASSIGN_ANY = re.compile(r"\b([A-Za-z_$][\w$]*)\s\+?=\s[^=]")
BARE_VAR = re.compile(r"^([A-Za-z_$][\w$]*)$")


def _stmt_at(lines, i, start):
    """Lấy câu lệnh từ vị trí start của dòng i, nối tối đa 3 dòng nếu chưa đóng."""
    stmt = lines[i][start:]
    for nxt in lines[i + 1:i + 4]:
        if ";" in stmt:
            break
        stmt += " " + nxt
    return stmt.split(";")[0]


DONG_NGOAC = {"[": "]", "(": ")", "{": "}"}


def _khoi_can(src, mo):
    """Cắt khối cân ngoặc bắt đầu tại src[mo] (mở bằng [ ( hoặc {).

    Phải BỎ QUA ngoặc nằm trong chuỗi, vì bảng nút thật có dòng
    wrapTa("[", "](" + u + ")") - đếm thô là cắt cụt ngay giữa bảng.
    Trả về (nguyên văn khối, vị trí ngay sau dấu đóng).
    """
    mo_c = src[mo]
    dong_c = DONG_NGOAC[mo_c]
    sau, nhay, bo_qua = 0, "", False
    for j in range(mo, len(src)):
        c = src[j]
        if bo_qua:                 # ký tự ngay sau dấu \ trong chuỗi: nuốt luôn,
            bo_qua = False         # nếu không thì \" bị hiểu là đóng chuỗi
            continue
        if nhay:
            if c == "\\":
                bo_qua = True
            elif c == nhay:
                nhay = ""
            continue
        if c in "\"'`":
            nhay = c
            continue
        if c == mo_c:
            sau += 1
        elif c == dong_c:
            sau -= 1
            if sau == 0:
                return src[mo:j + 1], j + 1
    return src[mo:], len(src)


# Rã mảng lấy tên ngay trên tham số callback: BTNS.forEach(([label, title]) => ...).
# Bắt cả dấu "(" của .forEach để còn khoanh được THÂN callback - tên kiểu label/title
# dùng lại khắp file, chỉ được tính là icon bên trong đúng vòng lặp đó.
# Chưa canh: dạng for (const [label] of BTNS) - chưa file nào viết vậy.
RA_MANG_LAP = r"\.(?:forEach|map|flatMap|filter|some|every)\s*(\()\s*(?:async\s*)?\(?\s*\[([^\]]*)\]"
TEN_TRONG_MAU = re.compile(r"[A-Za-z_$][\w$]*")


def _so_dong(dau_dong, vi_tri):
    """Offset ký tự -> số dòng (đếm từ 0)."""
    return bisect.bisect_right(dau_dong, vi_tri) - 1


def scan_text_content():
    """Tìm chỗ gán HTML icon vào .textContent (phải là .innerHTML).

    Ba lối lọt, canh cả ba:
    - Icon nằm NGAY trong câu lệnh gán. Quét theo CÂU LỆNH chứ không theo dòng,
      vì nhiều chỗ viết ternary trải 3 dòng, icon ở dòng dưới dấu "=".
    - Icon nằm trong BIẾN dựng ở trên rồi mới gán (vd `line = ic(...)` ... rồi
      `st.textContent = line`). Đây đúng là chỗ đã lọt thật ở thẻ Telegram.
    - Icon nằm trong BẢNG DỮ LIỆU rồi rã mảng ra biến (vd `const BTNS = [[ic(..),
      ...]]` rồi `BTNS.forEach(([label]) => b.textContent = label)`). Đây là
      đường lọt thật của thanh công cụ sửa file .md ở 0.9.257: nhãn nút thành
      chuỗi <svg> mà lệnh gán vẫn nguyên textContent, nên user đọc mã nguồn
      hiện ra giữa thanh công cụ. Tên rã ra chỉ tính TRONG THÂN callback đó,
      vì label/title là tên chung, dùng lại chỗ khác với chữ thuần là bình thường.

    Chưa canh được: icon truyền qua THAM SỐ hàm phụ (vd một hàm mk(label) tự
    gán label vào textContent). Chỗ đó phải tự nhớ khi viết hàm nhận HTML.
    """
    hits = []
    for path in SCAN:
        if path.suffix != ".js":
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        dau_dong, chay = [0], 0
        for line in lines:
            chay += len(line) + 1
            dau_dong.append(chay)

        # Vòng 1: biến nào từng nhận chuỗi icon.
        icon_vars = set()
        for i, line in enumerate(lines):
            for m in ASSIGN_ANY.finditer(line):
                if ICON_EXPR.search(_stmt_at(lines, i, m.end() - 1)):
                    icon_vars.add(m.group(1))

        # Vòng 1b: bảng dữ liệu có icon -> tên rã ra từ bảng, chỉ tính trong thân vòng lặp.
        vung = []   # (dòng đầu, dòng cuối, {tên})
        for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\[", text):
            bang, _ = _khoi_can(text, m.end() - 1)
            if not ICON_EXPR.search(bang):
                continue
            for mau in re.finditer(re.escape(m.group(1)) + RA_MANG_LAP, text):
                _, het = _khoi_can(text, mau.start(1))
                vung.append((_so_dong(dau_dong, mau.start(1)), _so_dong(dau_dong, het - 1),
                             set(TEN_TRONG_MAU.findall(mau.group(2)))))

        # Vòng 2: chỗ gán vào textContent - icon trực tiếp hoặc qua biến trên.
        for i, line in enumerate(lines):
            m = ASSIGN_TEXT.search(line)
            if not m:
                continue
            stmt = _stmt_at(lines, i, m.end())
            bare = BARE_VAR.match(stmt.strip())
            ten = bare.group(1) if bare else None
            trong_bang = ten and any(d0 <= i <= d1 and ten in ts for d0, d1, ts in vung)
            if ICON_EXPR.search(stmt) or (ten and ten in icon_vars) or trong_bang:
                hits.append((path.name, i + 1, line.strip()[:90]))
    return hits


def scan_emoji():
    hits = []
    for path in SCAN:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for glyph in EMOJI.findall(line):
                if (path.name, glyph) in ALLOW:
                    continue
                hits.append((path.name, lineno, glyph, line.strip()[:70]))
    return hits


# --- 1. Bộ icon đã vendor khớp manifest --------------------------------------
want = sorted({n for group in MANIFEST["groups"].values() for n in group})
have = sorted(set(re.findall(r'^\s*"([a-z0-9-]+)":\s*"', VENDOR, re.M)))

check(f"manifest có icon ({len(want)} tên)", len(want) > 50)
check("vendor có đủ mọi icon trong manifest", set(want) <= set(have))
check("vendor không chứa icon thừa ngoài manifest", set(have) <= set(want))
check("vendor ghi rõ là file tự sinh", "FILE TỰ SINH" in VENDOR)
check("vendor ghi rõ nguồn và giấy phép", "lucide-static" in VENDOR and "ISC" in VENDOR)

# --- 2. Mọi tên icon gọi trong nguồn đều có thật -----------------------------
used = set()
for path in SCAN:
    text = path.read_text(encoding="utf-8")
    used |= set(re.findall(r'\bic\(\s*["\']([a-z0-9-]+)["\']', text))
    used |= set(re.findall(r'\bmsg\(\s*["\']([a-z0-9-]+)["\']', text))
    used |= set(re.findall(r'data-ic=["\']([a-z0-9-]+)["\']', text))

unknown = sorted(used - set(have))
check(f"mọi tên icon gọi trong nguồn đều có trong vendor (đang gọi {len(used)} tên)",
      not unknown)
if unknown:
    print("      tên không có thật: " + ", ".join(unknown))

# --- 3. Tầng API dựng đúng ---------------------------------------------------
check("icons.js phơi hàm ic ra toàn cục", "window.ic = ic" in ICONS_JS)
check("icons.js có Icons.msg để escape chữ từ server",
      "function msg(" in ICONS_JS and "esc(text)" in ICONS_JS)
check("icons.js có render() thay data-ic trong HTML tĩnh",
      "function render(" in ICONS_JS and "[data-ic]" in ICONS_JS)
check("icon thiếu thì cảnh báo ra console chứ không im lặng",
      "console.warn" in ICONS_JS)
check("icon mặc định ẩn khỏi trình đọc màn hình",
      'aria-hidden="true"' in ICONS_JS)
check("icon dùng currentColor để tự đổi màu theo tông",
      'stroke="currentColor"' in ICONS_JS)

# --- 4. Thứ tự nạp trong index.html -----------------------------------------
pos_vendor = INDEX.find("vendor/lucide-icons.js")
pos_api = INDEX.find("static/icons.js")
pos_theme = INDEX.find("static/theme.js")
check("index.html nạp bộ icon", pos_vendor > 0 and pos_api > 0)
check("dữ liệu icon nạp trước tầng API", 0 < pos_vendor < pos_api)
check("bộ icon nạp trước mọi file dùng nó", 0 < pos_api < pos_theme)

# --- 5. CSS của icon --------------------------------------------------------
check("style.css có lớp .ic", ".ic {" in STYLE)
check("icon co theo cỡ chữ chứ không cứng px",
      "width: 1em;" in STYLE and "height: 1em;" in STYLE)
check("icon canh theo đường chân chữ", "vertical-align: -0.14em;" in STYLE)
check("có lớp tô đặc cho đèn trạng thái", ".ic-fill { fill: currentColor; }" in STYLE)
check("icon quay tôn trọng prefers-reduced-motion",
      "prefers-reduced-motion" in STYLE and ".ic-spin { animation: none; }" in STYLE)

# --- 5b. Icon trong ngữ cảnh chỉ CSS với tới được (content của ::before) -----
# Thẻ SVG không nhét vào content: được, nên dùng mặt nạ + biến data URI.
css_declared = set(re.findall(r"--ic-([a-z0-9-]+):", VENDOR_CSS))
# Quét cả nguồn: console.js cũng nhúng CSS lúc chạy và dùng các biến này.
css_used = set()
for path in SCAN:
    css_used |= set(re.findall(r"var\(--ic-([a-z0-9-]+)\)", path.read_text(encoding="utf-8")))
check("file biến CSS được sinh ra", "FILE TỰ SINH" in VENDOR_CSS and css_declared)
check(f"mọi biến --ic-* dùng trong nguồn đều có thật (đang dùng {len(css_used)})",
      css_used <= css_declared)
if css_used - css_declared:
    print("      biến thiếu: " + ", ".join(sorted(css_used - css_declared)))
check("mặt nạ giữ được currentColor thay vì màu cứng",
      "background-color: currentColor;" in STYLE)
check("có tiền tố -webkit- cho mask (Safari)",
      "-webkit-mask" in STYLE and STYLE.count("-webkit-mask") >= 2)
pos_vencss = INDEX.find("vendor/lucide-icons.css")
pos_style = INDEX.find("static/style.css")
check("biến CSS nạp TRƯỚC style.css (style.css tham chiếu chúng)",
      0 < pos_vencss < pos_style)

# --- 6. Emoji không được bò trở lại -----------------------------------------
hits = scan_emoji()
check(f"không còn emoji trong giao diện dashboard (thấy {len(hits)})", not hits)
if hits:
    by_file = {}
    for fname, lineno, glyph, snippet in hits:
        by_file.setdefault(fname, []).append((lineno, glyph, snippet))
    for fname in sorted(by_file, key=lambda k: -len(by_file[k])):
        rows = by_file[fname]
        print(f"      {fname}: {len(rows)} chỗ")
        for lineno, glyph, snippet in rows[:4]:
            print(f"        {lineno}: {glyph} | {snippet}")
        if len(rows) > 4:
            print(f"        ... thêm {len(rows) - 4} chỗ")

# --- 7. Không gán HTML icon vào textContent ----------------------------------
tc_hits = scan_text_content()
check(f"không nhét thẻ <svg> icon vào .textContent (thấy {len(tc_hits)})", not tc_hits)
for fname, lineno, snippet in tc_hits:
    print(f"      {fname}:{lineno} - phải đổi sang .innerHTML | {snippet}")

if fails:
    raise SystemExit(f"\nFAIL - test_icons: {len(fails)} lỗi")
print("\nOK - test_icons: tất cả pass")
