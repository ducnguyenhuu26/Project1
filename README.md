# WasteWise VN

**WasteWise VN** là dự án Project 1 xây dựng giao diện trực quan để hỗ trợ phân loại rác thải sinh hoạt. Người dùng chỉ cần chụp hoặc tải một bức ảnh: ứng dụng khoanh vùng những vật dụng nhận diện được, gợi ý nhóm vật liệu và hiển thị hướng dẫn **nên làm, tránh làm, lưu ý khi thu gom tại Việt Nam**. Một ảnh có thể chứa nhiều món rác, chẳng hạn chai và nắp nhựa, ống hút, giấy vụn, thùng carton, lon nước hoặc nắp kim loại.

Ngoài kết quả trên ảnh, người dùng có thể sửa nhóm được gợi ý, tra cứu cách xử lý pin, thủy tinh, rác hữu cơ và hỏi trợ lý tra cứu bằng tiếng Việt. Những mục này được ghi rõ là **tra cứu thủ công** khi mô hình chưa nhận diện được; ứng dụng không coi một bức ảnh là đủ để kết luận chắc chắn vật có tái chế được hay không.

Phần nhận diện dùng **YOLO26s** theo quy trình fine-tune từ checkpoint pretrained trên ảnh SWiM3 có gắn khung, nhằm dự đoán vị trí và nhóm vật liệu. Phạm vi nhãn của detector là nhựa, giấy/bìa và kim loại; chất lượng trên ảnh thực tế ở Việt Nam sẽ được kiểm tra riêng trước khi sử dụng rộng rãi. [Cách train và đánh giá](docs/training.md).

## Cài và chạy từ repo mới tải về

Cần **Python 3.11+**, **Node.js 20.19+**, npm và Git. Dữ liệu SWiM3 và checkpoint không nằm trong Git; **chế độ minh họa chạy được ngay sau khi cài**.

### Windows PowerShell

```powershell
git clone https://github.com/ducnguyenhuu26/Project1.git
cd Project1
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend
npm ci
cd ..
```

Mở **hai cửa sổ PowerShell** tại thư mục `Project1`:

```powershell
# Cửa sổ API
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Cửa sổ giao diện
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### macOS / Linux

```bash
git clone https://github.com/ducnguyenhuu26/Project1.git
cd Project1
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cd frontend && npm ci && cd ..
```

Chạy API bằng `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`; ở terminal khác, chạy `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`.

Mở [giao diện](http://127.0.0.1:5173) và [tài liệu API](http://127.0.0.1:8000/docs). Chọn **ảnh mẫu** để xem luồng demo. Khung trên ảnh mẫu được ghi rõ là minh họa; ảnh khác trong demo không được gán kết quả AI giả.

## Dùng checkpoint thật

Sau khi có `best.pt` đã fine-tune đúng các lớp `Plastic`, `Paper`, `Metal`, sửa `.env`:

```dotenv
DETECTOR_MODE=real
MODEL_PATH=weights/best.pt
INFERENCE_DEVICE=cpu
```

Đặt checkpoint vào đường dẫn đã khai báo rồi **khởi động lại API**. Nếu thiếu checkpoint, API trả lỗi rõ ràng; checkpoint COCO chưa fine-tune không được nhận làm detector rác. Chỉ triển khai nhận diện cho người dùng thật sau khi kiểm tra trên ảnh Việt Nam độc lập.
Đặt `INFERENCE_DEVICE=0` để suy luận trên GPU CUDA đầu tiên.

## Chuẩn bị dữ liệu và train

Để train, đặt thư mục SWiM3 đã giải nén tại `datasets/swim3/Splitted_Dataset` theo cấu trúc `train/valid/test`, mỗi split có `images` và `labels`. Bộ dữ liệu có thể lấy từ [nguồn SWiM3](https://github.com/Burhan-Ahmed/SWiM3-Dataset); kiểm tra quyền sử dụng trước khi tải hoặc chia sẻ. Không train trực tiếp trên split gốc vì kiểm toán phát hiện ảnh trùng qua các split.

```powershell
.\.venv\Scripts\python.exe ml\scripts\prepare_clean_split.py
.\.venv\Scripts\python.exe ml\scripts\audit_dataset.py --root datasets\swim3_clean --hash-images --perceptual --out outputs\clean_audit.json
.\.venv\Scripts\python.exe ml\scripts\train.py --data datasets\swim3_clean\data.yaml --model yolo26s.pt --device 0 --name waste_yolo26s
.\.venv\Scripts\python.exe ml\scripts\evaluate.py --model runs\train\waste_yolo26s\weights\best.pt --data datasets\swim3_clean\data.yaml --split val
```

Lệnh train trên yêu cầu GPU CUDA. Với Kaggle, cách chuẩn bị bundle, submit và tải checkpoint ở [docs/training.md](docs/training.md). Bước Cross-domain Test và Domain Adaptation với ảnh Việt Nam ở [docs/vietnam-data-strategy.md](docs/vietnam-data-strategy.md).

## Kiểm tra cài đặt

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

Tài liệu thêm: [kiến trúc](docs/architecture-overview.md) · [kiểm toán dữ liệu](docs/data-audit.md) · [trạng thái triển khai](docs/implementation-status.md).
