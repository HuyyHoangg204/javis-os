"""Test connector + plugin Facebook cá nhân (cookie/mbasic). Chạy tay / CI:

    cd server && python test_fb_personal.py

KHÔNG mạng (giả cookie + giả _get/_post + _client). Phủ: catalog connector hợp lệ (apikey,
field cookie, risk cảnh báo khoá tài khoản), plugin nạp đủ 3 tool + đúng min_mode (đọc readonly,
đăng/bình luận full), gate chưa-có-cookie, bóc fb_dtsg + tìm form soạn bài/bình luận, đọc feed
(text + link, chặn khi bị đẩy về login), đăng bài + bình luận build đúng POST, và validate_connection
cho connector ẢO (không URL) qua cửa mà không dial MCP.
"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-fbpersonal-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_fails = []
def check(n, c):
    print(("ok  " if c else "FAIL ") + n)
    if not c: _fails.append(n)


# ---- 1. Catalog connector ----
cat = json.load(open(Path(__file__).parent.parent / "system" / "mcp-catalog.json", encoding="utf-8"))
fp = next((x for x in cat["connectors"] if x["id"] == "facebook-personal"), None)
check("catalog: có connector facebook-personal", fp is not None)
check("catalog: auth apikey + field cookie", fp["auth"].get("type") == "apikey"
      and any(f["key"] == "cookie" for f in fp["auth"]["fields"]))
check("catalog: field cookie multiline", any(f["key"] == "cookie" and f.get("multiline") for f in fp["auth"]["fields"]))
check("catalog: default_perm readonly", fp["default_perm"] == "readonly")
check("catalog: risk cảnh báo khoá tài khoản", "KHO" in (fp.get("risk") or "").upper() and "cá nhân" in fp["risk"].lower())
check("catalog: tool ghi ở danger",
      set(fp["tool_meta"].get("danger") or [])
      == {"fb_personal_post", "fb_personal_comment", "fb_personal_comment_reply",
          "fb_personal_delete", "fb_personal_react", "fb_personal_share", "fb_message_send"})
check("catalog: tool đọc (bình luận + Messenger) ở read",
      {"fb_personal_comments", "fb_messages_read", "fb_message_thread"}
      <= set(fp["tool_meta"].get("read") or []))
import mcp_catalog  # noqa: E402
check("mcp_catalog.get load được", mcp_catalog.get("facebook-personal") is not None)


# ---- 2. validate_connection: connector ẢO (không URL) qua cửa không dial ----
import mcp_hub, mcp_store  # noqa: E402


async def virtual_validate_test():
    orig = mcp_store.resolved
    mcp_store.resolved = lambda enabled_only=False: [{
        "id": "cfp", "url": "", "command": "",
        "connector": {"tool_meta": {"read": ["fb_feed_read"], "danger": ["fb_personal_post", "fb_personal_comment"]}},
    }]
    try:
        r = await mcp_hub.validate_connection("cfp")
        check("validate_connection: connector ẢO ok + đếm 3 tool, KHÔNG dial MCP",
              r.get("ok") and r.get("tools") == 3)
    finally:
        mcp_store.resolved = orig

asyncio.run(virtual_validate_test())


# ---- 3. Plugin nạp + min_mode ----
spec = importlib.util.spec_from_file_location(
    "fb_personal_test", str(Path(__file__).parent.parent / "system" / "plugins" / "fb-personal" / "plugin.py"))
plug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plug)


class _Ctx:
    def __init__(self): self.tools = []
    def register_tool(self, name, description, handler, schema=None, min_mode="readonly", check_fn=None, **k):
        self.tools.append({"name": name, "handler": handler, "min_mode": min_mode})


ctx = _Ctx()
plug.register(ctx)
byname = {t["name"]: t for t in ctx.tools}
check("plugin: đủ 11 tool", set(byname) == {
    "fb_feed_read", "fb_personal_post", "fb_personal_comment", "fb_personal_comments",
    "fb_personal_comment_reply", "fb_personal_delete", "fb_personal_react", "fb_personal_share",
    "fb_messages_read", "fb_message_thread", "fb_message_send"})
check("plugin: tool đọc đều readonly",
      all(byname[n]["min_mode"] == "readonly" for n in
          ("fb_feed_read", "fb_personal_comments", "fb_messages_read", "fb_message_thread")))
check("plugin: tool ghi đều full",
      all(byname[n]["min_mode"] == "full" for n in
          ("fb_personal_post", "fb_personal_comment", "fb_personal_comment_reply", "fb_personal_delete",
           "fb_personal_react", "fb_personal_share", "fb_message_send")))

# gate: chưa có cookie
plug._connected_id = lambda: None
check("plugin: _check chặn khi chưa có cookie", "Chưa kết nối" in (plug._check() or ""))


# ---- 4. Helper thuần: fb_dtsg, find_form, strip ----
HOME = ('<html><body>'
        '<form method="post" action="/composer/mbasic/?csid=1">'
        '<input type="hidden" name="fb_dtsg" value="AbC123">'
        '<textarea name="xc_message"></textarea>'
        '<input type="submit" name="view_post" value="Đăng"></form>'
        '<div class="story"><h3>Nguyen Van A</h3><p>Hôm nay trời đẹp quá</p>'
        '<a href="/story.php?story_fbid=111&id=222">Chi tiết</a></div>'
        '<div class="story"><h3>Shop B</h3><p>Giảm giá 50 phần trăm</p>'
        '<a href="/story.php?story_fbid=333&id=444">Chi tiết</a></div>'
        '</body></html>')
POSTPAGE = ('<html><body><div><h3>Nguyen Van A</h3><p>Hôm nay trời đẹp quá</p></div>'
            '<form method="post" action="/a/comment.php?ctoken=xyz">'
            '<input type="hidden" name="fb_dtsg" value="Cmt99">'
            '<textarea name="comment_text"></textarea>'
            '<input type="submit" name="submit" value="Bình luận"></form></body></html>')
COMMENTS_PAGE = ('<html><body><div><h3>Nguyen Van A</h3><p>Hôm nay trời đẹp quá</p></div>'
                 '<div id="1234500001"><h3><a href="/profile.php?id=700001">Tran Thi B</a></h3>'
                 '<div>Anh cho hoi gia bao nhieu</div>'
                 '<div><a href="/comment/replies/?ctoken=r1&cmt_id=1234500001">Trả lời</a> · '
                 '<abbr>3 giờ</abbr></div></div>'
                 '<div id="1234500002"><h3><a href="/profile.php?id=700002">Le Van C</a></h3>'
                 '<div>Dep lam ban oi</div>'
                 '<div><a href="/comment/replies/?ctoken=r2&cmt_id=1234500002">Trả lời</a> · '
                 '<abbr>1 ngày</abbr></div></div>'
                 '</body></html>')
REPLYPAGE = ('<html><body><form method="post" action="/a/comment_replies.php?ctoken=r1">'
             '<input type="hidden" name="fb_dtsg" value="Rpl77">'
             '<textarea name="comment_text"></textarea>'
             '<input type="submit" name="submit" value="Trả lời"></form></body></html>')

check("_fb_dtsg: bóc được token", plug._fb_dtsg(HOME) == "AbC123")
a, hid, ta = plug._find_form(HOME, ["xc_message", "status"])
check("_find_form: form soạn bài (action + fb_dtsg + textarea)",
      a == "/composer/mbasic/?csid=1" and hid.get("fb_dtsg") == "AbC123" and ta == "xc_message")
ac, hic, tc = plug._find_form(POSTPAGE, ["comment_text", "comment"])
check("_find_form: form bình luận", ac == "/a/comment.php?ctoken=xyz" and hic.get("fb_dtsg") == "Cmt99" and tc == "comment_text")
check("_strip: bỏ tag, còn chữ", "trời đẹp quá" in plug._strip(HOME) and "<" not in plug._strip(HOME))

cmts = plug._parse_comments(COMMENTS_PAGE)
check("_parse_comments: bóc đủ 2 bình luận, đúng id/tên/nội dung, bỏ nhiễu Trả lời/thời gian",
      len(cmts) == 2
      and cmts[0]["comment_id"] == "1234500001" and cmts[0]["author"] == "Tran Thi B"
      and cmts[0]["text"] == "Anh cho hoi gia bao nhieu"
      and "cmt_id=1234500001" in cmts[0]["reply_url"]
      and cmts[1]["comment_id"] == "1234500002" and cmts[1]["text"] == "Dep lam ban oi")


# ---- 4b. Fixture + helper cho thao tác mở rộng (xoá/react/share/messenger) ----
DELPOST = ('<html><body><div><h3>Minh Quy</h3><p>Bai cua toi</p></div>'
           '<a href="/story.php?story_fbid=555">Chi tiet</a>'
           '<a href="/delete.php?story_fbid=555&confirm=1">Xoá bài viết</a>'
           '<a href="/a/like.php?ft=555">Thích</a></body></html>')
DELCONFIRM = ('<html><body><form method="post" action="/a/removecontent.php?story_fbid=555">'
              '<input type="hidden" name="fb_dtsg" value="Del55">'
              '<input type="submit" name="delete" value="Xoá">'
              '<input type="submit" name="cancel" value="Huỷ"></form></body></html>')
REACTPAGE = ('<html><body><div><h3>Ai do</h3><p>Bai viet</p></div>'
             '<a href="/a/like.php?ft_ent_identifier=555&like">Thích</a>'
             '<a href="/reactions/picker/?ft_ent_identifier=555">Cảm xúc</a></body></html>')
PICKER = ('<html><body>'
          '<a href="/a/reactions.php?ft=555&reaction_type=1">Thích</a>'
          '<a href="/a/reactions.php?ft=555&reaction_type=2">Yêu thích</a>'
          '<a href="/a/reactions.php?ft=555&reaction_type=4">Haha</a></body></html>')
SHAREPAGE = ('<html><body><div><h3>Ai do</h3><p>Bai hay</p></div>'
             '<a href="/story.php?story_fbid=555">Chi tiet</a>'
             '<a href="/sharer.php?sid=555">Chia sẻ</a></body></html>')
SHARECOMPOSER = ('<html><body><form method="post" action="/a/sharer.php?sid=555">'
                 '<input type="hidden" name="fb_dtsg" value="Shr9">'
                 '<textarea name="message"></textarea>'
                 '<input type="submit" name="post" value="Chia sẻ"></form></body></html>')
MSGLIST = ('<html><body>'
           '<a href="/messages/read/?tid=cid.c.100">Tran Thi B<br/>Còn hàng không ạ</a>'
           '<a href="/messages/read/?tid=cid.c.200">Le Van C<br/>Ok em lấy 2 cái</a></body></html>')
THREADPAGE = ('<html><body><h3>Tran Thi B</h3>'
              '<div>Chào shop, còn hàng không?</div><div>Dạ còn ạ</div>'
              '<form method="post" action="/messages/send/?tid=cid.c.100">'
              '<input type="hidden" name="fb_dtsg" value="Msg42">'
              '<textarea name="body"></textarea>'
              '<input type="submit" name="send" value="Gửi"></form></body></html>')

check("_find_link: ưu tiên cụm cụ thể (Xoá bài viết) hơn Xoá chung",
      plug._find_link(DELPOST, ["Xoá bài viết", "Xoá"]) == "/delete.php?story_fbid=555&confirm=1")
check("_find_link: href_contains bắt đúng link like",
      plug._find_link(REACTPAGE, [], href_contains="like.php") == "/a/like.php?ft_ent_identifier=555&like")
check("_find_link: chọn đúng cảm xúc theo tên trong picker",
      plug._find_link(PICKER, ["Haha"]) == "/a/reactions.php?ft=555&reaction_type=4")
da, df = plug._find_button_form(DELCONFIRM, ["Xoá", "Delete"])
check("_find_button_form: lấy đúng nút Xoá + fb_dtsg, BỎ nút Huỷ",
      da == "/a/removecontent.php?story_fbid=555" and df.get("fb_dtsg") == "Del55"
      and df.get("delete") == "Xoá" and "cancel" not in df)
thr = plug._parse_threads(MSGLIST)
check("_parse_threads: bóc 2 hội thoại đúng tên + thread_url + đoạn tin",
      len(thr) == 2 and thr[0]["name"] == "Tran Thi B" and "tid=cid.c.100" in thr[0]["thread_url"]
      and "Còn hàng không" in thr[0]["snippet"] and thr[1]["name"] == "Le Van C")


# ---- 5. Handler (giả cookie + _client + _get/_post) ----
async def handler_tests():
    plug._connected_id = lambda: "cfp"
    plug._cookie = lambda: "c_user=1; xs=abc"

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    plug._client = lambda ck, ua=None: _FakeClient()

    state = {"page": HOME, "url": BASE_HOME, "posted": None}
    async def _fake_get(client, url):
        return state["page"], state["url"]
    async def _fake_post(client, action, data):
        state["posted"] = (action, data)
        return "<html>ok</html>", state["url"]
    plug._get = _fake_get
    plug._post = _fake_post

    # feed: text + link, không bị chặn
    r_feed = await plug._feed({"max_chars": 500}, None)
    d = json.loads(r_feed)
    check("fb_feed_read: có feed_text + post_links",
          "trời đẹp" in d["feed_text"] and any("story_fbid=111" in u for u in d["post_links"]))

    # feed bị đẩy về login → ERROR
    state["url"] = "https://mbasic.facebook.com/login.php?next=..."
    r_block = await plug._feed({}, None)
    check("fb_feed_read: cookie hỏng (login) → ERROR", r_block.startswith("ERROR") and "cookie" in r_block.lower())
    state["url"] = BASE_HOME

    # post: POST đúng form action + xc_message + fb_dtsg
    r_post = await plug._publish({"message": "Xin chao ca nha"}, None)
    check("fb_personal_post: POST composer + message + fb_dtsg",
          state["posted"][0] == "/composer/mbasic/?csid=1"
          and state["posted"][1].get("xc_message") == "Xin chao ca nha"
          and state["posted"][1].get("fb_dtsg") == "AbC123"
          and '"ok": true' in r_post.lower())
    r_post_empty = await plug._publish({}, None)
    check("fb_personal_post: thiếu message → ERROR", r_post_empty.startswith("ERROR"))

    # comment: nạp trang bài rồi POST comment_text
    state["page"] = POSTPAGE
    r_cmt = await plug._comment({"post_url": "/story.php?story_fbid=111", "message": "Dep qua"}, None)
    check("fb_personal_comment: POST comment form + comment_text + fb_dtsg",
          state["posted"][0] == "/a/comment.php?ctoken=xyz"
          and state["posted"][1].get("comment_text") == "Dep qua"
          and state["posted"][1].get("fb_dtsg") == "Cmt99"
          and '"ok": true' in r_cmt.lower())
    r_cmt_nopost = await plug._comment({"message": "hi"}, None)
    check("fb_personal_comment: thiếu post_url/post_id → ERROR", r_cmt_nopost.startswith("ERROR"))
    r_cmt_nomsg = await plug._comment({"post_url": "/x"}, None)
    check("fb_personal_comment: thiếu message → ERROR", r_cmt_nomsg.startswith("ERROR"))

    # đọc bình luận: nạp trang bài rồi bóc danh sách
    state["page"] = COMMENTS_PAGE
    r_read = await plug._read_comments({"post_url": "/story.php?story_fbid=111"}, None)
    d_read = json.loads(r_read)
    check("fb_personal_comments: đọc đủ 2 bình luận kèm reply_url",
          len(d_read["comments"]) == 2 and d_read["comments"][0]["author"] == "Tran Thi B"
          and d_read["comments"][0]["reply_url"])
    r_read_empty = await plug._read_comments({"message": "hi"}, None)
    check("fb_personal_comments: thiếu post_url/post_id → ERROR", r_read_empty.startswith("ERROR"))

    # trả lời bình luận qua reply_url thẳng: POST vào form của trang reply
    state["page"] = REPLYPAGE
    r_reply = await plug._reply_comment(
        {"reply_url": "/comment/replies/?ctoken=r1&cmt_id=1234500001", "message": "Da nhan tin rieng nhe"}, None)
    check("fb_personal_comment_reply: POST đúng form trang reply + comment_text + fb_dtsg",
          state["posted"][0] == "/a/comment_replies.php?ctoken=r1"
          and state["posted"][1].get("comment_text") == "Da nhan tin rieng nhe"
          and state["posted"][1].get("fb_dtsg") == "Rpl77"
          and '"ok": true' in r_reply.lower())

    # trả lời qua comment_id + post_url: tự nạp trang bài tìm reply_url rồi mới nạp trang reply
    pages = [COMMENTS_PAGE, REPLYPAGE]
    async def _fake_get_seq(client, url):
        return pages.pop(0), state["url"]
    plug._get = _fake_get_seq
    r_reply2 = await plug._reply_comment(
        {"comment_id": "1234500001", "post_url": "/story.php?story_fbid=111", "message": "Oke ban nhe"}, None)
    check("fb_personal_comment_reply: tự tìm reply_url qua comment_id rồi trả lời",
          state["posted"][1].get("comment_text") == "Oke ban nhe" and '"ok": true' in r_reply2.lower())
    plug._get = _fake_get

    r_reply_nomsg = await plug._reply_comment({"reply_url": "/x"}, None)
    check("fb_personal_comment_reply: thiếu message → ERROR", r_reply_nomsg.startswith("ERROR"))
    r_reply_notarget = await plug._reply_comment({"message": "hi"}, None)
    check("fb_personal_comment_reply: thiếu reply_url và comment_id/post → ERROR", r_reply_notarget.startswith("ERROR"))

    # ---- Thao tác mở rộng: xoá / react / share / messenger ----
    got = {"url": None}

    def _seq_getter(seq):
        box = list(seq)
        async def _g(client, url):
            got["url"] = url
            return (box.pop(0) if box else seq[-1]), state["url"]
        return _g

    # xoá bài: nạp trang bài → trang xác nhận → POST form removecontent (đúng nút Xoá, bỏ Huỷ)
    plug._get = _seq_getter([DELPOST, DELCONFIRM])
    r_del = await plug._delete({"post_url": "/story.php?story_fbid=555"}, None)
    check("fb_personal_delete: POST form removecontent + fb_dtsg + nút Xoá, KHÔNG kèm Huỷ",
          state["posted"][0] == "/a/removecontent.php?story_fbid=555"
          and state["posted"][1].get("fb_dtsg") == "Del55"
          and state["posted"][1].get("delete") == "Xoá"
          and "cancel" not in state["posted"][1]
          and '"ok": true' in r_del.lower())
    r_del_nopost = await plug._delete({}, None)
    check("fb_personal_delete: thiếu post → ERROR", r_del_nopost.startswith("ERROR"))

    # react like: GET đúng link like.php trên bài
    plug._get = _seq_getter([REACTPAGE, REACTPAGE])
    r_react = await plug._react({"post_url": "/story.php?story_fbid=555"}, None)
    check("fb_personal_react: like GET đúng link like.php",
          got["url"] == "/a/like.php?ft_ent_identifier=555&like" and '"ok": true' in r_react.lower())
    # react haha: mở picker rồi GET đúng reaction_type
    plug._get = _seq_getter([REACTPAGE, PICKER, PICKER])
    r_haha = await plug._react({"post_url": "/story.php?story_fbid=555", "reaction": "haha"}, None)
    check("fb_personal_react: haha mở picker rồi GET đúng reaction_type",
          "reaction_type=4" in (got["url"] or "") and '"ok": true' in r_haha.lower())
    r_react_bad = await plug._react({"post_url": "/x", "reaction": "xyz"}, None)
    check("fb_personal_react: reaction lạ → ERROR", r_react_bad.startswith("ERROR"))

    # chia sẻ: nạp trang bài → trang soạn chia sẻ → POST form sharer + message
    plug._get = _seq_getter([SHAREPAGE, SHARECOMPOSER])
    r_share = await plug._share({"post_url": "/story.php?story_fbid=555", "message": "Hay qua"}, None)
    check("fb_personal_share: POST form sharer + message + fb_dtsg",
          state["posted"][0] == "/a/sharer.php?sid=555"
          and state["posted"][1].get("message") == "Hay qua"
          and state["posted"][1].get("fb_dtsg") == "Shr9"
          and '"ok": true' in r_share.lower())
    r_share_nopost = await plug._share({"message": "x"}, None)
    check("fb_personal_share: thiếu post → ERROR", r_share_nopost.startswith("ERROR"))

    # messenger: đọc danh sách hội thoại
    plug._get = _fake_get
    state["page"] = MSGLIST
    r_msgs = await plug._messages({}, None)
    d_msgs = json.loads(r_msgs)
    check("fb_messages_read: đọc 2 hội thoại kèm thread_url",
          len(d_msgs["threads"]) == 2 and d_msgs["threads"][0]["name"] == "Tran Thi B"
          and "tid=cid.c.100" in d_msgs["threads"][0]["thread_url"])

    # messenger: đọc 1 cuộc trò chuyện + gửi tin
    state["page"] = THREADPAGE
    r_thr = await plug._thread({"tid": "cid.c.100"}, None)
    d_thr = json.loads(r_thr)
    check("fb_message_thread: đọc nội dung + can_send",
          "còn hàng không" in d_thr["thread_text"].lower() and d_thr["can_send"] is True)
    r_thr_notarget = await plug._thread({}, None)
    check("fb_message_thread: thiếu thread_url/tid → ERROR", r_thr_notarget.startswith("ERROR"))

    r_send = await plug._send_message({"tid": "cid.c.100", "message": "Da con hang"}, None)
    check("fb_message_send: POST form send + body + fb_dtsg",
          state["posted"][0] == "/messages/send/?tid=cid.c.100"
          and state["posted"][1].get("body") == "Da con hang"
          and state["posted"][1].get("fb_dtsg") == "Msg42"
          and '"ok": true' in r_send.lower())
    r_send_nomsg = await plug._send_message({"tid": "cid.c.100"}, None)
    check("fb_message_send: thiếu message → ERROR", r_send_nomsg.startswith("ERROR"))
    r_send_notarget = await plug._send_message({"message": "hi"}, None)
    check("fb_message_send: thiếu thread_url/tid → ERROR", r_send_notarget.startswith("ERROR"))

BASE_HOME = "https://mbasic.facebook.com/"
asyncio.run(handler_tests())


# ---- 6. Lớp fetch: phát hiện trang 'không hỗ trợ' + tự đổi UA + ô UA override ----
UNSUPPORTED = ('<html><body><h2>Trình duyệt này không hỗ trợ Facebook, hãy tải Facebook Lite</h2>'
               '</body></html>')
check("_unsupported: bắt trang 'không hỗ trợ / Facebook Lite'",
      plug._unsupported(UNSUPPORTED) and not plug._unsupported(HOME))
LOGINPAGE = ('<html><body><form method="post" action="/login/device-based/regular/login/">'
             '<input name="email" type="text"><input name="pass" type="password">'
             '<input name="login" value="Đăng nhập"></form></body></html>')
check("_is_login: bắt trang đăng nhập (email+pass)", plug._is_login(LOGINPAGE) and not plug._is_login(HOME))
# Trang splash 'Đăng nhập hoặc đăng ký' khi cookie bị đá ra: KHÔNG có ô email/mật khẩu, chỉ
# tiêu đề + nút, URL không chứa 'login'. Trước đây lọt thành feed - phải bắt được theo nội dung.
SPLASH = ('<html><head><title>Facebook - Đăng nhập hoặc đăng ký Facebook</title></head>'
          '<body><h2>Đăng nhập hoặc đăng ký</h2>'
          '<a href="/login/?next=%2F">Đăng nhập</a>'
          '<a href="/reg/">Tạo tài khoản mới</a></body></html>')
check("_is_login: bắt trang splash (không ô email/mật khẩu, chỉ tiêu đề + nút login)",
      plug._is_login(SPLASH) and not plug._is_login(HOME) and not plug._is_login(POSTPAGE))


async def fetch_tests():
    plug._connected_id = lambda: "cfp"
    plug._cookie = lambda: "c_user=1; xs=abc"

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    plug._client = lambda ck, ua: _FakeClient()

    # UA override: field user_agent → đứng đầu danh sách UA thử
    import mcp_store
    orig = mcp_store.connection_secrets
    mcp_store.connection_secrets = lambda cid: {"cookie": "c=1", "user_agent": "MyUA/1.0"}
    try:
        check("_uas: UA user khai đứng đầu + còn UA mặc định",
              plug._uas()[0] == "MyUA/1.0" and len(plug._uas()) >= 2)
    finally:
        mcp_store.connection_secrets = orig

    # mọi UA bị chê → trả lỗi hướng dẫn đổi UA (KHÔNG trả rác)
    async def _get_bad(client, url):
        return UNSUPPORTED, BASE_HOME
    plug._get = _get_bad
    _p, _u, _ua, err = await plug._fetch("c=1", "/")
    check("_fetch: mọi UA bị chê → ERROR hướng dẫn đổi UA", bool(err) and err.startswith("ERROR") and "User-Agent" in err)
    r_feed_bad = await plug._feed({}, None)
    check("fb_feed_read: trang 'không hỗ trợ' → ERROR rõ (không trả rác)",
          r_feed_bad.startswith("ERROR") and "User-Agent" in r_feed_bad)

    # UA đầu bị chê, UA sau OK → tự chuyển, trả trang tốt
    calls = {"n": 0}
    async def _get_flaky(client, url):
        calls["n"] += 1
        return (UNSUPPORTED, BASE_HOME) if calls["n"] == 1 else (HOME, BASE_HOME)
    plug._get = _get_flaky
    page, _url, _ua2, err2 = await plug._fetch("c=1", "/")
    check("_fetch: UA đầu bị chê thì tự thử UA sau và qua được",
          err2 is None and "xc_message" in page and calls["n"] == 2)

    # trang đăng nhập theo NỘI DUNG (url vẫn mbasic, không /login) → báo cookie bị từ chối, KHÔNG đổi UA vô ích
    async def _get_login(client, url):
        return LOGINPAGE, BASE_HOME
    plug._get = _get_login
    _p3, _u3, _ua3, err3 = await plug._fetch("c=1", "/")
    check("_fetch: trang đăng nhập (nội dung) → ERROR cookie bị từ chối", bool(err3) and "từ chối" in err3)
    r_feed_login = await plug._feed({}, None)
    check("fb_feed_read: cookie bị từ chối → ERROR rõ (không đọc login thành feed)",
          r_feed_login.startswith("ERROR") and "ĐĂNG NHẬP" in r_feed_login)

    # trang splash (URL sạch, không ô email/mật khẩu) → vẫn phải báo cookie bị từ chối, KHÔNG trả thành feed
    async def _get_splash(client, url):
        return SPLASH, BASE_HOME
    plug._get = _get_splash
    r_feed_splash = await plug._feed({}, None)
    check("fb_feed_read: trang splash đăng nhập → ERROR (không trả splash thành feed)",
          r_feed_splash.startswith("ERROR") and "cookie" in r_feed_splash.lower())

    # mbasic bị Facebook khai tử: bị 302 sang m.facebook.com → báo mbasic NGỪNG PHỤC VỤ, KHÔNG đổ lỗi cookie
    check("_off_mbasic: bắt redirect ra khỏi mbasic",
          plug._off_mbasic("https://m.facebook.com/") and plug._off_mbasic("https://www.facebook.com/x")
          and not plug._off_mbasic("https://mbasic.facebook.com/home.php") and not plug._off_mbasic(""))
    async def _get_offmbasic(client, url):
        return LOGINPAGE, "https://m.facebook.com/"      # nội dung login nhưng đã rời mbasic
    plug._get = _get_offmbasic
    _po, _uo, _uao, erro = await plug._fetch("c=1", "/")
    check("_fetch: bị đá khỏi mbasic → báo mbasic NGỪNG PHỤC VỤ (không đổ lỗi cookie)",
          bool(erro) and "NGỪNG PHỤC VỤ" in erro and "m.facebook.com" in erro)
    r_feed_off = await plug._feed({}, None)
    check("fb_feed_read: mbasic ngừng phục vụ → ERROR đúng bệnh (không nói cookie hỏng)",
          r_feed_off.startswith("ERROR") and "mbasic" in r_feed_off.lower())

asyncio.run(fetch_tests())

if _fails:
    print(f"\nFAIL - {len(_fails)} test: {_fails}")
    sys.exit(1)
print("\nOK - test_fb_personal: tất cả pass")
