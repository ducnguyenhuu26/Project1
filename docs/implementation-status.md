# Trạng thái 12/11/2026

## Bổ sung kiến trúc taxonomy (12/11/2026)

- `backend/taxonomy.json` là registry taxonomy `2026-11-12.1`, phân biệt object/category ID, material và handling stream. Chỉ ba ID legacy (`plastic`, `paper`, `metal`) đang có detector mapping; các ID còn lại là manual-only, chưa phải lớp đã huấn luyện.
- `model_manifest.json` đặt cạnh checkpoint có class map theo ID. Checkpoint cũ không có manifest dùng adapter cố định 0=Plastic, 1=Paper, 2=Metal. Manifest sai phiên bản, ID hoặc tên lớp bị từ chối; health báo `invalid_manifest` và scan trả 503.
- API scan trả `category_id`, nhãn chuẩn hóa, bbox, confidence, nguồn, model version; `material_id` vẫn được trả tương thích. Frontend sửa nhãn theo từng box và thêm mục tra cứu tay riêng. Các sửa đổi chỉ lưu ở local history; không gửi làm nhãn huấn luyện.
- `ml/scripts/build_multisource.py` tạo bundle COCO→YOLO có audit issues, provenance, visualization sample và deterministic group split; chỉ nhận taxonomy class `ready_for_training`, nhưng **chưa có dataset đa lớp nào được build**. `ml/config/dataset_sources.json` đánh dấu các mapping cần review; TACO là ứng viên object detection, SWiM3 license vẫn chưa xác minh trong checkout.
- `train_multiclass.py --preflight-only` kiểm tra YAML, split, labels, taxonomy, disk và CUDA request mà không train. Run GPU chưa được khởi chạy. `train.py` và baseline SWiM3 ba lớp không bị sửa.
- Trạng thái coverage: Plastic/Paper/Metal = `ready_for_training` cho baseline đang có; Glass, Organic, Textile, Rubber, E-waste, Battery, Composite, Sanitary, Ceramic, Wood, Sharps, Chemical container = `manual_only` cho sản phẩm; các mapping nguồn TACO/SWiM3 ngoài baseline = `blocked` tới khi license/annotation mapping được rà soát.

- Backend FastAPI: health, scan, waste-types, chat; demo/real detector, validate upload, 503 khi thiếu model. Real adapter đã được thử bằng checkpoint mini ba lớp.
- Frontend React/Vite: upload, ảnh mẫu, overlay, kết quả, hướng dẫn, tra cứu theo checkpoint, sửa/ẩn từng detection, thêm nhãn thủ công, trợ lý, lịch sử local.
- Dữ liệu: tạo `datasets/swim3_clean` từ ZIP SWiM3 thật có directory entries Windows; 5.131/368/381 ảnh train/val/test, kiểm toán lại 0 lỗi và 0 overlap family/SHA/dHash gần (≤2 bit). Xem `docs/data-audit.md`.
- CPU smoke: YOLO26n, 24 train/12 val, 256 px, 1 epoch; mAP50 ≈0,167, mAP50:95 ≈0,056. **Chỉ xác nhận code train/val/weights/API chạy**, tập nhỏ mất cân bằng nên không dùng làm kết luận chất lượng. Trên CPU i5-1335U, checkpoint mini tại 640 px đạt median ~70 ms / p95 ~158 ms qua 10 lần trên một ảnh minh họa; đây không phải benchmark YOLO26s hoặc tải phục vụ thực tế.
- YOLO26s pretrained đã được tải và nạp thành công; CPU smoke **24 train/12 val, 256 px, 1 epoch** tạo được `best.pt` 3 lớp và `evaluate.py` đọc được. mAP50 ≈0,028 và mAP50:95 ≈0,015 trên chỉ 12 ảnh; số này chỉ chứng minh đường train/evaluate của **s** chạy, không so chất lượng với n hay dự báo train đầy đủ.
- Xác minh phiên này: `pytest -q` 21 passed, `npm run build` thành công, `git diff --check` sạch. Tích hợp cũ đi từ ZIP Windows giả lập qua đóng gói Kaggle, giải nén, tạo split và kiểm toán; không sửa dữ liệu/checkpoint hiện có.
- Nguồn: TACO upstream có segmentation/COCO và khai báo MIT cho repository; license của ảnh và khả năng tái sử dụng từng nguồn vẫn cần rà soát. SWiM3 license vẫn chưa xác minh trong checkout.
- Ngày mai: xác minh license SWiM3, tạo Kaggle Dataset từ ZIP, chạy lại `kaggle_prepare.py --archive swim3_train.zip` với username/slug thật, kiểm tra metadata, rồi chạy YOLO26s và n trên split sạch; chọn bằng validation, đánh giá SWiM3 test đúng một lần. Chỉ xem xét deploy nhận diện thật sau khi có VN-Field test. Chưa benchmark latency CPU ở 640 px cho **s**.
- Rủi ro còn lại: dHash không bảo đảm phát hiện mọi ảnh tương tự về ngữ nghĩa; nhãn nhóm giấy có ví dụ vật liệu phủ/wood, chưa có tập kiểm tra ngoài miền được gắn box từ Việt Nam, latency CPU của s chưa đo, nội dung hướng dẫn mới ở mức chung. Có CSS mobile nhưng chưa kiểm tra trực quan ở viewport điện thoại thật.
- **Chưa sẵn sàng deploy nhận diện thật tại Việt Nam:** cần nghiệm thu trên `VN-Field-test` độc lập; [giao thức và script đo tại ngưỡng triển khai](vietnam-data-strategy.md). SWiM3-test không thay thế được bước này.
- Đã thêm đường **Domain Adaptation** bằng `train.py --init-checkpoint`: nạp checkpoint ba lớp từ SWiM3 để bắt đầu run mới trên VN-Field, tách khỏi `--resume-checkpoint`. Đã thử CPU smoke một epoch trên mini SWiM3 để xác nhận đường nạp/training hoạt động; **chưa có dữ liệu VN nên chưa chạy adaptation thực**.

## Beta01 — 14/11/2026

- Scan Studio giữ trạng thái riêng cho từng detection, cho phép sửa/bỏ từng khung và khoanh vùng để gọi YOLO lần hai; kết quả crop được quy về tọa độ ảnh gốc. Chế độ demo không giả vờ chạy lượt YOLO thứ hai.
- Recommendation Wizard dùng catalog 166 vật thể, thu thập điều kiện theo từng vật thể và trả lời có nguồn/cảnh báo KB.
- Chatbot gọi Groq `openai/gpt-oss-20b` cho mọi câu hỏi khi `GROQ_API_KEY` được cấu hình. KB chỉ bổ sung ngữ cảnh; lỗi provider hoặc thiếu key dùng KB dự phòng. API key chỉ ở `.env`, không được commit.
- Tin môi trường hiển thị dải bài mới và bài đã lưu riêng. Dữ liệu model, dataset, checkpoint, `node_modules`, `.venv` và output huấn luyện vẫn là tài nguyên local bị Git ignore.
- Tích hợp không retrain YOLO, không sửa 166 bản ghi recommendation KB, chưa deploy.
- Báo cáo về API contracts và kiểm thử nằm ở [CV_KB_INTEGRATION_REPORT.md](CV_KB_INTEGRATION_REPORT.md); chatbot có [hướng dẫn cấu hình](CHATBOT_GROQ.md).
- Kiểm tra Beta01: backend 346 passed (1 cảnh báo Starlette deprecation), frontend 14 passed, TypeScript/Vite build thành công.
