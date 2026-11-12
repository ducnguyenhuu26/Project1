# Kiểm toán SWiM3 local (12/11/2026)

`audit_dataset.py` đã quét 6.363 ảnh gốc: train 4.992, valid 943, test 428. Đếm nhãn đầy đủ 3 lớp nhưng phát hiện **704 họ ảnh** (`_aug*`/Roboflow) đi qua nhiều split và **8 hash ảnh** trùng byte qua split. Bộ gốc có 348 dòng bị cờ theo điều kiện biên chính xác tuyệt đối; khi cho phép sai số ghi số 1e-6, còn **62 dòng** vượt biên rõ hơn. README dataset nói 6.429 ảnh, khác 6.363 ảnh thực có trong split local.

`prepare_clean_split.py` tạo bản dẫn xuất với seed 42 bằng cách nhóm ảnh cùng stem gốc và cùng hash trước khi chia 80/10/10 theo **nhóm**. Ảnh validation/test chỉ giữ một đại diện mỗi nhóm; ảnh train giữ các biến thể augmentation. Script không sửa hoặc xóa ảnh/nhãn gốc; 243 box trong các ảnh được giữ đã được clip vào `[0,1]` và ghi trong manifest. Bản sạch có 5.127 train, 372 validation, 384 test; 480 biến thể augmentation dư ở validation/test được loại khỏi bản dẫn xuất. Kiểm toán lại: **0 lỗi, 0 family overlap, 0 exact hash overlap**.

Vẫn có nguy cơ ảnh gần giống nhưng khác tên/khác pixel chưa bị bộ kiểm tra family/hash bắt được. Trước báo cáo kết quả cuối, nên kiểm tra perceptual hash trên ảnh gần giống và một mẫu nhãn trực quan, nhất là các nhóm “ly giấy”, “hộp sữa”, “wood” có thể không tương ứng vật liệu thuần.
