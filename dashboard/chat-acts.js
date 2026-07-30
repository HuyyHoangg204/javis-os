/* chat-acts.js - hang nut duoi moi tin nhan trong khung chat Javis.

   Moi bong bong (cua anh va cua Javis) co mot hang nho ben duoi: gio gui, gui lai,
   sua lai (chi tin nguoi dung), sao chep. Hang nay AN san (opacity 0), chi hien khi
   hover tren may tinh hoac khi cham vao tin tren dien thoai (.acts-on).

   File nay chi giu phan THUAN (khong dung tai lieu DOM that) de test bang node:
     node dashboard/test_chat_acts.js
   Phan gan su kien nam trong app.js vi no can sendMessage / chatInput.

   Ghi chu: KHONG dung ky tu em dash o bat ky dau. */
(function () {
  "use strict";

  var THU = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];

  // File này chạy hai chế độ: trong trình duyệt và dưới node (test require nó).
  // Dưới node không có window nên không có ic() - trả về chuỗi rỗng để phần logic
  // vẫn test được mà không phải kéo cả tầng icon vào. Trong trình duyệt thì
  // icons.js đã nạp trước (index.html bảo đảm thứ tự, có test canh) nên lấy
  // được hàm thật.
  var ic = (typeof window !== "undefined" && window.ic) ? window.ic : function () { return ""; };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  // Tin cu luu tu truoc ban nay khong co moc thoi gian -> tra "" de AN phan gio,
  // KHONG duoc lay gio hien tai vi nhu vay la bia so lieu.
  function toDate(ts) {
    if (!ts) return null;
    var d = new Date(ts);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtTime(ts) {
    var d = toDate(ts);
    return d ? pad2(d.getHours()) + ":" + pad2(d.getMinutes()) : "";
  }

  function fmtTimeFull(ts) {
    var d = toDate(ts);
    if (!d) return "";
    return THU[d.getDay()] + ", " + pad2(d.getDate()) + "/" + pad2(d.getMonth() + 1) +
      "/" + d.getFullYear() + " " + fmtTime(ts);
  }

  // role: "user" | "javis". Tin cua Javis khong co nut sua (sua cau tra loi cua may
  // roi gui di thi khong con y nghia gi) - nut gui lai o do chay lai CAU HOI ngay tren no.
  //
  // canResend=false khi khong co CHU de gui lai (tin chi co anh, khong kem loi nhan).
  // Khi do bo han nut gui lai + sua lai thay vi de nut bam vao khong ra gi. Bo trong
  // tham so nay thi mac dinh van co nut, de cac cho goi cu khong doi hanh vi.
  function actsHtml(role, ts, canResend) {
    var t = fmtTime(ts);
    var time = t
      ? '<span class="msg-time" title="' + esc(fmtTimeFull(ts)) + '">' + esc(t) + "</span>"
      : "";
    var send = "";
    if (canResend !== false) {
      var retryTitle = role === "user" ? "Gửi lại câu này" : "Trả lời lại câu hỏi phía trên";
      send = '<button class="msg-act" type="button" data-act="retry" title="' + esc(retryTitle) + '">↻</button>' +
        (role === "user"
          ? '<button class="msg-act" type="button" data-act="edit" title="Sửa lại rồi gửi">' + ic("pencil") + '</button>'
          : "");
    }
    return '<div class="msg-acts">' + time + send +
      '<button class="msg-act" type="button" data-act="copy" title="Sao chép nội dung">⧉</button>' +
      "</div>";
  }

  function isUserMsg(el) {
    return !!(el && el.classList && el.classList.contains("msg-user"));
  }

  // Nut "tra loi lai" o tin Javis: nguoc len tren tim tin nguoi dung gan nhat roi gui
  // lai dung chu goc do (luu o dataset.text, khong lay tu DOM da render vi tin dai bi
  // thu gon va tin Javis da thanh HTML).
  function prevUserText(msgEl) {
    var el = msgEl ? msgEl.previousElementSibling : null;
    while (el) {
      if (isUserMsg(el)) return (el.dataset && el.dataset.text) || "";
      el = el.previousElementSibling;
    }
    return "";
  }

  var API = {
    fmtTime: fmtTime,
    fmtTimeFull: fmtTimeFull,
    actsHtml: actsHtml,
    prevUserText: prevUserText,
    isUserMsg: isUserMsg,
  };

  if (typeof window !== "undefined") window.JavisActs = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})();
