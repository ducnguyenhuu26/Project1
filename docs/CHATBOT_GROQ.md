# Cấu hình chatbot Groq

Chatbot gọi Groq từ FastAPI. Trình duyệt chỉ gọi `/api/v1/chat`; API key chỉ được lưu ở backend.

1. Tạo API key tại [Groq Console](https://console.groq.com/keys).
2. Thêm vào `.env` ở thư mục gốc (không commit file này):

   ```env
   GROQ_API_KEY=your-key
   GROQ_MODEL=openai/gpt-oss-20b
   ```

3. Khởi động lại backend. Khi có key, mọi câu hỏi đều được gửi tới Groq; KB chỉ là ngữ cảnh bổ sung khi có mục phù hợp. Nếu không có KB khớp, mô hình vẫn trả lời bằng hướng dẫn chung an toàn. Khi thiếu key hoặc Groq lỗi/hết hạn mức, endpoint mới dùng câu trả lời dự phòng từ KB.

Backend gửi câu hỏi, tối đa 8 lượt chat gần nhất và đoạn KB phù hợp nếu tìm được. Nó không gửi ảnh. Mô hình có thể đưa hướng dẫn xử lý phổ thông khi KB không có mục khớp, nhưng không được bịa địa chỉ thu gom, chương trình đang hoạt động, quy định địa phương hoặc cam kết an toàn. Giao diện phân biệt `Groq AI · tham khảo KB`, `Groq AI · kiến thức chung` và `KB dự phòng`.

Model production đang dùng là `openai/gpt-oss-20b`. Gói miễn phí có giới hạn theo tài khoản/model; vượt giới hạn sẽ trả lỗi rate limit và chatbot quay về KB. Không gửi dữ liệu cá nhân hoặc thông tin nhạy cảm qua chatbot. Xem [model hiện có](https://console.groq.com/docs/models), [giới hạn API](https://console.groq.com/docs/rate-limits) và [chính sách dữ liệu](https://console.groq.com/docs/your-data).
