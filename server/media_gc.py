"""
media_gc.py - Dọn vùng cache media của brain.

Vì sao tồn tại: ảnh Javis tự tạo (image_gen.py:202) và file user gửi qua Telegram
(main.py:6242) rơi vào `<brain>/attachments/` và `<brain>/inbox/` rồi nằm đó vĩnh viễn.
Không ai dọn, mà trước đây chúng còn được commit vào git của brain nên xoá file cũng
không lấy lại được dung lượng. Quyết định: hai thư mục đó là VÙNG CACHE, không phải tri
thức. Tri thức là file .md. Cái gì trong đó cũng có thể biến mất mà brain vẫn nguyên vẹn.

Tách làm hai tầng để test được:
  - plan_deletions: THUẦN. Nhận sẵn danh sách (path, size, mtime), trả danh sách cần xoá.
    Không chạm đĩa, không đọc đồng hồ -> test không cần fixture.
  - scan / media_dirs / sweep: chạm đĩa. Dùng os.scandir và phải gọi qua asyncio.to_thread.

Stdlib-only.
"""
from __future__ import annotations

import os
import re
import time


def plan_deletions(entries, now, max_age_days, max_mb):
    """Quyết định file nào phải xoá. HÀM THUẦN.

    entries      : list[(path, size_bytes, mtime)] - mọi file trong vùng cache của MỘT brain.
    now          : mốc thời gian tham chiếu (time.time()).
    max_age_days : file già hơn ngần này ngày thì xoá. <= 0 = tắt luật tuổi.
    max_mb       : trần dung lượng vùng cache. <= 0 = tắt luật trần.

    Trả list path theo ĐÚNG thứ tự xoá: nhóm quá hạn trước, rồi nhóm bị trần cắt (cũ tới mới).

    File .md không bao giờ bị xoá: vùng cache có thể lạc note vào, mà note là tri thức.
    """
    giu = [t for t in entries if not str(t[0]).lower().endswith(".md")]
    xoa, con_lai = [], []
    if max_age_days and max_age_days > 0:
        han = now - max_age_days * 86400.0
        for t in giu:
            (xoa if t[2] < han else con_lai).append(t)
    else:
        con_lai = list(giu)
    if max_mb and max_mb > 0:
        tran = max_mb * 1024 * 1024
        tong = sum(t[1] for t in con_lai)
        # Trần là van an toàn cho trường hợp sinh cả trăm ảnh trong một ngày: lúc đó
        # luật tuổi chưa kịp cứu. Xoá từ CŨ NHẤT và dừng ngay khi xuống dưới trần.
        for t in sorted(con_lai, key=lambda x: x[2]):
            if tong <= tran:
                break
            xoa.append(t)
            tong -= t[1]
    return [t[0] for t in xoa]
