"""Test khối B UX Kết nối: nhóm Google một cửa + wizard steps + dùng lại key client.

Chạy: cd server && ../.venv/Scripts/python.exe -m pytest test_connect_group.py -q
"""
import mcp_catalog
import mcp_store

GOOGLE_GROUP = {"google-workspace", "google-tasks", "google-calendar",
                "gmail", "google-keep", "google-sheets"}
STEP_CONNECTORS = {"google-workspace", "google-tasks", "google-calendar",
                   "gmail", "google-keep"}


def _public():
    return {c["id"]: c for c in mcp_catalog.public_catalog()}


def test_nhom_google_du_thanh_vien():
    pc = _public()
    got = {cid for cid, c in pc.items() if c.get("group") == "google"}
    assert got == GOOGLE_GROUP
    # Google Ads KHÔNG thuộc nhóm (mảng Quảng cáo, mental model khác)
    assert pc["google-ads"].get("group", "") == ""


def test_moi_thanh_vien_nhom_co_group_line():
    pc = _public()
    for cid in GOOGLE_GROUP:
        line = pc[cid].get("group_line", "")
        assert line, cid
        assert len(line) <= 120, f"{cid}: group_line dài quá ({len(line)})"
        assert "—" not in line, f"{cid}: group_line chứa em dash"


def test_steps_dung_schema():
    pc = _public()
    for cid in STEP_CONNECTORS:
        steps = pc[cid].get("steps") or []
        assert len(steps) >= 4, f"{cid}: quá ít bước"
        for i, s in enumerate(steps):
            assert s.get("text", "").strip(), f"{cid} bước {i}: thiếu text"
            assert len(s["text"]) <= 260, f"{cid} bước {i}: text dài quá"
            assert "—" not in s["text"], f"{cid} bước {i}: em dash"
            if s.get("link"):
                assert s["link"].startswith("https://"), f"{cid} bước {i}: link không https"
                assert s.get("link_label", "").strip(), f"{cid} bước {i}: có link phải có nhãn"
            assert s.get("copy", "") in ("", "redirect"), f"{cid} bước {i}: copy lạ"


def test_oauth_google_co_buoc_redirect():
    """Connector oauth BYO của Google phải có đúng một bước chèn ô copy Redirect URI."""
    pc = _public()
    for cid in ("google-calendar", "gmail"):
        n = sum(1 for s in pc[cid]["steps"] if s.get("copy") == "redirect")
        assert n == 1, cid


def test_public_catalog_khong_lo_secret_noi_bo():
    """steps/group là trường hiển thị - không được kéo theo validate/arg_rules nội bộ."""
    for c in mcp_catalog.public_catalog():
        assert "validate" not in c and "arg_rules" not in c


# ---- reuse_client_fields: copy key server-side ----

def _target_con():
    return {"auth": {"fields": [{"key": "client_id"}, {"key": "client_secret"},
                                {"key": "user_email"}]}}


def test_reuse_copy_du_hai_key(monkeypatch):
    monkeypatch.setattr(mcp_store, "connection_secrets",
                        lambda cid: {"client_id": "abc.apps", "client_secret": "GOCSPX-x",
                                     "api_key": "leak-me-not"})
    out = mcp_store.reuse_client_fields(_target_con(), {}, "src1")
    assert out == {"client_id": "abc.apps", "client_secret": "GOCSPX-x"}


def test_reuse_khong_de_gia_tri_user_nhap(monkeypatch):
    monkeypatch.setattr(mcp_store, "connection_secrets",
                        lambda cid: {"client_id": "cu.apps", "client_secret": "GOCSPX-cu"})
    out = mcp_store.reuse_client_fields(_target_con(), {"client_id": "moi.apps"}, "src1")
    assert out["client_id"] == "moi.apps"          # user nhập thì giữ
    assert out["client_secret"] == "GOCSPX-cu"     # thiếu mới copy


def test_reuse_chi_copy_key_thuoc_fields_dich(monkeypatch):
    monkeypatch.setattr(mcp_store, "connection_secrets",
                        lambda cid: {"client_id": "abc", "client_secret": "x"})
    target = {"auth": {"fields": [{"key": "api_key"}]}}   # đích không nhận client key
    out = mcp_store.reuse_client_fields(target, {}, "src1")
    assert out == {}


def test_reuse_khong_from_thi_giu_nguyen():
    fields = {"client_id": "a"}
    out = mcp_store.reuse_client_fields(_target_con(), fields, "")
    assert out == fields
