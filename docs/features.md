# Tính năng đã triển khai

| Tính năng | Lý do và giới hạn |
|---|---|
| Quét ảnh, chỉnh sửa từng detection | Box, nhãn và trạng thái sửa/bỏ được quản lý riêng cho từng vật thể |
| Khoanh vùng bị bỏ sót | Chạy YOLO lần hai trên crop ảnh và ghép detection mới về tọa độ ảnh gốc; demo ghi rõ không chạy model thật |
| Hướng dẫn theo điều kiện | Chọn một trong 166 vật thể KB, trả lời câu hỏi tình trạng và nhận hướng dẫn kèm nguồn/cảnh báo |
| Tra cứu thủ công | Vật liệu ngoài lớp YOLO vẫn tra cứu được, không bị gán thành dự đoán AI |
| Trợ lý Groq | Mọi câu hỏi gọi `openai/gpt-oss-20b` khi có key; KB là ngữ cảnh bổ sung, không phải cổng chặn LLM. Lỗi hoặc thiếu key dùng KB dự phòng |
| Lịch sử tóm tắt | Lưu localStorage; không lưu ảnh gốc |
| Giao diện song ngữ và tin môi trường | Việt/Anh; tin RSS tách dải bài mới và bài đã lưu |

Trạng thái và kiểm thử Beta01 được ghi trong [báo cáo tích hợp](CV_KB_INTEGRATION_REPORT.md). Cấu hình key chatbot ở [CHATBOT_GROQ.md](CHATBOT_GROQ.md).
