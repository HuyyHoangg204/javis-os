"""Plugin bundled (THỬ NGHIỆM): tự động hoá Facebook CÁ NHÂN bằng cookie phiên.

Facebook đã đóng API cho tài khoản cá nhân (đọc feed, đăng tường) từ lâu, nên đi đường cookie:
gọi mbasic.facebook.com (bản HTML nhẹ) bằng httpx + cookie phiên của kết nối "facebook-personal".
Chạy được headless trên VPS (chỉ cần cookie, KHÔNG cần mở trình duyệt / Chromium).

QUAN TRỌNG - User-Agent: mbasic là site cho TRÌNH DUYỆT DI ĐỘNG thật; gửi UA lạ (desktop, hoặc
Firefox mobile) sẽ bị đẩy sang trang "Trình duyệt không hỗ trợ, tải Facebook Lite" thay vì feed.
Nên mặc định dùng UA iPhone Safari, tự thử vài UA di động nếu bị chê, và cho user dán UA riêng
(khớp UA với trình duyệt nơi lấy cookie là chắc nhất) qua field 'user_agent' của kết nối.

CẢNH BÁO: vi phạm điều khoản Facebook, RỦI RO KHOÁ TÀI KHOẢN. Cookie = chìa khoá toàn quyền tài
khoản (lưu mã hoá). Tool đọc feed = readonly; đăng bài + bình luận = min_mode full nên không tự
chạy ở chế độ suggest/auto. mbasic có thể bị Facebook đổi/đóng → bộ tìm form là BEST-EFFORT.
"""
from __future__ import annotations

import html as _html
import json
import re
from urllib.parse import urlsplit

BASE = "https://mbasic.facebook.com"
CONNECTOR_ID = "facebook-personal"

# mbasic chỉ nhả HTML cho UA di động thật. iPhone Safari là UA nhận được mbasic ổn nhất; kèm
# vài UA dự phòng để tự đổi khi bị chê. User có thể ghi đè bằng field user_agent của kết nối.
_DEFAULT_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]


def _secrets():
    try:
        import mcp_store
    except Exception:
        return {}
    cid = _connected_id()
    if not cid:
        return {}
    return mcp_store.connection_secrets(cid) or {}


def _connected_id():
    try:
        import mcp_store
    except Exception:
        return None
    for c in mcp_store.list_connections():
        if c.get("connector_id") == CONNECTOR_ID:
            return c["id"]
    return None


def _cookie():
    ck = (_secrets().get("cookie") or "").strip()
    if ck.lower().startswith("cookie:"):
        ck = ck.split(":", 1)[1].strip()
    return ck or None


def _uas():
    """UA để thử, theo thứ tự: UA user tự khai (nếu có) rồi tới các UA mặc định."""
    lst = []
    override = (_secrets().get("user_agent") or "").strip()
    if override:
        lst.append(override)
    for u in _DEFAULT_UAS:
        if u not in lst:
            lst.append(u)
    return lst


def _check():
    if not _cookie():
        return ("Chưa kết nối Facebook cá nhân. Vào trang Kết nối, chọn 'Facebook cá nhân (cookie)', "
                "dán cookie phiên theo hướng dẫn. Sau đó gọi lại tool này.")
    return None


def _client(cookie, ua):
    import httpx
    return httpx.AsyncClient(timeout=30, follow_redirects=True,
                             headers={"Cookie": cookie, "User-Agent": ua,
                                      "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})


def _abs(u):
    if u.startswith("http"):
        return u
    return BASE + ("" if u.startswith("/") else "/") + u


async def _get(client, url):
    r = await client.get(_abs(url))
    return r.text, str(r.url)


async def _post(client, action, data):
    r = await client.post(_abs(action), data=data)
    return r.text, str(r.url)


def _blocked(url):
    u = (url or "").lower()
    return "login" in u or "checkpoint" in u


def _off_mbasic(url):
    """True nếu request bị chuyển hướng RA KHỎI mbasic (sang m./www.facebook.com). Đây là dấu
    hiệu Facebook đã NGỪNG phục vụ mbasic cho phiên/khu vực này (mbasic đang bị khai tử dần),
    khác hẳn lỗi cookie - cookie có thể vẫn tốt mà mbasic vẫn chết."""
    host = urlsplit(url or "").netloc.lower()
    return bool(host) and "facebook.com" in host and not host.endswith("mbasic.facebook.com")


def _unsupported(page):
    """Trang 'Trình duyệt không hỗ trợ, tải Facebook Lite' mà mbasic trả khi chê UA."""
    return bool(re.search(r"không hỗ trợ|browser is not supported|isn'?t compatible|"
                          r"tải Facebook Lite|Get Facebook Lite|Nâng cấp trình duyệt|Update your browser",
                          page or "", re.I))


_LOGIN_TITLE_RE = re.compile(
    r"Đăng nhập hoặc đăng ký|Log in or sign up|Log Into Facebook|Đăng nhập vào Facebook|"
    r"You must log in|Bạn (?:cần|phải) đăng nhập", re.I)
_LOGIN_ACTION_RE = re.compile(r'<(?:form|a)\b[^>]*(?:action|href)="[^"]*/(?:login|checkpoint)', re.I)


def _is_login(page):
    """Trang ĐĂNG NHẬP / WELCOME (cookie bị từ chối). Bắt RỘNG theo NỘI DUNG: khi cookie bị đá
    ra, mbasic (hoặc m.facebook.com khi bị chuyển hướng) hay trả trang splash 'Đăng nhập hoặc
    đăng ký' ở URL KHÔNG chứa 'login' và KHÔNG có sẵn ô email/mật khẩu trong HTML (chỉ nút +
    tiêu đề). Phải bắt được, nếu không trang đăng nhập bị trả nhầm thành feed."""
    p = page or ""
    if (re.search(r'<input[^>]*type="password"', p, re.I)
            or re.search(r'<input[^>]*name="(?:pass|encpass)"', p, re.I)):
        return True                          # có ô mật khẩu = chắc chắn form đăng nhập
    if _LOGIN_ACTION_RE.search(p):           # form/nút dẫn tới /login hoặc /checkpoint
        return True
    if _LOGIN_TITLE_RE.search(p):            # tiêu đề trang đăng nhập / splash
        return True
    return False


_COOKIE_HELP = ("ERROR: Facebook trả trang ĐĂNG NHẬP - cookie đang bị từ chối, không đọc được feed. "
                "Thường do: (1) cookie đã hết hạn / bạn đã đăng xuất trình duyệt gốc - đừng logout sau khi "
                "copy, và lấy cookie MỚI ngay trước khi thử; (2) Javis đang chạy ở IP/máy KHÁC nơi bạn đăng "
                "nhập (VPS, khác nước) nên Facebook chặn phiên vì 'đăng nhập lạ' - chạy Javis cùng máy/mạng "
                "nơi đăng nhập, hoặc đăng nhập Facebook từ chính IP của VPS; (3) tài khoản đang bị checkpoint - "
                "mở trình duyệt xác minh xong rồi lấy lại cookie. Kiểm tra cookie có đủ cả c_user và xs.")


_MBASIC_GONE = ("ERROR: Facebook CHUYỂN HƯỚNG khỏi mbasic sang m.facebook.com - nhiều khả năng "
                "mbasic.facebook.com (bản HTML nhẹ mà công cụ này dựa vào) đã bị Facebook NGỪNG PHỤC VỤ "
                "cho tài khoản/khu vực của bạn. Cookie của bạn nhiều khả năng VẪN TỐT (vẫn đăng nhập được "
                "trên m.facebook.com), nên đây KHÔNG phải lỗi cookie và đổi cookie cũng không cứu được. Muốn "
                "đọc feed / thao tác tài khoản cá nhân lúc này cần trình duyệt thật (Playwright/Chromium) chạy "
                "m.facebook.com, hoặc chuyển sang nguồn được hỗ trợ: Trang qua Graph API, theo dõi công khai "
                "qua Apify.")


_UA_HELP = ("mbasic chê trình duyệt ('không hỗ trợ, tải Facebook Lite') với mọi User-Agent thử. "
            "Cách sửa: mở kết nối Facebook cá nhân, dán vào ô 'User-Agent' đúng UA của trình duyệt "
            "nơi bạn lấy cookie (tra 'my user agent' trên trình duyệt đó). Tốt nhất lấy cookie từ "
            "trình duyệt DI ĐỘNG (điện thoại) rồi dán cả UA di động đó.")


async def _fetch(cookie, url):
    """GET url, tự đổi UA nếu mbasic chê. Trả (page, final_url, ua_dùng, err_str)."""
    last_url = ""
    off_mbasic_seen = False
    for ua in _uas():
        try:
            async with _client(cookie, ua) as c:
                page, furl = await _get(c, url)
        except Exception as e:
            return None, "", ua, f"ERROR: không tải được ({type(e).__name__}: {e})."
        if _off_mbasic(furl):
            off_mbasic_seen = True        # bị đá sang m./www.facebook.com; thử UA khác xem có UA nào còn ở lại mbasic
            last_url = furl
            continue
        if _blocked(furl) or _is_login(page):
            return None, furl, ua, _COOKIE_HELP     # cookie bị từ chối - đổi UA không cứu được
        if _unsupported(page):
            last_url = furl
            continue                      # thử UA kế tiếp
        return page, furl, ua, None
    if off_mbasic_seen:                    # không UA nào ở lại được mbasic → mbasic đã ngừng phục vụ
        return None, last_url, None, _MBASIC_GONE
    return None, last_url, None, "ERROR: " + _UA_HELP


_STORY_LINK_RE = re.compile(r'href="(/story\.php\?[^"]+|/[^"]*permalink[^"]*|/[^"]*\?story_fbid=[^"]+)"')


async def _feed(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    try:
        limit = max(500, min(20000, int(args.get("max_chars") or 6000)))
    except (TypeError, ValueError):
        limit = 6000
    try:
        pages = max(1, min(5, int(args.get("pages") or 1)))
    except (TypeError, ValueError):
        pages = 1
    cur = str(args.get("next_url") or args.get("start_url") or "/").strip() or "/"
    texts, links, next_url, src, visited = [], [], None, None, set()
    for _i in range(pages):
        if cur in visited:
            break
        visited.add(cur)
        page, url, _ua, err = await _fetch(ck, cur)
        if err:
            if texts:      # đã lấy được ít nhất 1 trang thì trả phần đó, đừng vứt hết
                break
            return err
        if src is None:
            src = url
        for href in _STORY_LINK_RE.findall(page):
            u = _html.unescape(href)
            if u not in links:
                links.append(u)
        texts.append(_strip(page))
        next_url = _find_link(page, ["Xem thêm câu chuyện", "Câu chuyện cũ hơn", "Xem thêm",
                                     "See more stories", "See more", "Older stories"])
        if not next_url:
            break
        cur = next_url
    text = "\n".join(texts)
    if len(text) > limit:
        text = text[:limit] + "…"
    return json.dumps({"feed_text": text, "post_links": links[:50],
                       "next_url": next_url, "source": src}, ensure_ascii=False)


async def _publish(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    msg = str((args or {}).get("message") or "").strip()
    if not msg:
        return "ERROR: thiếu 'message' (nội dung bài đăng)."
    home, _url, ua, err = await _fetch(ck, "/")
    if err:
        return err
    action, fields, ta = _find_form(home, ["xc_message", "status", "text"])
    if not action or not ta:
        return ("ERROR: Không tìm thấy ô soạn bài trên mbasic (Facebook có thể đã đổi/đóng mbasic). "
                "Cần chỉnh lại selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua) as c:
            _res, rurl = await _post(c, action, {**fields, ta: msg})
    except Exception as e:
        return f"ERROR: đăng bài lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi đăng (login/checkpoint) - cookie yếu hoặc bị nghi tự động."
    return json.dumps({"ok": True, "action": "post",
                       "note": "Đã gửi yêu cầu đăng lên tường. Kiểm tra lại trang cá nhân để chắc chắn."},
                      ensure_ascii=False)


async def _comment(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    msg = str(args.get("message") or "").strip()
    post = str(args.get("post_url") or args.get("post_id") or "").strip()
    if not msg:
        return "ERROR: thiếu 'message' (nội dung bình luận)."
    if not post:
        return "ERROR: thiếu 'post_url' (link bài mbasic, lấy từ fb_feed_read) hoặc 'post_id'."
    if post.isdigit():
        post = f"/story.php?story_fbid={post}"
    page, _url, ua, err = await _fetch(ck, post)
    if err:
        return err
    action, fields, ta = _find_form(page, ["comment_text", "comment"])
    if not action or not ta:
        return ("ERROR: Không tìm thấy ô bình luận trên bài này (mbasic đổi/đóng, hoặc bài không cho "
                "bình luận). Cần chỉnh lại selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua) as c:
            _res, rurl = await _post(c, action, {**fields, ta: msg})
    except Exception as e:
        return f"ERROR: bình luận lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi bình luận (login/checkpoint)."
    return json.dumps({"ok": True, "action": "comment",
                       "note": "Đã gửi bình luận. Kiểm tra lại bài để chắc chắn."}, ensure_ascii=False)


# ---- Đọc bình luận của 1 bài + trả lời đúng 1 bình luận ----
_CMT_ID_RE = re.compile(r'<div id="(\d{6,})"[^>]*>')
_CMT_NOISE = {"Thích", "Trả lời", "Báo cáo", "Ẩn", "Xoá", "Chia sẻ"}
_CMT_TIME_RE = re.compile(r"^\d+\s*(giây|phút|giờ|ngày|tuần|tháng|năm)(\s*trước)?$", re.I)


def _parse_comments(page):
    """Bóc danh sách bình luận từ trang bài mbasic. BEST-EFFORT (xem đầu file): lấy
    <div id="số"> làm mốc từng bình luận thay vì cân cặp </div> (mbasic lồng div sâu,
    regex không tách chính xác theo thẻ đóng). Chỉnh lại nếu Facebook đổi cấu trúc."""
    marks = list(_CMT_ID_RE.finditer(page))
    out = []
    for i, m in enumerate(marks):
        cid = m.group(1)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(page)
        block = page[m.end():end]
        links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block)
        if not links:
            continue
        author_url, author = links[0]
        author = _html.unescape(author).strip()
        author_url = _html.unescape(author_url)
        reply_url = next((_html.unescape(h) for h, _t in links
                          if "comment/replies" in h or "replies.php" in h), "")
        kept = []
        for ln in (l for l in _strip(block).split("\n") if l):
            parts = [p.strip() for p in ln.split("·")]
            parts = [p for p in parts
                    if p and p != author and p not in _CMT_NOISE and not _CMT_TIME_RE.match(p)]
            if parts:
                kept.append(" ".join(parts))
        text = " ".join(kept).strip()
        if not text:
            continue
        out.append({"comment_id": cid, "author": author, "author_url": author_url,
                    "text": text[:2000], "reply_url": reply_url})
    return out


async def _read_comments(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post = str(args.get("post_url") or args.get("post_id") or "").strip()
    if not post:
        return "ERROR: thiếu 'post_url' (link bài mbasic, lấy từ fb_feed_read) hoặc 'post_id'."
    if post.isdigit():
        post = f"/story.php?story_fbid={post}"
    page, url, _ua, err = await _fetch(ck, post)
    if err:
        return err
    comments = _parse_comments(page)
    try:
        limit = max(1, min(200, int(args.get("limit") or 50)))
    except (TypeError, ValueError):
        limit = 50
    if not comments:
        return json.dumps({"comments": [], "source": url,
                           "note": ("Không thấy bình luận nào - bài chưa có ai bình luận, hoặc mbasic đã "
                                    "đổi cấu trúc trang (cần chỉnh lại selector trong plugin fb-personal).")},
                          ensure_ascii=False)
    return json.dumps({"comments": comments[:limit], "source": url}, ensure_ascii=False)


async def _reply_comment(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    msg = str(args.get("message") or "").strip()
    if not msg:
        return "ERROR: thiếu 'message' (nội dung trả lời)."
    reply_url = str(args.get("reply_url") or "").strip()
    if not reply_url:
        comment_id = str(args.get("comment_id") or "").strip()
        post = str(args.get("post_url") or args.get("post_id") or "").strip()
        if not comment_id or not post:
            return ("ERROR: cần 'reply_url' (lấy từ fb_personal_comments) hoặc cả 'comment_id' kèm "
                    "'post_url'/'post_id' để Javis tự tìm link trả lời.")
        if post.isdigit():
            post = f"/story.php?story_fbid={post}"
        page0, _url0, _ua0, err0 = await _fetch(ck, post)
        if err0:
            return err0
        match = next((c for c in _parse_comments(page0) if c["comment_id"] == comment_id), None)
        if not match or not match.get("reply_url"):
            return ("ERROR: Không tìm thấy bình luận có comment_id đó trên bài, hoặc bình luận này không "
                    "có link trả lời riêng (mbasic đổi cấu trúc - cần chỉnh lại selector).")
        reply_url = match["reply_url"]
    page, _url, ua, err = await _fetch(ck, reply_url)
    if err:
        return err
    action, fields, ta = _find_form(page, ["comment_text", "comment", "reply_text"])
    if not action or not ta:
        return ("ERROR: Không tìm thấy ô trả lời trên trang này (mbasic đổi/đóng, hoặc bình luận này không "
                "cho trả lời riêng). Cần chỉnh lại selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua) as c:
            _res, rurl = await _post(c, action, {**fields, ta: msg})
    except Exception as e:
        return f"ERROR: trả lời bình luận lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi trả lời (login/checkpoint)."
    return json.dumps({"ok": True, "action": "reply_comment",
                       "note": "Đã gửi trả lời bình luận. Kiểm tra lại bài để chắc chắn."}, ensure_ascii=False)


# ---- Bóc dữ liệu HTML (BEST-EFFORT: chỉnh khi Facebook đổi mbasic) ----
def _fb_dtsg(page):
    m = (re.search(r'name="fb_dtsg"\s+value="([^"]+)"', page)
         or re.search(r"name='fb_dtsg'\s+value='([^']+)'", page))
    return m.group(1) if m else ""


def _find_form(page, textarea_names):
    """Tìm <form> chứa <textarea name=...> khớp một trong textarea_names.
    Trả (action, hidden_dict, ta_name) hoặc (None, {}, None)."""
    for fm in re.findall(r"<form[^>]*>.*?</form>", page, re.S | re.I):
        ta = next((n for n in textarea_names
                   if re.search(r'<textarea[^>]*name="' + re.escape(n) + r'"', fm, re.I)), None)
        if not ta:
            continue
        am = re.search(r'<form[^>]*\baction="([^"]*)"', fm, re.I)
        action = _html.unescape(am.group(1)) if am else ""
        fields = {}
        for nm, val in re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', fm, re.I):
            fields[_html.unescape(nm)] = _html.unescape(val)
        return (action or None), fields, ta
    return None, {}, None


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def _strip(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", page, flags=re.I)
    txt = _html.unescape(_TAG.sub(" ", page))
    lines = [_WS.sub(" ", ln).strip() for ln in txt.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ---- Thao tác mở rộng: xoá bài, thả cảm xúc, chia sẻ, Messenger (BEST-EFFORT mbasic) ----
def _find_link(page, keywords, href_contains=None):
    """Tìm 1 anchor: ưu tiên href chứa href_contains, rồi tới TEXT khớp keywords (xét
    keyword theo THỨ TỰ - cụm cụ thể để trước). Trả href đã unescape hoặc None."""
    anchors = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I)
    parsed = [(_html.unescape(h), _html.unescape(_TAG.sub("", t)).strip()) for h, t in anchors]
    if href_contains:
        for h, _t in parsed:
            if href_contains in h:
                return h
    for kw in keywords:
        for h, t in parsed:
            if kw.lower() in t.lower():
                return h
    return None


def _find_button_form(page, submit_keywords):
    """Tìm <form> có nút submit value khớp submit_keywords (form xác nhận KHÔNG có
    textarea, vd form xoá bài). Trả (action, fields) - fields gồm hidden + ĐÚNG nút
    submit khớp (bỏ các nút khác như Huỷ để không gửi nhầm). Hoặc (None, {})."""
    for fm in re.findall(r"<form[^>]*>.*?</form>", page, re.S | re.I):
        submit_nv = None
        for inp in re.findall(r"<input\b[^>]*>", fm, re.I):
            if not re.search(r'type="submit"', inp, re.I):
                continue
            vm = re.search(r'value="([^"]*)"', inp, re.I)
            val = _html.unescape(vm.group(1)) if vm else ""
            if any(kw.lower() in val.lower() for kw in submit_keywords):
                nm = re.search(r'name="([^"]*)"', inp, re.I)
                submit_nv = (_html.unescape(nm.group(1)) if nm else "", val)
                break
        if not submit_nv:
            continue
        am = re.search(r'<form[^>]*\baction="([^"]*)"', fm, re.I)
        action = _html.unescape(am.group(1)) if am else ""
        fields = {}
        for inp in re.findall(r"<input\b[^>]*>", fm, re.I):
            if re.search(r'type="submit"', inp, re.I):
                continue        # nút submit khác (Huỷ...) không gửi kèm
            nm = re.search(r'name="([^"]*)"', inp, re.I)
            if not nm:
                continue
            vm = re.search(r'value="([^"]*)"', inp, re.I)
            fields[_html.unescape(nm.group(1))] = _html.unescape(vm.group(1)) if vm else ""
        if submit_nv[0]:
            fields[submit_nv[0]] = submit_nv[1]
        return (action or None), fields
    return None, {}


async def _get_action(ck, url):
    """GET một link 'hành động' (thích, xác nhận...). Trả (err_str hoặc None, final_url)."""
    _page, furl, _ua, err = await _fetch(ck, url)
    if err:
        return err, None
    if _blocked(furl):
        return "ERROR: Bị chặn (login/checkpoint).", None
    return None, furl


_REACTIONS = {
    "like": ["Thích", "Like"],
    "love": ["Yêu thích", "Love"],
    "care": ["Thương thương", "Care"],
    "haha": ["Haha"],
    "wow": ["Wow"],
    "sad": ["Buồn", "Sad"],
    "angry": ["Phẫn nộ", "Giận dữ", "Angry"],
}


async def _delete(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post = str(args.get("post_url") or args.get("post_id") or "").strip()
    if not post:
        return "ERROR: thiếu 'post_url' hoặc 'post_id' (bài của CHÍNH bạn cần xoá)."
    if post.isdigit():
        post = f"/story.php?story_fbid={post}"
    page, _url, _ua, err = await _fetch(ck, post)
    if err:
        return err
    del_link = _find_link(page, ["Xoá bài viết", "Xóa bài viết", "Gỡ bài viết", "Xoá bài", "Xóa bài",
                                 "Delete post", "Remove post", "Xoá", "Xóa", "Delete"])
    if not del_link:
        return ("ERROR: Không tìm thấy nút xoá trên bài này (chỉ xoá được bài của CHÍNH bạn; mbasic có thể "
                "đã đổi cấu trúc). Cần chỉnh selector trong plugin fb-personal.")
    confirm, _u2, ua2, err2 = await _fetch(ck, del_link)
    if err2:
        return err2
    action, fields = _find_button_form(confirm, ["Xoá", "Xóa", "Gỡ", "Delete", "Remove", "Đồng ý", "Confirm"])
    if not action:
        return ("ERROR: Không tìm thấy form xác nhận xoá (mbasic đổi cấu trúc). "
                "Cần chỉnh selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua2) as c:
            _res, rurl = await _post(c, action, fields)
    except Exception as e:
        return f"ERROR: xoá bài lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi xoá (login/checkpoint)."
    return json.dumps({"ok": True, "action": "delete_post",
                       "note": "Đã gửi yêu cầu xoá bài. Kiểm tra lại trang cá nhân để chắc chắn."},
                      ensure_ascii=False)


async def _react(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post = str(args.get("post_url") or args.get("post_id") or "").strip()
    if not post:
        return "ERROR: thiếu 'post_url' hoặc 'post_id'."
    reaction = str(args.get("reaction") or "like").strip().lower()
    if reaction not in _REACTIONS:
        return "ERROR: reaction phải là một trong: " + ", ".join(_REACTIONS)
    if post.isdigit():
        post = f"/story.php?story_fbid={post}"
    page, _url, _ua, err = await _fetch(ck, post)
    if err:
        return err
    if reaction == "like":
        target = _find_link(page, _REACTIONS["like"], href_contains="like.php")
        if not target:
            picker = _find_link(page, [], href_contains="reactions/picker")
            if picker:
                pg2, _u, _ua2, e2 = await _fetch(ck, picker)
                if e2:
                    return e2
                target = _find_link(pg2, _REACTIONS["like"])
        if not target:
            return ("ERROR: Không tìm thấy nút Thích trên bài (mbasic đổi cấu trúc). "
                    "Cần chỉnh selector trong plugin fb-personal.")
    else:
        picker = _find_link(page, [], href_contains="reactions/picker")
        if not picker:
            return ("ERROR: Không mở được bảng cảm xúc trên bài (mbasic đổi cấu trúc, hoặc bài chỉ cho Thích). "
                    "Cần chỉnh selector trong plugin fb-personal.")
        pg2, _u, _ua2, e2 = await _fetch(ck, picker)
        if e2:
            return e2
        target = _find_link(pg2, _REACTIONS[reaction])
        if not target:
            return f"ERROR: Không tìm thấy cảm xúc '{reaction}' trong bảng chọn (mbasic đổi cấu trúc)."
    err3, _furl = await _get_action(ck, target)
    if err3:
        return err3
    return json.dumps({"ok": True, "action": "react", "reaction": reaction,
                       "note": "Đã gửi cảm xúc. Kiểm tra lại bài để chắc chắn."}, ensure_ascii=False)


async def _share(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post = str(args.get("post_url") or args.get("post_id") or "").strip()
    if not post:
        return "ERROR: thiếu 'post_url' hoặc 'post_id' (bài cần chia sẻ)."
    msg = str(args.get("message") or "").strip()
    if post.isdigit():
        post = f"/story.php?story_fbid={post}"
    page, _url, _ua, err = await _fetch(ck, post)
    if err:
        return err
    share_link = _find_link(page, ["Chia sẻ ngay", "Chia sẻ", "Share"], href_contains="sharer")
    if not share_link:
        return ("ERROR: Không tìm thấy nút Chia sẻ trên bài (mbasic đổi cấu trúc, hoặc bài không cho chia sẻ). "
                "Cần chỉnh selector trong plugin fb-personal.")
    spage, _u2, ua2, err2 = await _fetch(ck, share_link)
    if err2:
        return err2
    action, fields, ta = _find_form(spage, ["message", "xc_message", "text", "share_text", "caption"])
    if action:
        data = {**fields}
        if ta:
            data[ta] = msg
    else:
        action, data = _find_button_form(spage, ["Chia sẻ", "Share", "Đăng", "Post"])
    if not action:
        return ("ERROR: Không tìm thấy form chia sẻ (mbasic đổi cấu trúc). "
                "Cần chỉnh selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua2) as c:
            _res, rurl = await _post(c, action, data)
    except Exception as e:
        return f"ERROR: chia sẻ lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi chia sẻ (login/checkpoint)."
    return json.dumps({"ok": True, "action": "share",
                       "note": "Đã gửi yêu cầu chia sẻ lên tường. Kiểm tra lại trang cá nhân."},
                      ensure_ascii=False)


# ---- Messenger (mbasic /messages) ----
_THREAD_RE = re.compile(
    r'<a\b[^>]*href="(/messages/read/\?[^"]+|/read/\?[^"]+|/messages/thread/[^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I)


def _parse_threads(page):
    """Bóc danh sách hội thoại từ trang /messages. BEST-EFFORT: mỗi anchor tới trang đọc
    tin = 1 hội thoại; dòng đầu là tên, phần còn lại là đoạn tin gần nhất."""
    out, seen = [], set()
    for href, inner in _THREAD_RE.findall(page):
        h = _html.unescape(href)
        if h in seen:
            continue
        seen.add(h)
        lines = [ln for ln in _strip(inner).split("\n") if ln]
        if not lines:
            continue
        out.append({"thread_url": h, "name": lines[0], "snippet": " ".join(lines[1:])[:300]})
    return out


async def _messages(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    try:
        limit = max(1, min(100, int(args.get("limit") or 30)))
    except (TypeError, ValueError):
        limit = 30
    page, url, _ua, err = await _fetch(ck, "/messages/")
    if err:
        return err
    threads = _parse_threads(page)
    if not threads:
        return json.dumps({"threads": [], "source": url,
                           "note": ("Không thấy hội thoại nào - hộp thư trống, hoặc mbasic đã đổi cấu trúc "
                                    "/messages (cần chỉnh selector trong plugin fb-personal).")},
                          ensure_ascii=False)
    return json.dumps({"threads": threads[:limit], "source": url}, ensure_ascii=False)


async def _thread(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    turl = str(args.get("thread_url") or "").strip()
    tid = str(args.get("tid") or "").strip()
    if not turl:
        if not tid:
            return "ERROR: cần 'thread_url' (từ fb_messages_read) hoặc 'tid' để biết đọc cuộc trò chuyện nào."
        turl = f"/messages/read/?tid={tid}"
    page, url, _ua, err = await _fetch(ck, turl)
    if err:
        return err
    try:
        limit = max(500, min(20000, int(args.get("max_chars") or 4000)))
    except (TypeError, ValueError):
        limit = 4000
    action, _fields, ta = _find_form(page, ["body", "message"])
    text = _strip(page)
    if len(text) > limit:
        text = text[-limit:]        # tin mới nhất nằm cuối trang mbasic, giữ phần đuôi
    return json.dumps({"thread_text": text, "source": url, "can_send": bool(action and ta)},
                      ensure_ascii=False)


async def _send_message(args, ctx):
    ck = _cookie()
    if not ck:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    msg = str(args.get("message") or "").strip()
    if not msg:
        return "ERROR: thiếu 'message' (nội dung tin nhắn)."
    turl = str(args.get("thread_url") or "").strip()
    tid = str(args.get("tid") or "").strip()
    if not turl:
        if not tid:
            return "ERROR: cần 'thread_url' (từ fb_messages_read) hoặc 'tid' để biết gửi cho ai."
        turl = f"/messages/read/?tid={tid}"
    page, _url, ua, err = await _fetch(ck, turl)
    if err:
        return err
    action, fields, ta = _find_form(page, ["body", "message"])
    if not action or not ta:
        return ("ERROR: Không tìm thấy ô soạn tin trên cuộc trò chuyện (mbasic đổi cấu trúc /messages, hoặc "
                "không gửi được cho hội thoại này). Cần chỉnh selector trong plugin fb-personal.")
    try:
        async with _client(ck, ua) as c:
            _res, rurl = await _post(c, action, {**fields, ta: msg})
    except Exception as e:
        return f"ERROR: gửi tin lỗi ({type(e).__name__}: {e})."
    if _blocked(rurl):
        return "ERROR: Bị chặn khi gửi tin (login/checkpoint)."
    return json.dumps({"ok": True, "action": "send_message",
                       "note": "Đã gửi tin nhắn. Kiểm tra lại Messenger để chắc chắn."}, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(
        name="fb_feed_read", min_mode="readonly", check_fn=_check, handler=_feed,
        description=("Đọc/lướt feed Facebook CÁ NHÂN của bạn qua cookie (mbasic). Trả feed_text (đã làm sạch), "
                     "post_links và next_url (trang feed kế). max_chars giới hạn độ dài (mặc định 6000); pages "
                     "để lướt sâu nhiều trang liền (mặc định 1, tối đa 5); next_url để đọc tiếp từ trang trước."),
        schema={"type": "object", "properties": {
            "max_chars": {"type": "integer", "description": "Số ký tự tối đa của feed_text (mặc định 6000)"},
            "pages": {"type": "integer", "description": "Số trang feed lướt liên tiếp (mặc định 1, tối đa 5)"},
            "next_url": {"type": "string", "description": "Link trang feed kế (next_url lần trước) để đọc tiếp"}}},
    )
    ctx.register_tool(
        name="fb_personal_post", min_mode="full", check_fn=_check, handler=_publish,
        description=("ĐĂNG một bài lên tường Facebook CÁ NHÂN của bạn - hành động THẬT bằng tài khoản cá nhân "
                     "(rủi ro khoá tài khoản). Cần message."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung bài đăng"}},
            "required": ["message"]},
    )
    ctx.register_tool(
        name="fb_personal_comment", min_mode="full", check_fn=_check, handler=_comment,
        description=("BÌNH LUẬN vào một bài trên Facebook bằng tài khoản CÁ NHÂN - hành động THẬT. Cần message "
                     "và post_url (link bài mbasic từ fb_feed_read) hoặc post_id."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung bình luận"},
            "post_url": {"type": "string", "description": "Link bài trên mbasic (từ fb_feed_read)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"}},
            "required": ["message"]},
    )
    ctx.register_tool(
        name="fb_personal_comments", min_mode="readonly", check_fn=_check, handler=_read_comments,
        description=("Đọc bình luận của MỘT bài trên tường Facebook CÁ NHÂN qua cookie (mbasic): comment_id, "
                     "tên người bình luận, nội dung, reply_url (dùng cho fb_personal_comment_reply). Cần "
                     "post_url (link bài mbasic từ fb_feed_read) hoặc post_id. BEST-EFFORT: chỉ thấy bình "
                     "luận mbasic hiển thị sẵn, không tự bấm 'xem thêm bình luận'."),
        schema={"type": "object", "properties": {
            "post_url": {"type": "string", "description": "Link bài trên mbasic (từ fb_feed_read)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"},
            "limit": {"type": "integer", "description": "Số bình luận tối đa trả về (mặc định 50)"}}},
    )
    ctx.register_tool(
        name="fb_personal_comment_reply", min_mode="full", check_fn=_check, handler=_reply_comment,
        description=("TRẢ LỜI một bình luận CỤ THỂ (khác fb_personal_comment vốn bình luận thẳng vào bài) "
                     "bằng tài khoản CÁ NHÂN - hành động THẬT. Cần message, và reply_url (lấy từ "
                     "fb_personal_comments) hoặc comment_id kèm post_url/post_id để Javis tự tìm."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung trả lời"},
            "reply_url": {"type": "string", "description": "Link trả lời bình luận (từ fb_personal_comments)"},
            "comment_id": {"type": "string",
                          "description": "ID bình luận cần trả lời (thay reply_url, cần kèm post_url/post_id)"},
            "post_url": {"type": "string", "description": "Link bài mbasic (dùng kèm comment_id khi không có reply_url)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"}},
            "required": ["message"]},
    )
    ctx.register_tool(
        name="fb_personal_delete", min_mode="full", check_fn=_check, handler=_delete,
        description=("XOÁ một bài trên tường Facebook CÁ NHÂN của bạn (chỉ bài của CHÍNH bạn) - hành động THẬT, "
                     "KHÔNG hoàn tác. Cần post_url (link bài mbasic từ fb_feed_read) hoặc post_id."),
        schema={"type": "object", "properties": {
            "post_url": {"type": "string", "description": "Link bài trên mbasic (từ fb_feed_read)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"}}},
    )
    ctx.register_tool(
        name="fb_personal_react", min_mode="full", check_fn=_check, handler=_react,
        description=("THẢ CẢM XÚC (thích/yêu thích/haha/wow/buồn/phẫn nộ) vào một bài trên Facebook bằng tài "
                     "khoản CÁ NHÂN - hành động THẬT. Cần post_url hoặc post_id; reaction mặc định 'like'."),
        schema={"type": "object", "properties": {
            "post_url": {"type": "string", "description": "Link bài trên mbasic (từ fb_feed_read)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"},
            "reaction": {"type": "string", "enum": list(_REACTIONS),
                         "description": "Loại cảm xúc: like|love|care|haha|wow|sad|angry (mặc định like)"}}},
    )
    ctx.register_tool(
        name="fb_personal_share", min_mode="full", check_fn=_check, handler=_share,
        description=("CHIA SẺ một bài lên tường Facebook CÁ NHÂN của bạn - hành động THẬT. Cần post_url hoặc "
                     "post_id; message là lời kèm khi chia sẻ (tuỳ chọn)."),
        schema={"type": "object", "properties": {
            "post_url": {"type": "string", "description": "Link bài trên mbasic (từ fb_feed_read)"},
            "post_id": {"type": "string", "description": "ID bài (thay cho post_url)"},
            "message": {"type": "string", "description": "Lời kèm khi chia sẻ (tuỳ chọn)"}}},
    )
    ctx.register_tool(
        name="fb_messages_read", min_mode="readonly", check_fn=_check, handler=_messages,
        description=("Đọc hộp thư MESSENGER của tài khoản Facebook CÁ NHÂN qua cookie (mbasic): danh sách hội "
                     "thoại gồm tên người, đoạn tin gần nhất, thread_url (dùng cho fb_message_thread/"
                     "fb_message_send). limit giới hạn số hội thoại (mặc định 30)."),
        schema={"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Số hội thoại tối đa trả về (mặc định 30)"}}},
    )
    ctx.register_tool(
        name="fb_message_thread", min_mode="readonly", check_fn=_check, handler=_thread,
        description=("Đọc nội dung MỘT cuộc trò chuyện Messenger qua cookie (mbasic). Cần thread_url (từ "
                     "fb_messages_read) hoặc tid. Trả thread_text (nội dung đã làm sạch) + can_send (gửi được không)."),
        schema={"type": "object", "properties": {
            "thread_url": {"type": "string", "description": "Link hội thoại (từ fb_messages_read)"},
            "tid": {"type": "string", "description": "ID hội thoại (thay cho thread_url)"},
            "max_chars": {"type": "integer", "description": "Số ký tự tối đa của thread_text (mặc định 4000)"}}},
    )
    ctx.register_tool(
        name="fb_message_send", min_mode="full", check_fn=_check, handler=_send_message,
        description=("GỬI một tin nhắn Messenger bằng tài khoản Facebook CÁ NHÂN - hành động THẬT. Cần message, "
                     "và thread_url (từ fb_messages_read) hoặc tid để biết gửi cho ai."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung tin nhắn"},
            "thread_url": {"type": "string", "description": "Link hội thoại (từ fb_messages_read)"},
            "tid": {"type": "string", "description": "ID hội thoại (thay cho thread_url)"}},
            "required": ["message"]},
    )
