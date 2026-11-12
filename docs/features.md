# Tính năng đã triển khai

| Tính năng | Lý do và giới hạn |
|---|---|
| Quét ảnh nhiều vật thể, overlay box | Luồng chính; demo chỉ là ảnh minh họa, real cần checkpoint ba lớp |
| Thẻ Nên làm / Tránh làm / Lưu ý | Chuyển lớp vật liệu thành hành động; không kết luận tái chế chắc chắn |
| Thêm/bỏ nhóm thủ công | Sửa gợi ý ngay trên UI; hiện chưa lưu feedback thành dữ liệu train |
| Tra cứu sáu vật liệu | Ba loại ngoài CV luôn ghi “chỉ tra cứu thủ công” |
| Trợ lý tra cứu theo JSON | Hoạt động offline với API local, không bịa câu trả lời ngoài KB |
| Lịch sử tóm tắt, nút xóa | Lưu localStorage, không lưu ảnh gốc |
