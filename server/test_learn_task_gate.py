"""Cửa gác việc learn tự tạo: loại việc worker nền KHÔNG THỂ làm.

Bối cảnh thật (0.9.232): bảng Kanban brain chính có 28 việc, 100% do learn tự tạo, và
những việc kiểu "cập nhật cookie Facebook", "gửi link Drive vào Zalo nhóm", "theo dõi
duyệt bài Substack" đều kết thúc archived/cancelled - vì worker nền là headless, chỉ
thao tác file trong brain, không có tay người dùng, không có trình duyệt đăng nhập, và
không được gửi ra ngoài. Việc như vậy vào hàng đợi là chắc chắn hỏng: tốn một lượt
worker, tốn quota, rồi bắn một thông báo "bị chặn" làm phiền chủ.

Gác ở cửa vào rẻ hơn hẳn chặn lúc chạy (kernel vốn đã chặn external-write mode != full).
"""
import learn


def _lyDo(title, intent=""):
    return learn.task_infeasible(title, intent)


# ---- Việc PHẢI bị loại (ca thật lấy từ bảng Kanban) ----

def test_loai_viec_can_tay_nguoi_dung():
    """Cookie/đăng nhập/OTP: chỉ chủ mới làm được, worker không có trình duyệt đăng nhập."""
    assert _lyDo("Cập nhật cookie Facebook cá nhân (đã hết hạn)")
    assert _lyDo("Xác thực Google Workspace OAuth tài khoản hi@minhquy.vn")
    assert _lyDo("Đăng nhập lại Zalo", "phiên hết hạn cần quét mã QR")


def test_loai_viec_gui_ra_ngoai():
    """Gửi tin/đăng bài: learn luôn tạo task mode auto → kernel chặn ở bước chạy.
    Chặn sớm ở cửa vào cho khỏi tốn một lượt worker rồi mới báo lỗi."""
    assert _lyDo("Tìm đúng link Drive record coaching chị Nga và gửi vào Zalo nhóm")
    assert _lyDo("Đăng bài tổng hợp lên Facebook Page")
    assert _lyDo("Trả lời bình luận khách trên bài quảng cáo")


def test_loai_viec_cho_nguoi_khac_lam():
    """Theo dõi/chờ duyệt: không có việc gì để worker làm, chỉ là nhắc hẹn trá hình."""
    assert _lyDo("Theo dõi duyệt & publish bài Substack 'AI automation'")
    assert _lyDo("Chờ đối tác phản hồi báo giá")


def test_loai_viec_dung_cham_ma_nguon_ngoai_brain():
    """Ca WarriorPlus: sửa code một dự án KHÁC không nằm trong brain - worker cắm đầu
    tìm shell, tìm GitHub API rồi chặn. Brain không chứa repo đó."""
    assert _lyDo(
        "Thiết kế credit bonus cho subscription WarriorPlus",
        "Sửa luồng IPN trong repo ShortMason để bonus chỉ cộng ở giao dịch đầu",
    )


# ---- Việc PHẢI được đi qua (không gác quá tay) ----

def test_giu_viec_thao_tac_file_trong_brain():
    assert not _lyDo("Ghi chú 3 lỗi giọng nói cần sửa")
    assert not _lyDo("Đối chiếu danh mục web vs POS Làng Chài Xưa",
                     "Đọc 2 file trong brain rồi lập bảng chênh lệch vào một note mới")
    assert not _lyDo("Tổng hợp bảng giá Submagic vào note",
                     "Đọc trang pricing rồi ghi lại thành note trong brain")


def test_giu_viec_doc_du_lieu_that():
    """Đọc MCP là năng lực worker CÓ - đừng chặn nhầm."""
    assert not _lyDo("Kiểm tra kết nối POS Kim Khí Hà Lộc bị mất")
    assert not _lyDo("Lấy doanh thu tuần này từ POS và ghi vào Data Cache")


def test_ly_do_la_tieng_viet_ngan():
    """Lý do đi vào report['blocked'] cho chủ đọc - phải là câu người hiểu, không phải mã."""
    reason = _lyDo("Cập nhật cookie Facebook cá nhân")
    assert isinstance(reason, str) and 0 < len(reason) <= 120
    assert reason == reason.strip()
