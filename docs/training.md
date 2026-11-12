# Training và Kaggle GPU

**Phạm vi kết luận:** run hiện tại chỉ đánh giá trong miền SWiM3. Kế hoạch tìm và xây tập ảnh Việt Nam được ghi ở [vietnam-data-strategy.md](vietnam-data-strategy.md); hiện chưa có tập VN có box được xác minh trong repo.

## Trước khi chạy

1. Đọc [kiểm toán dữ liệu](data-audit.md). `datasets/swim3_clean/data.yaml` là nguồn train, validation và test; file gốc có leakage.
2. Kiểm tra quyền sử dụng SWiM3. README của dataset nói dùng nghiên cứu/giáo dục nhưng trỏ tới LICENSE chưa thấy trong bản repo hiện tại. Không công bố hay thương mại hóa ảnh trước khi xác minh giấy phép gốc.
3. Cài Kaggle CLI và xác thực tài khoản của bạn vào ngày mai. Tạo một Kaggle Dataset chứa đúng **một** archive `swim3_train.zip`; không đưa dữ liệu vào kernel code bundle. `--archive` dưới đây kiểm tra cặp ảnh/nhãn và lưu SHA-256; kernel so checksum sau khi nhận archive để tránh train nhầm bản.

## GPU tại Kaggle

Notebook thử nghiệm local tại `ml/notebooks/wastewise_training.ipynb`; chạy cell train chỉ khi đã chọn GPU/dữ liệu. Workflow Kaggle chính dùng script bundle dưới đây để tránh phụ thuộc notebook state.

Ví dụ sau **chỉ chuẩn bị bundle**; lệnh `push` là hành động ngày mai sau khi bạn kiểm tra metadata và cấp quyền Kaggle.

```powershell
.\.venv\Scripts\python.exe ml\scripts\kaggle_prepare.py --username TEN_USER --dataset-source TEN_USER/swim3 --model yolo26s.pt --epochs 80 --batch 8 --archive swim3_train.zip
Get-Content outputs\kaggle_kernel\kernel-metadata.json
Get-Content outputs\kaggle_kernel\archive_preflight.json
kaggle kernels push -p outputs\kaggle_kernel
kaggle kernels status TEN_USER/wastewise-yolo26s
kaggle kernels output TEN_USER/wastewise-yolo26s -p outputs\kaggle_yolo26s
```

Bundle chứa script độc lập: kiểm tra checksum ZIP, kiểm tra GPU, giải nén an toàn cả đường dẫn ZIP kiểu Windows, tạo split sạch ở `/kaggle/working`, kiểm toán ảnh/nhãn/overlap và **dừng nếu audit lỗi**, train, đánh giá **validation** và xuất `best.pt`, `validation.json`, `clean_audit.json`, `model_metadata.json`. Tạo bundle riêng với `--model yolo26n.pt` để chạy đối chứng; dùng tên kernel riêng để không ghi đè run s. Kernel bật GPU và internet để lấy dependency/checkpoint pretrained; nếu Kaggle cấm internet, cần gắn checkpoint như model input và sửa đường dẫn model trong bundle trước khi submit.

Nếu hết bộ nhớ GPU, giảm `--batch` từ 8 xuống 4. Chạy 80 epoch, early stopping patience 15, ảnh 640, seed 42. Theo dõi mAP50:95, mAP50, precision, recall từng lớp và confusion matrix/PR curves trong thư mục run. Chọn cấu hình bằng validation, sau đó đánh giá test một lần:

```powershell
.\.venv\Scripts\python.exe ml\scripts\evaluate.py --model DUONG_DAN_BEST_PT --data datasets\swim3_clean\data.yaml --split test --out outputs\final_test.json
```

Để tiếp tục run dở **trong cùng môi trường và cùng đường dẫn dữ liệu**: dùng `--resume-checkpoint DUONG_DAN_LAST_PT` với `train.py`. Run mới phải có `--name` chưa tồn tại để checkpoint luôn nằm đúng thư mục dự kiến. Mini CPU dùng `--smoke --device cpu`; run chính bắt buộc có train/val/test riêng và đúng thứ tự nhãn. `best.pt` của vòng CPU mini không phải model triển khai.

## Sau SWiM3: kiểm tra tổng quát hóa và thích nghi miền Việt Nam

Luồng nghiên cứu là **SWiM3 → Cross-domain Test → Domain Adaptation → VN holdout mới → WasteWise VN**. Cross-domain Test dùng ảnh ngoài SWiM3, ưu tiên ảnh rác tại Việt Nam, để biết checkpoint ban đầu suy giảm ở bối cảnh nào. Sau khi thu và gắn box thêm ảnh Việt Nam, dùng `--init-checkpoint SWIM3_BEST_PT` để bắt đầu **run fine-tune mới**, không dùng `--resume-checkpoint` của run SWiM3. Các phép augmentation chỉ áp dụng ở train; chọn cấu hình bằng VN validation và giữ VN test mới độc lập. [Giao thức đầy đủ](vietnam-data-strategy.md).

## Thí nghiệm và tiêu chí chọn

| Run | Thay đổi | Mục đích |
|---|---|---|
| A | YOLO26n, 640, seed 42 | Mốc gọn/CPU |
| B | YOLO26s, cùng config | Ứng viên chính |
| C | YOLO26s, augmentation ánh sáng nhẹ hơn hoặc mạnh hơn | Kiểm tra domain shift Việt Nam |

Chỉ thay **một** yếu tố mỗi run, giữ split sạch và seed. Chọn theo mAP50:95 validation, recall lớp yếu, lỗi ảnh nhỏ/chồng lấp và latency CPU. Không dùng test hoặc ảnh báo chí chưa gắn box để tune. Nếu sau này có ảnh Việt Nam được cấp quyền, gắn nhãn thủ công và giữ **tập VN ngoài miền** riêng; tránh dùng ảnh không nhãn để tuyên bố độ chính xác.

Nguồn kỹ thuật: [Ultralytics train](https://docs.ultralytics.com/modes/train), [Kaggle kernel metadata](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md), [Kaggle CLI kernels](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md).
