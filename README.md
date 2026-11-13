# SOICTERRA

**SOICTERRA** là dự án của sinh viên SoICT, Đại học Bách khoa Hà Nội, ứng dụng thị giác máy tính vào phân loại rác trong bối cảnh đô thị Việt Nam. Người dùng có thể tải ảnh lên Scan Studio, xem kết quả nhận diện, hiệu chỉnh nhãn, tra cứu hướng dẫn theo vật liệu và hỏi trợ lý kiến thức.

## Tính năng

- **Scan Studio:** tải ảnh JPEG, PNG hoặc WebP để gửi tới FastAPI; xem bounding box, lớp, confidence và hướng dẫn theo kết quả.
- **Ảnh mẫu:** thử luồng demo ngay sau khi cài đặt, không cần checkpoint. Các khung trên ảnh mẫu được đánh dấu là minh họa.
- **Thư viện phân loại:** tìm kiếm vật liệu, xem hướng dẫn nên làm, cần tránh và lưu ý.
- **Hiệu chỉnh kết quả:** đổi nhãn, bỏ phát hiện hoặc thêm nhóm vật liệu để tra cứu.
- **Trợ lý SOICTERRA:** tra cứu FAQ và dữ liệu hướng dẫn được biên soạn cùng dự án.
- **Lịch sử riêng trên trình duyệt:** lưu thời gian và nhãn quét trong `localStorage`, không lưu ảnh vào lịch sử.
- **Song ngữ Việt–Anh:** đổi ngôn ngữ giao diện từ nút VI/EN trên thanh điều hướng. Nội dung hướng dẫn lấy từ `backend/knowledge.json` hiện được biên soạn bằng tiếng Việt.

## Công nghệ

| Phần | Công nghệ |
| --- | --- |
| Giao diện | React, TypeScript, Vite |
| API | Python, FastAPI, Uvicorn |
| Nhận diện | Ultralytics YOLO; có chế độ demo và chế độ checkpoint thật |
| Tri thức phân loại | JSON trong `backend/knowledge.json` và taxonomy trong `backend/taxonomy.json` |

## Yêu cầu

- Git
- Python **3.11** (khuyến nghị)
- Node.js **20.19+** và npm
- Trình duyệt hiện đại

Chế độ mặc định là `demo`, không cần tải model hoặc dữ liệu huấn luyện. Cài Python requirements có thể tải các thư viện nhận diện khá lớn; hãy chờ pip cài xong trước khi chạy API.

## Cài đặt và chạy

API và giao diện chạy như hai tiến trình riêng. Mở hai terminal tại thư mục dự án sau khi clone.

### Windows PowerShell

```powershell
git clone https://github.com/ducnguyenhuu26/Project1.git
cd Project1

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env

cd frontend
npm ci
cd ..
```

**Terminal 1 — FastAPI** (chạy từ thư mục gốc `Project1`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — giao diện** (chạy từ thư mục gốc `Project1`):

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### macOS / Linux

```bash
git clone https://github.com/ducnguyenhuu26/Project1.git
cd Project1

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env

cd frontend
npm ci
cd ..
```

**Terminal 1 — FastAPI** (từ thư mục gốc `Project1`):

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — giao diện** (từ thư mục gốc `Project1`):

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Mở giao diện tại [http://127.0.0.1:5173](http://127.0.0.1:5173). Tài liệu API nằm ở [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Vite tự chuyển tiếp các request `/api` tới FastAPI ở cổng `8000`.

## Chạy thử

1. Đảm bảo cả API và giao diện đang chạy.
2. Trên trang SOICTERRA, chọn **Chạy ảnh mẫu** hoặc cuộn tới Scan Studio và chạy ảnh mẫu.
3. API trả về các khung minh họa cho ảnh mẫu. Ảnh khác trong chế độ demo vẫn đi qua API nhưng không được gán dự đoán giả.
4. Tải ảnh của bạn lên để thử luồng giao diện. Muốn nhận dự đoán từ model thật, cần cài checkpoint theo mục bên dưới.

## Dùng checkpoint YOLO thật (tùy chọn)

Checkpoint không được lưu trong Git. Tạo thư mục `weights`, đặt checkpoint bạn được phép sử dụng vào đó, ví dụ `weights/best.pt`, rồi sửa file `.env`:

```dotenv
DETECTOR_MODE=real
MODEL_PATH=weights/best.pt
INFERENCE_DEVICE=cpu
CONFIDENCE=0.25
```

Khởi động lại API sau khi đổi cấu hình. Nếu checkpoint cần manifest, đặt `model_manifest.json` cùng thư mục và đảm bảo `taxonomy_version` cùng `class_map` khớp với `backend/taxonomy.json`. Baseline legacy hỗ trợ các lớp Plastic, Paper và Metal. API báo trạng thái model tại `/api/v1/health`; khi thiếu hoặc sai checkpoint, phần nhận diện trả lỗi thay vì âm thầm chạy demo.

Để dùng GPU CUDA, cài PyTorch phù hợp với máy theo hướng dẫn chính thức của PyTorch, rồi đặt `INFERENCE_DEVICE=0`. Cấu hình GPU phụ thuộc phiên bản CUDA và driver trên máy.

## Kiểm tra và build

Chạy từ thư mục gốc:

```powershell
# Windows
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

```bash
# macOS / Linux
.venv/bin/python -m pytest -q
cd frontend
npm run build
```

## Cấu trúc repository

```text
backend/       FastAPI, detector adapter, taxonomy và knowledge base
frontend/      React/TypeScript UI, ảnh và tài nguyên giao diện
ml/            Cấu hình và script chuẩn bị dữ liệu, train, đánh giá
tests/         Python tests cho backend và pipeline
docs/          Tài liệu kiến trúc, dữ liệu, hướng dẫn train và frontend
scripts/       Tiện ích cài đặt/kiểm tra model
```

Một số điểm để sửa giao diện và nội dung:

- Copy tiếng Việt/Anh và thông tin đội ngũ: `frontend/src/content/siteContent.ts`
- Link liên hệ footer: `frontend/src/content/contactLinks.ts`
- Nhãn/copy giao diện dùng chung: `frontend/src/components/` và `frontend/src/lib/language.tsx`
- Màu sắc và bố cục responsive: `frontend/src/style.css`
- Hướng dẫn và FAQ: `backend/knowledge.json`
- Taxonomy và lớp mô hình hỗ trợ: `backend/taxonomy.json`

## Khắc phục sự cố

- **Cổng 8000 đã được sử dụng:** thường là FastAPI đã chạy trong terminal khác. Dùng server đó nếu truy cập được `/docs`; không cần khởi động thêm một bản. Nếu đó là tiến trình không liên quan, dừng tiến trình đang chiếm cổng rồi chạy lại API.
- **Frontend mở được nhưng không tải thư viện/quét ảnh lỗi:** kiểm tra terminal FastAPI, sau đó mở `/docs` để xác nhận API đang chạy ở cổng `8000`.
- **`py -3.11` không được nhận diện trên Windows:** cài Python 3.11 và bật Python Launcher, hoặc dùng `python` nếu máy đã trỏ đúng phiên bản.
- **`npm ci` lỗi:** kiểm tra Node.js/npm và chạy lệnh trong thư mục `frontend`.
- **Chọn chế độ `real` nhưng thiếu model:** đặt checkpoint đúng `MODEL_PATH` rồi khởi động lại API; file model không đi kèm repository.

## Tài liệu dự án

- [Kiến trúc tổng quan](docs/architecture-overview.md)
- [Chiến lược dữ liệu và huấn luyện](docs/training.md)
- [Kiểm toán dữ liệu](docs/data-audit.md)
- [Trạng thái triển khai](docs/implementation-status.md)
- [Hướng dẫn frontend SOICTERRA](docs/soicterra-frontend-v3.md)
