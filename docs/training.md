# Training và Kaggle GPU

## Trạng thái hiện tại: detector đa lớp v3

`datasets/multiclass_v3/` đã được build từ TACO ODbL và KNR-PET-7 (ảnh chai PET chụp tại Việt Nam), audit nhãn và preflight CPU. Không có GPU training nào chạy. Dataset `multiclass_v2` vẫn được giữ nguyên để tái lập kết quả cũ. Để chuẩn bị phiên Vast.ai, transfer `datasets/multiclass_v3/` và làm theo [Vast.ai runbook](vast-runbook.md); `scripts/vast_preflight.sh` và `scripts/vast_train.sh` hiện mặc định trỏ đến v3. Dataset chưa được push lên GitHub vì thư mục `datasets/` được git-ignored.

## Dataset đa lớp v2 (bản cũ, giữ để tái lập)

`ml/config/dataset_sources.json` là source inventory và bảng mapping TACO dùng để build `multiclass_v2`. TACO là ảnh litter ngoài trời; chỉ ảnh ghi rõ ODbL được giữ trong bản train cũ. SWiM3 tiếp tục là baseline độc lập; không thay đổi weights hay labels của baseline.

Sau khi kiểm tra license, tải nguồn thủ công và chuẩn bị COCO JSON cùng ảnh, viết config JSON cho `build_multisource.py`: classes theo thứ tự taxonomy, source paths, `license_reviewed: true`, `mapping_reviewed: true`, `fully_annotated`, và mapping từng source class với quyết định `map`/`exclude`/`needs_review`/`unmappable`. Script bỏ ảnh có mapping chưa rõ để tránh hidden target objects làm nhãn âm; dữ liệu chưa xác định thì không thể train bằng cách coi là background. Split group theo `scene_id` nếu có; nếu không, ảnh có SHA-256 riêng. Audit/provenance được ghi vào output và output có sẵn sẽ làm lệnh fail.

```powershell
.\.venv\Scripts\python.exe ml\scripts\build_multisource.py --config reviewed_sources.json --out datasets\multiclass_v2
.\.venv\Scripts\python.exe ml\scripts\train_multiclass.py --data datasets\multiclass_v2\data.yaml --name waste_v2_preflight --device 0 --preflight-only
```

Xem `audit_report.json` và spot-check labels/visualizations thủ công trước khi cho phép GPU run. `train_multiclass.py` kiểm tra các split/classes/labels/taxonomy/GPU/disk, dùng pretrained `yolo26s.pt` hoặc `yolo26n.pt` cho **run mới**, lưu `run_config.json`, và tạo manifest cạnh weights. Nó không có chế độ resume/transferring optimizer từ baseline. `evaluate.py` báo per-class metric theo tên từ data YAML. Chỉ bật category trong detector class map sau khi có dữ liệu annotation hợp lệ, checkpoint đã train và validation; lớp trong taxonomy đơn thuần không phải bằng chứng nhận diện.

**Lịch sử:** các kết luận và lệnh Kaggle/SWiM3 bên dưới là workflow baseline/legacy. Dataset Vietnam PET mới và số liệu audit nằm trong [vietnam-dataset-expansion.md](vietnam-dataset-expansion.md); chúng không chứng minh năng lực phát hiện rác sinh hoạt ngoài các loại có box.

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
