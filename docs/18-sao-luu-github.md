# Đồng bộ brain với GitHub (2 chiều)

Tính năng này đồng bộ **TẤT CẢ brain trong thư mục brains** (mọi bộ não: ghi chú, Wiki, ký ức, agent/workflow) với một repo GitHub **riêng tư** của bạn - theo CẢ HAI CHIỀU: đẩy thay đổi của máy này lên, đồng thời kéo thay đổi từ máy khác về. Mục đích: không mất dữ liệu khi hỏng máy/mất VPS, và **dùng được nhiều máy cùng lúc** (máy nhà + VPS) - các máy tự khớp dữ liệu với nhau qua repo.

> Nên để **mọi brain nằm trong thư mục brains** (tạo brain mới qua nút ➕ là tự vào đó). Đồng bộ lấy nguyên thư mục brains làm một khối, nên brain nào nằm ngoài (chọn folder ngoài bằng nút 📁) sẽ KHÔNG được đồng bộ chung - hãy chuyển nó vào brains.

Mở tại: trang **Tự học** (nhóm **Bộ não** trên thanh nav trái), kéo xuống mục **⇅ Đồng bộ brain với GitHub (2 chiều)**.

## Vì sao nên bật

Brain là toàn bộ tri thức Javis tích luỹ được về bạn và công việc. Nó nằm trên đĩa máy/VPS. Nếu chỉ có một bản, một sự cố là mất sạch. Đồng bộ với GitHub cho bạn:

- Bản sao ngoài, an toàn khi máy hỏng.
- Lịch sử từng lần thay đổi (xem lại, khôi phục điểm cũ).
- Làm việc xen kẽ nhiều máy: sửa ở máy nhà, VPS tự nhận được ở lần đồng bộ sau, và ngược lại.
- Máy mới chỉ cần dán repo + token rồi bấm đồng bộ là toàn bộ brain về lại đủ.

## Điều kiện

- Máy/VPS phải có **git** (mục Đồng bộ sẽ báo "máy chưa cài git" nếu thiếu). Trên Docker image chính thức đã có sẵn git.
- Một tài khoản GitHub.

## Cài đặt trong 3 bước

### Bước 1 - Tạo repo GitHub riêng tư

1. Vào https://github.com/new
2. Đặt tên, ví dụ `javis-brain-backup`.
3. Chọn **Private** (BẮT BUỘC - brain chứa dữ liệu cá nhân/kinh doanh, tuyệt đối không để Public).
4. **KHÔNG** tích "Add a README file" (để repo trống, tránh xung đột lần đẩy đầu).
5. Bấm **Create repository**. Copy URL dạng `https://github.com/<tên-bạn>/javis-brain-backup`.

### Bước 2 - Tạo token (fine-grained)

1. Vào https://github.com/settings/tokens?type=beta (Settings → Developer settings → **Fine-grained tokens** → Generate new token).
2. Đặt tên token, chọn thời hạn.
3. **Repository access** → Only select repositories → chọn đúng repo `javis-brain-backup`.
4. **Permissions** → Repository permissions → **Contents** → chọn **Read and write**.
5. Bấm Generate, **copy token** (dạng `github_pat_...`). Token chỉ hiện 1 lần - copy ngay.

### Bước 3 - Dán vào Javis

1. Mở trang **Tự học** → mục **⇅ Đồng bộ brain với GitHub (2 chiều)**.
2. Dán **URL repo (https)** và **GitHub token (fine-grained, quyền Contents)** vào ô tương ứng.
3. Kiểm tra ô **Nhánh**: mặc định là `main`. Repo của bạn dùng nhánh mặc định khác (ví dụ `master`) thì sửa ở đây, không thì đẩy lên sẽ trật nhánh.
4. Bấm **🔌 Kiểm tra kết nối** - phải hiện "Kết nối OK".
5. Bấm **⇅ Đồng bộ ngay** cho lần đầu.
6. Muốn tự động: bật công tắc **Tự động**, đặt **Tự đồng bộ mỗi (giờ)** (mặc định 6), rồi **💾 Lưu cấu hình**.

Dùng nhiều máy: làm đúng 3 bước này trên TỪNG máy (cùng repo, cùng nhánh, cùng token hoặc token riêng đều được). Bật Tự động ở cả hai nơi - các máy sẽ tự khớp nhau theo chu kỳ.

## Bảng tra nhanh ô nhập và nút

| Ô / nút | Việc nó làm |
|---|---|
| **URL repo (https)** | Repo GitHub riêng tư nhận backup, dạng `https://github.com/<bạn>/<repo>`. |
| **GitHub token (fine-grained, quyền Contents)** | Token đẩy/kéo. Lưu nội bộ trong `settings.json` ở dạng mã hoá, không bao giờ lên repo. |
| **Nhánh** | Nhánh sẽ đẩy lên, mặc định `main`. Ứng với khoá `backup.branch` trong `settings.json`. |
| **Tự đồng bộ mỗi (giờ)** | Chu kỳ tự chạy, mặc định 6. |
| **Tự động** | Công tắc bật/tắt chạy định kỳ, hiện **○ Tắt** khi đang tắt. |
| **🔌 Kiểm tra kết nối** | Thử kết nối repo + token, không đẩy gì. |
| **⇅ Đồng bộ ngay** | Chạy một lượt đồng bộ đầy đủ ngay lập tức. |
| **💾 Lưu cấu hình** | Ghi lại toàn bộ ô trên (kể cả công tắc Tự động và số giờ). |

## Cách nó hoạt động

Mỗi lượt đồng bộ làm 4 việc theo thứ tự:

1. **Chụp** thư mục brains vào một bản sao sạch (bỏ file nhạy cảm + git thô của từng brain) và ghi nhận thay đổi của máy này.
2. **Kéo về** bản mới nhất trên GitHub và **hoà nhập**: file khác nhau thì tự ghép; hai máy cùng sửa MỘT file thì **bản sửa mới hơn thắng**, bản thua được giữ nguyên thành file `.conflict-<local|remote>-<thời điểm>` ngay cạnh để bạn tự quyết; một bên sửa một bên xoá thì bản sửa thắng (không âm thầm mất dữ liệu).
3. **Áp kết quả** về thư mục brains của máy (file vừa sửa tay ngay trong lúc đồng bộ sẽ không bị đè - máy giữ bản của bạn, vòng sau tự hoà tiếp).
4. **Đẩy lên** GitHub (đẩy thường, KHÔNG force). Nếu máy khác vừa đẩy chen ngang, Javis tự kéo về hoà tiếp rồi đẩy lại.

Ghi chú an toàn của cơ chế:

- Token **không** được lưu vào brain hay đẩy lên repo. Nó nằm trong `settings.json` nội bộ (đã git bỏ qua). Thông báo lỗi cũng tự che token.
- File nhạy cảm bị loại khỏi đồng bộ: hội thoại gốc (`memory/conversations`), log loop/learn (`Javis/loop-log`, `Javis/learn-log`, `Javis/learn-staging`), thống kê dùng skill (`Javis/skill-usage.json`), khoá lock, file `.tmp`, và `.git` riêng của từng brain. Những file này chỉ nằm trên máy tạo ra chúng.
- Thùng rác brain (`brain-trash` trong thư mục state) nằm NGOÀI vùng đồng bộ nên không lên repo.
- Máy có thư mục brains **trống** (máy mới, volume mới) được coi là KHÔI PHỤC: chỉ nhận dữ liệu về, không bao giờ đẩy "trạng thái trống" lên đè mất backup.
- Xoá file/brain trên một máy thì lần đồng bộ sau các máy khác cũng xoá theo (đó là nghĩa của sync). Nhờ repo là git, mọi thứ vẫn nằm trong lịch sử commit - khôi phục được khi cần.

## Ảnh và file đính kèm: đẩy lên repo, nhưng tự hết hạn

Đây là chỗ dễ bất ngờ nhất, đọc kỹ một lần rồi thôi.

**Ảnh và file VẪN lên repo backup.** Hai thư mục `attachments/` và `inbox/` của brain (ảnh Javis tạo, file bạn gửi qua chat hoặc Telegram) **không** nằm trong danh sách loại trừ ở trên, nên chúng được chép nguyên vào bản sao và đẩy lên GitHub như file thường. Hệ quả thực tế: repo backup có thể phình nhanh vì ảnh, và mỗi tấm ảnh là một blob nằm vĩnh viễn trong lịch sử git.

**Trong khi đó, git RIÊNG của từng brain lại bỏ qua chúng.** Từ 0.9.247, `.gitignore` của mỗi brain có sẵn `attachments/`, `Attachments/`, `*attachments/`, `inbox/`, và Javis gỡ chúng khỏi index một lần cho brain cũ. Hai cơ chế này khác nhau và đều đúng theo thiết kế: git của brain là để version **tri thức đã chưng cất** (facts, Wiki, skill), còn repo backup là bản sao đầy đủ để cứu hộ.

**Media tự hết hạn, và việc xoá đó lan lên repo.** Javis coi `attachments/` và `inbox/` là vùng cache: cứ 6 tiếng một lần, file quá **30 ngày** bị xoá, và nếu tổng vượt trần **300 MB** thì xoá từ cũ tới mới cho tới khi xuống dưới trần. Vì hai thư mục này vẫn trong phạm vi đồng bộ, lần đồng bộ kế tiếp sẽ đẩy luôn việc xoá đó lên GitHub và sang máy còn lại.

Nghĩa là: **lời hứa "bản sao ngoài an toàn" đúng với ghi chú `.md`, nhưng không đúng với ảnh sau 30 ngày.** Ảnh cũ chỉ còn lấy lại được từ lịch sử commit của repo, không còn ở nhánh hiện tại. Muốn giữ ảnh lâu dài thì rút nội dung ra note `.md`, chuyển file sang thư mục khác của brain, hoặc nới/tắt luật dọn (khoá `media` trong `settings.json`). Chi tiết cách tắt ở [Khắc phục sự cố & FAQ](17-khac-phuc-su-co.md).

## Khôi phục brain trên máy mới

Không cần thao tác git tay: cài Javis, vào **Tự học → ⇅ Đồng bộ brain với GitHub (2 chiều)**, dán repo + token + đúng nhánh, bấm **⇅ Đồng bộ ngay** - toàn bộ brain về lại đủ. (Cách cũ `git clone` thẳng vào thư mục brains vẫn dùng được.)

## Xử lý file .conflict-*

Khi hai máy sửa cùng một file giữa hai lần đồng bộ, bạn sẽ thấy thêm file dạng `ten-file.conflict-local-20260702-101530.md` cạnh file gốc:

- File gốc = bản THẮNG (bản có lần sửa mới hơn).
- File `.conflict-*` = bản THUA, giữ nguyên nội dung để bạn so và gộp tay nếu cần.
- Xem xong thì xoá file `.conflict-*` đi (nó cũng đồng bộ giữa các máy như file thường).

## Lưu ý an toàn

- **Luôn dùng repo Private.** Brain có thể chứa số liệu kinh doanh, tên khách hàng, đôi khi cả khoá bạn lỡ dán trong hội thoại - và như mục trên đã nói, cả ảnh/file bạn gửi lên chat cũng đi theo.
- Token nên đặt thời hạn và chỉ cấp quyền **Contents** cho đúng repo đó - không cấp rộng hơn.
- Một repo dùng cho MỘT bộ brains. Đừng trỏ 2 hệ thống Javis khác mục đích (dữ liệu khác nhau hoàn toàn) vào cùng repo - chúng sẽ trộn dữ liệu vào nhau đúng như thiết kế sync.

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| "máy chưa cài git" | Cài git trên máy/VPS. Docker image chính thức đã có sẵn. |
| Kiểm tra kết nối báo lỗi 403 | Token thiếu quyền Contents: Read and write, hoặc chưa chọn đúng repo. |
| Đẩy được nhưng trên GitHub không thấy file ở nhánh quen thuộc | Ô **Nhánh** đang khác nhánh mặc định của repo (mặc định Javis dùng `main`). Sửa ô Nhánh cho khớp rồi Lưu cấu hình và đồng bộ lại. |
| "push liên tục bị vượt" | Nhiều máy đồng bộ cùng lúc liên tục. Bấm lại sau ít phút - cơ chế tự hoà sẽ khớp. |
| "Áp bản đồng bộ về máy lỗi N file" | Có file đang bị khoá/không ghi được trên máy (vd đang mở trong app khác). Lần này KHÔNG đẩy gì lên (an toàn), đóng app đang giữ file rồi đồng bộ lại. |
| Thấy nhiều file `.conflict-*` | Hai máy hay sửa cùng file giữa hai lần đồng bộ. Rút ngắn chu kỳ Tự động, hoặc chia việc mỗi máy một mảng; xử lý file conflict theo mục ở trên. |
| Repo backup phình rất nhanh | Ảnh trong `attachments/`/`inbox/` cũng được đẩy lên. Xem mục "Ảnh và file đính kèm" ở trên; cân nhắc để luật dọn media chạy thay vì tắt nó. |
| Ảnh cũ biến mất khỏi repo | Đúng thiết kế: media quá 30 ngày bị dọn trên máy rồi lan lên repo. Lấy lại từ lịch sử commit, hoặc nới `media.max_age_days` trong `settings.json`. |
| Muốn ngừng tự động | Tắt công tắc Tự động rồi Lưu cấu hình. Vẫn bấm "Đồng bộ ngay" thủ công được. |

---

Liên quan: [08 - Việc định kỳ & Nhắc hẹn](08-viec-dinh-ky.md) · [13 - Second Brain: bộ nhớ, Wiki](13-second-brain-bo-nho-wiki.md) · [22 - Tự học](22-tu-hoc.md) · [17 - Khắc phục sự cố](17-khac-phuc-su-co.md)
