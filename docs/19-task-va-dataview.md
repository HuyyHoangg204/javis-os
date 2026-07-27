# Task & Dataview trong note

Từ bản 0.9.216, note trong brain của Javis "sống" hơn hẳn theo kiểu Obsidian: ô checkbox `- [ ]` trong note **bấm được và tự lưu**, còn khối ` ```dataview ` **chạy thật** ngay trong dashboard - hiện danh sách việc, danh sách note, bảng tổng hợp lấy từ toàn bộ brain. Hai tính năng này lấy cảm hứng từ hai plugin nổi tiếng của Obsidian là **Tasks** và **Dataview**, được Javis tự cài lại gọn nhẹ, không cần cài Obsidian hay plugin nào cả.

## 1. Checkbox task bấm được

### Tính năng là gì

Trong file markdown, một dòng việc viết theo cú pháp chuẩn:

```markdown
- [ ] Gọi lại khách hàng A
- [x] Chốt báo giá lô hàng thép
```

Trước đây Javis chỉ hiển thị mấy ô này cho đẹp, muốn tick phải mở chế độ Nguồn sửa tay chữ `[ ]` thành `[x]`. Giờ thì bấm thẳng vào ô vuông là xong: dấu tick hiện ra, chữ gạch ngang, và **file được lưu ngay lập tức** - không cần bấm nút 💾 Lưu.

### Tick ở đâu

- **Trang Tệp tin / trang Bộ não**: mở một file `.md`, để ở chế độ **Sửa** (bản render, mặc định). Bấm checkbox là tick và tự lưu.
- **Khung sửa file bung ra từ chat** (khi bấm vào link file trong câu trả lời của Javis): y hệt, tick là lưu.
- **Trong tin nhắn chat**: checkbox chỉ để xem, không bấm được. Lý do: nội dung chat không gắn với file nào để ghi lại.
- **Trong kết quả khối dataview**: bấm được, ghi thẳng vào file gốc chứa việc đó (xem phần 2).

### Ký hiệu ngày và độ ưu tiên (kiểu plugin Tasks)

Javis hiểu các ký hiệu emoji mà plugin obsidian-tasks dùng, viết ngay trong dòng việc:

| Ký hiệu | Ý nghĩa | Ví dụ |
|---|---|---|
| 📅 | Hạn chót (due) | `- [ ] Nộp báo cáo 📅 2026-08-01` |
| ⏳ | Ngày dự kiến làm | `- [ ] Soạn slide ⏳ 2026-07-30` |
| 🛫 | Ngày bắt đầu | `- [ ] Chiến dịch Tết 🛫 2026-12-01` |
| ✅ | Ngày hoàn thành | tự sinh khi tick xong |
| 🔺 ⏫ 🔼 🔽 ⏬ | Độ ưu tiên từ cao nhất tới thấp nhất | `- [ ] Xử lý khiếu nại ⏫` |

Hai hành vi tự động giống plugin Tasks:

- Việc **có ký hiệu ngày** (📅/⏳/🛫/🔁) khi tick xong sẽ tự được gắn thêm `✅ 2026-07-28` (ngày hôm đó); bỏ tick thì ngày ✅ được gỡ ra.
- Checklist thường (không có ký hiệu nào) thì tick chỉ đổi `[ ]` thành `[x]`, **không** chèn thêm gì vào chữ của bạn.

Việc có 📅 mà đã quá hạn sẽ hiện badge đỏ trong kết quả dataview để đập vào mắt.

## 2. Khối dataview - truy vấn note như cơ sở dữ liệu

### Tính năng là gì

Chèn một khối code với ngôn ngữ `dataview` vào bất kỳ note nào:

````markdown
```dataview
TASK WHERE !completed
```
````

Khi mở note đó trong Javis (hoặc khi Javis dán khối này vào câu trả lời chat), khối không hiện dưới dạng code nữa mà **chạy truy vấn thật** trên toàn bộ note `.md` của brain đang chọn và vẽ kết quả: danh sách việc chưa xong, gom theo từng file, tick được từng việc.

Ba loại truy vấn:

- `TASK` - liệt kê các dòng việc `- [ ]` / `- [x]`, gom nhóm theo file, có checkbox tick được.
- `LIST` - liệt kê note (mỗi dòng một link, bấm mở note luôn).
- `TABLE` - bảng: mỗi hàng một note, cột lấy từ frontmatter hoặc thông tin file.

### Các mệnh đề hỗ trợ

Viết theo thứ tự quen thuộc của Dataview: dòng đầu là loại truy vấn, sau đó tuỳ chọn `FROM`, `WHERE`, `SORT`, `LIMIT`.

**FROM - khoanh vùng lấy dữ liệu:**

````markdown
```dataview
TASK FROM "01 - Daily"
```
````

- `"thư mục"` - chỉ lấy note trong thư mục đó (tính cả thư mục con).
- `#tag` - chỉ lấy note mang tag đó (tag trong frontmatter hoặc `#tag` viết trong bài).
- Kết hợp: `FROM "05 - Việc" OR #du-an`, `FROM "notes" AND -#luu-tru` (dấu `-` hoặc `!` là loại trừ).
- Không có `FROM` thì quét cả brain.

**WHERE - lọc theo điều kiện:**

````markdown
```dataview
TASK WHERE !completed AND due <= date(today)
```
````

- Với `TASK`, các trường có sẵn: `completed` (đã tick chưa), `text` (nội dung việc), `due`, `scheduled`, `start`, `done` (các ngày dạng `2026-08-01`), `priority` (0 cao nhất, 3 mặc định, 5 thấp nhất), `tags`, `file.name`, `file.folder`.
- Với `LIST` / `TABLE`, dùng thẳng tên trường frontmatter của note (`status`, `type`...), cùng `tags`, `file.name`, `file.folder`, `file.mtime`.
- Phép so sánh: `=`, `!=`, `>`, `<`, `>=`, `<=`. Ngày so sánh được vì cùng định dạng `YYYY-MM-DD`.
- `date(today)`, `date(tomorrow)`, `date(yesterday)`, `date("2026-12-31")`.
- `contains(text, "khách")` - chuỗi chứa chuỗi; `contains(tags, "#ban-hang")` - mảng chứa phần tử.
- Kết hợp `AND` / `OR` / `!` / ngoặc `( )` thoải mái.

**SORT và LIMIT:**

````markdown
```dataview
TASK WHERE !completed SORT due ASC LIMIT 10
```
````

- `SORT trường ASC` (tăng dần, mặc định) hoặc `DESC` (giảm dần).
- `LIMIT n` - lấy tối đa n kết quả.

**Cột trong TABLE:**

````markdown
```dataview
TABLE status AS "Trạng thái", file.folder AS "Thư mục"
FROM #du-an
SORT file.mtime DESC
```
````

- Liệt kê cột cách nhau dấu phẩy, `AS "Tên cột"` để đặt tên đẹp.
- Cột đầu tiên luôn là link tới file; muốn bỏ thì viết `TABLE WITHOUT ID ...`.

### Tick việc ngay trong kết quả

Kết quả `TASK` có checkbox y như trong note. Tick một cái là Javis ghi thẳng vào **file gốc** chứa dòng việc đó, kể cả khi bạn đang đứng ở một note tổng hợp khác. Có rào an toàn: nếu file gốc vừa bị sửa (dòng việc không còn đúng chỗ cũ), Javis tự dò lại đúng dòng theo nội dung; dò không chắc chắn thì báo lỗi "File đã thay đổi" và **không ghi bừa** - bạn tải lại trang rồi tick lại là được.

### Ví dụ thực dụng

Việc quá hạn, gấp nhất lên đầu:

````markdown
```dataview
TASK WHERE !completed AND due < date(today) SORT priority ASC
```
````

Bảng dự án đang chạy, mới sửa gần đây nhất lên đầu:

````markdown
```dataview
TABLE status AS "Trạng thái", deadline AS "Hạn"
FROM "03 - Projects"
WHERE status != "done"
SORT file.mtime DESC
```
````

Note nhắc tới một khách hàng:

````markdown
```dataview
LIST WHERE contains(file.name, "Chị Nga") OR contains(tags, "#chi-nga")
```
````

Việc của riêng một note/thư mục Daily tuần này:

````markdown
```dataview
TASK FROM "01 - Daily" WHERE !completed LIMIT 20
```
````

### Chưa hỗ trợ gì

Đây là bản "lite", cố tình chỉ phủ phần hay dùng nhất. Chưa có:

- `dataviewjs` (khối chạy code JavaScript) - khối sẽ hiện thông báo rõ ràng thay vì im lặng.
- `FLATTEN`, `GROUP BY` tuỳ ý (TASK vốn đã tự gom theo file), hàm `dur(...)` cộng trừ thời gian.
- `[[link]]` trong `FROM`.

Gặp cú pháp chưa hỗ trợ, khối hiện thông báo lỗi kèm nguyên văn truy vấn để bạn sửa, không bao giờ vỡ trang.

### Hiệu năng và giới hạn kỹ thuật

Dataview được thiết kế để vault lớn vẫn mượt, ba tầng tiết kiệm tự động:

- **Cache tăng dần ở server**: chỉ mục note được giữ trong RAM, mỗi lần gọi chỉ đọc và parse lại đúng những file vừa sửa (so theo thời gian sửa + dung lượng), phần còn lại dùng bản đã có. Vault hàng nghìn note: lần đầu sau khi khởi động server hơi chậm, từ lần hai chỉ còn vài chục ms.
- **ETag / 304**: không có note nào đổi thì server trả gói rỗng thay vì gửi lại cả cục chỉ mục, trình duyệt dùng lại bản cũ.
- **Khoanh vùng theo FROM**: truy vấn dùng `FROM "thư mục"` thì chỉ quét đúng nhánh đó thay vì cả brain. Vì vậy **nên viết FROM thư mục cụ thể** khi có thể, ví dụ chỉ quan tâm nhật ký thì `FROM "01 - Daily Log" OR "02 - Weekly Log" OR "03 - Monthly Log" OR "04 - Future Log"` nhanh hơn hẳn quét cả vault. Nhánh `FROM` chỉ có `#tag` thì vẫn phải quét cả brain (tag nằm rải rác mọi nơi).

Giới hạn còn lại:

- Chỉ mục tối đa **20.000 note** mỗi brain, bỏ qua file `.md` nặng hơn 1MB và các thư mục ẩn (`.git`, `.obsidian`, `.trash`...).
- Trình duyệt giữ kết quả khoảng **15 giây** rồi mới hỏi lại server: vừa sửa note xong mà khối chưa cập nhật thì đợi vài giây rồi mở lại note chứa khối. Tick task thì cập nhật ngay, không phải đợi.
- Task nằm **trong khối code** của note khác không bị nhặt nhầm (ví dụ code mẫu có chứa `- [ ]`).

## Khắc phục sự cố

- **Bấm checkbox không ăn**: kiểm tra bạn đang ở chế độ **Sửa** (bản render) chứ không phải **Nguồn**; trong chat thì checkbox vốn chỉ để xem. Nếu vẫn không ăn, khả năng server đang chạy bản cũ hơn 0.9.216 - cập nhật rồi tải lại trang (Ctrl+Shift+R).
- **Khối dataview hiện "Đang chạy truy vấn…" mãi**: server chưa có API `/files/mdindex` (bản cũ). Cập nhật Javis rồi khởi động lại server.
- **Kết quả trống dù chắc chắn có việc**: xem lại `FROM` - tên thư mục phải đúng nguyên văn (có dấu, có số thứ tự, ví dụ `"05 - Việc"` chứ không phải `"Việc"`); tag phải có `#`.
- **Báo "File đã thay đổi - tải lại rồi tick lại"**: file gốc vừa bị sửa chỗ khác (bởi bạn hoặc bởi Javis). Tải lại trang cho khối chạy lại với dữ liệu mới rồi tick lại.

Xem thêm: [Quản lý tệp tin](05-quan-ly-tep-tin.md) (mở và sửa note), [Second Brain: bộ nhớ, Wiki, INGEST](13-second-brain-bo-nho-wiki.md) (cấu trúc brain), [Khắc phục sự cố & FAQ](17-khac-phuc-su-co.md).
