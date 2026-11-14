# WasteWise VN: bài toán và kiến trúc đã chốt

Đọc [bản kiến trúc dễ theo dõi, dùng ký hiệu thay cho giá trị cụ thể](architecture-overview.md) trước.

Đặc tả từng tensor, từng layer 0–23, attention, head và loss của YOLO26: [architecture-math.md](architecture-math.md). Đồ thị toán học của **toàn hệ thống WasteWise VN**, phần nào học sâu và khả năng giải thích: [system-architecture-math.md](system-architecture-math.md).

## 1. Bài toán

Cho ảnh RGB (I\in[0,1]^{H\times W\times3}), dự đoán tập vật thể
\(\mathcal D(I)=\{(b_j,c_j,s_j)\}_{j=1}^{N}\), trong đó
\(b_j=(x_{1j},y_{1j},x_{2j},y_{2j})\) là box trên **ảnh gốc**,
\(c_j\in\{0,1,2\}=\{\text{Plastic, Paper, Metal}\}\), và \(s_j\) là điểm tin cậy mô hình (không tự coi là xác suất đã hiệu chuẩn). Bài toán là **object detection nhiều vật thể**, không phải phân loại toàn ảnh. Từ box, ứng dụng gom nhóm và tra cứu hướng dẫn có điều kiện. Không suy diễn khả năng tái chế, hóa chất hoặc tính an toàn khi đốt từ một ảnh RGB.

**Quyết định cuối cho lần train chính:** YOLO26s pretrained COCO → fine-tune 3 lớp trên SWiM3 split sạch; YOLO26n cùng cấu hình làm baseline tốc độ/CPU. Triển khai qua interface `Detector`; chỉ nạp checkpoint ba lớp khi chuyển sang chế độ real. Ở CPU, chọn `s` nếu latency chấp nhận được; nếu không chọn `n` sau khi so mAP và recall. Vòng mini CPU chứng minh pipeline chạy, chưa đủ dữ liệu để chọn chất lượng.

**Không chèn attention/CNN block mới vào run chính.** YOLO26 đã có `C2PSA` attention ở cuối backbone và `C3k2` có nhánh attention ở tầng neck sâu. Một block thêm sẽ khởi tạo ngẫu nhiên và tạo biến thí nghiệm mới; chưa có validation chứng minh lợi ích. Nếu nghiên cứu tiếp, ứng viên nhẹ là ECA theo kênh sau P4 trong [đặc tả toàn hệ thống](system-architecture-math.md). Cần triển khai và chạy ablation riêng trước khi xem là cải tiến; không coi ECA là thành phần đã train hoặc có trong code hiện tại.

## 2. Hai mạng sâu được train

YOLO26n và YOLO26s có **cùng đồ thị module** (backbone → neck FPN/PAN → head ba mức), khác hệ số width. YAML trong checkpoint local ghi scale `n=[0.5,0.25,1024]`, `s=[0.5,0.5,1024]`: hệ số depth đều 0,5; số kênh ở `s` gần gấp đôi `n` khi chưa bị giới hạn max-channel. Bản local: `n` khoảng **2,57 triệu** tham số từ pretrained COCO, `s` khoảng **10,01 triệu** tham số ở YAML dựng mới; số cuối của checkpoint 3 lớp thay đổi theo head. `yolo26s.pt` chưa có local, nên chưa chạy mini train `s`.

| Tầng | YOLO26n và YOLO26s | Vai trò |
|---|---|---|
| Stem | hai `Conv(3×3,stride=2)` | từ ảnh tới đặc trưng stride 4 |
| Backbone P3/P4/P5 | `Conv` xuống mẫu + `C3k2` | đặc trưng stride 8/16/32 |
| Backbone cuối | `SPPF` residual + `C2PSA` | ngữ cảnh đa tỉ lệ và attention |
| Neck | top-down upsample/concat/`C3k2`, rồi bottom-up conv/concat/`C3k2` | trộn định vị của P3 với ngữ nghĩa P5 |
| Head | `Detect(P3,P4,P5)` | box và 3 điểm lớp mỗi vị trí |

### 2.1. Phép tích chập và các khối CNN

Với tensor \(X\in\mathbb R^{H\times W\times C_{in}}\), một lớp conv tiêu chuẩn tại vị trí \((u,v)\) và kênh \(o\) có dạng

\[
Z_{u,v,o}=\sum_{i=1}^{k}\sum_{j=1}^{k}\sum_{c=1}^{C_{in}}K_{i,j,c,o}X_{u+i,v+j,c}+b_o,
\qquad Y=\operatorname{SiLU}(\operatorname{BN}(Z)).
\]

`stride=2` giảm kích thước không gian để tạo pyramid. `DWConv` trong nhánh phân lớp chạy riêng từng kênh (chi phí khoảng \(k^2C\)); conv điểm `1×1` sau đó trộn kênh (khoảng \(CC'\)). Điều này rẻ hơn conv \(k×k\) toàn phần (khoảng \(k^2CC'\)).

`C3k2` là biến thể CSP/C2f. Đầu vào được chiếu `1×1` rồi chia làm hai nhánh \((U_0,U_1)=\operatorname{split}(\operatorname{Conv}_{1×1}(X))\). Nhánh học sâu tạo tuần tự
\(U_{t+1}=B_t(U_t)\), với \(B_t\) là Bottleneck/C3k (hoặc nhánh có PSABlock khi YAML đặt `attn=True`). Đầu ra là
\[
Y=\operatorname{Conv}_{1×1}\bigl([U_0,U_1,U_2,\dots,U_{r+1}]\bigr).
\]
Việc nối mọi tensor trung gian tái sử dụng đặc trưng nông và sâu. Trong YOLO26, backbone P3/P4/P5 và các nút hợp nhất neck dùng `C3k2`; không thay implementation Ultralytics.

`SPPF` tại đáy backbone dùng max-pool `5×5` lặp ba lần. Với \(V=\operatorname{Conv}_{1×1}(X)\):
\(M_0=V, M_t=\operatorname{MaxPool}_{5×5}(M_{t-1})\),
\(S=\operatorname{Conv}_{1×1}([M_0,M_1,M_2,M_3])+X\).
Nhánh cộng tắt (residual) của YOLO26 giúp giữ thông tin đầu vào.

### 2.2. Attention C2PSA hiện có

Đặt \((A,B)=\operatorname{split}(\operatorname{Conv}_{1×1}(S))\). Ở nhánh \(B\), mỗi `PSABlock` biến tensor thành token không gian và tạo
\[
Q=BW_Q,\quad K=BW_K,\quad V=BW_V,\qquad
T=\operatorname{softmax}\!\left(\frac{QK^\top}{\sqrt{d}}\right)V.
\]
Các head attention được nối lại, chiếu về số kênh cũ, rồi dùng residual và mạng điểm theo kênh:
\[
B'=B+\operatorname{Proj}(T),\qquad
B''=B'+W_2\,\phi(W_1B'),\qquad
Y=\operatorname{Conv}_{1×1}([A,B'']).
\]
Như vậy một nửa kênh đi thẳng, một nửa học phụ thuộc xa giữa các vùng ảnh. Đây là attention thật trong kiến trúc gốc, không phải tên gắn thêm. Cấu hình local đặt `C2PSA` sau `SPPF` và cờ attention ở `C3k2` sâu cuối neck.

### 2.3. Neck FPN/PAN và ba mức phát hiện

Với đặc trưng backbone \(C_3,C_4,C_5\), nhánh top-down xấp xỉ
\(F_5=C_5, F_4=G_4([C_4,\operatorname{Up}(F_5)]), F_3=G_3([C_3,\operatorname{Up}(F_4)])\).
Nhánh bottom-up tạo
\(P_3=F_3, P_4=H_4([F_4,\operatorname{Down}(P_3)]), P_5=H_5([F_5,\operatorname{Down}(P_4)])\).
Các \(G,H\) là `C3k2`. Ảnh 640×640 cho kích thước xấp xỉ \(P_3:80×80\), \(P_4:40×40\), \(P_5:20×20\). Vật nhỏ như nắp chai/ống hút chủ yếu cần P3; vật lớn dùng P4/P5.

### 2.4. Head YOLO26 và hàm mất mát

Ở mỗi mức \(\ell\in\{3,4,5\}\), nhánh box xuất bốn số \(t_b\in\mathbb R^4\), nhánh lớp xuất \(t_c\in\mathbb R^3\); \(s_c=\sigma(t_c)\). `reg_max=1` nên không có DFL 16-bin của YOLOv8/11. Head **anchor-free** dự đoán từ điểm lưới, không gắn bộ anchor kích thước cố định. YAML YOLO26 có nhánh huấn luyện one-to-many và one-to-one; bản local có `one2one_cv2/cv3`. Inference mặc định của API giữ đường `predict` Ultralytics và hậu xử lý của thư viện; chế độ NMS-free là lựa chọn riêng cần benchmark/kiểm tra export, chưa bật trong ứng dụng.

Với ground-truth \(b_i^*,c_i^*\), training gán mẫu dương cho các điểm phù hợp; tối ưu dạng tổng quát
\[
\mathcal L=\lambda_b\mathcal L_{\rm box}(b,b^*)+\lambda_c\mathcal L_{\rm cls}(s,c^*)+\lambda_1\mathcal L_{\rm L1}(b,b^*),
\]
trên các nhánh được thư viện giám sát. Log mini train phiên bản 8.4.210 ghi `box_loss`, `cls_loss`, `l1_loss`. Không tự thay loss, assignment hay backbone; muốn diễn giải chính xác từng hệ số theo phiên bản phải dựa vào mã nguồn Ultralytics tương ứng. Pretrained COCO 80 lớp cấp tham số backbone/neck và các phần head tương thích; head ba lớp được điều chỉnh trong fine-tune.

### 2.5. Từ output model đến box ảnh gốc

Tiền xử lý letterbox giữ tỉ lệ: \(r=\min(640/W,640/H)\), \(W'=rW,H'=rH\), padding \((p_x,p_y)\). Nếu box dự đoán trên ảnh letterbox là \((x'_1,y'_1,x'_2,y'_2)\), khôi phục
\(x_i=\operatorname{clip}((x'_i-p_x)/r,0,W)\),
\(y_i=\operatorname{clip}((y'_i-p_y)/r,0,H)\).
Ultralytics `result.boxes.xyxy` đã trả box theo ảnh gốc; adapter chỉ lấy ra số thực. SVG frontend dùng `viewBox="0 0 W H"` và cùng phép `contain` như ảnh, nên khung co giãn đúng khi responsive. Tổng hợp lớp \(k\): \(\hat n_k=\sum_j\mathbf1[c_j=k]\), chỉ là số khung ước tính.

## 3. Phần mềm và quy tắc an toàn

`FastAPI → Detector (Demo/Real) → Detection/summary → knowledge-base advice → React`. Detector nạp một lần khi app khởi động. `DemoDetector` chỉ tạo box cho ảnh minh họa; ảnh bất kỳ trả rỗng với cảnh báo. `RealYOLODetector` chỉ nhận checkpoint có đúng `Plastic, Paper, Metal`; thiếu checkpoint trả 503. `POST /api/v1/scans/region` chạy detector lần nữa trên vùng người dùng khoanh và ánh xạ box về ảnh gốc. Knowledge base JSON cung cấp `do/avoid/caution/vn_tip`; các mục ngoài ba lớp detector là **tra cứu thủ công**. Chatbot gọi Groq khi có key, dùng KB làm ngữ cảnh nếu có và cho LLM trả lời kiến thức chung an toàn nếu không có mục khớp. Lịch sử quét chỉ lưu thời gian và tên nhóm trong localStorage; ảnh gốc không được lưu.

Đây là ứng dụng hỗ trợ, không phải bộ phân loại pháp lý hay quyết định tái chế. Cần kiểm tra quy định thu gom địa phương, đặc biệt với vật liệu hỗn hợp, bẩn, sắc hoặc có áp suất. Nội dung tham khảo chung từ [cổng Bộ TN&MT](https://www.monre.gov.vn/) và [tài liệu quản lý chất thải rắn sinh hoạt](https://cspl-tnmt.monre.gov.vn/upload/81732/fck/files/59728d487ba47e4e0040c49e48ca5415.pdf); nên bổ sung nguồn hướng dẫn địa phương cụ thể trước khi mở rộng.

Nguồn kiến trúc: [Ultralytics YOLO Architecture](https://docs.ultralytics.com/guides/yolo-architecture), [Ultralytics YOLO26 Training](https://docs.ultralytics.com/modes/train), [Ultralytics Export](https://docs.ultralytics.com/modes/export). Ultralytics dùng [AGPL-3.0 hoặc Enterprise](https://docs.ultralytics.com/help/contributing/); cần rà soát trước khi thương mại hóa.
