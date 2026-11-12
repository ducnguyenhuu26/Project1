# Kiến trúc WasteWise VN — bản dễ theo dõi

Tài liệu này cố ý dùng ký hiệu thay cho giá trị cụ thể của kích thước, số kênh, số head và ngưỡng. Bảng layer và các giá trị triển khai nằm riêng ở [đặc tả YOLO26](architecture-math.md).

## Ý tưởng tổng thể

```text
SWiM3 sạch → train YOLO26s → chọn checkpoint trên validation
    ↓
Cross-domain Test → ảnh ngoài SWiM3, ưu tiên ảnh Việt Nam
    ↓ phân tích lỗi và gắn nhãn thêm
Domain Adaptation → fine-tune checkpoint trên VN-Field train/val
    ↓ kiểm tra trên holdout Việt Nam mới
WasteWise VN → ảnh → detector → box/vật liệu → hướng dẫn xử lý
```

**Mạng được học:** YOLO26s là detector hoàn chỉnh. YOLO26n có cùng sơ đồ, dùng làm đối chứng gọn hơn. **Phần do dự án thiết kế thêm:** bộ tổng hợp, chỉnh sửa thủ công, cơ sở tri thức và giao diện. Những thành phần đó không phải mạng sâu. Mô hình chính hiện **không có block attention/CNN tự thêm**; attention mô tả dưới đây đã thuộc YOLO26 gốc.

## Ký hiệu chung

| Ký hiệu | Nghĩa |
|---|---|
| $I$ | Ảnh RGB gốc |
| $X=T(I)$ | Ảnh sau chuẩn hóa và letterbox |
| $C_\ell$ | Đặc trưng ở mức $\ell$ do backbone tạo |
| $P_\ell$ | Đặc trưng ở mức $\ell$ sau khi neck hợp nhất |
| $H_\ell,W_\ell,D_\ell$ | Chiều cao, chiều rộng, số kênh của đặc trưng ở mức $\ell$ |
| $\theta$ | Toàn bộ trọng số học được của YOLO26 |
| $\mathcal K$ | Cơ sở tri thức hướng dẫn xử lý |

## Luồng bên trong YOLO26

### Backbone: nhìn ảnh ở nhiều mức chi tiết

Ảnh đầu vào là tensor $X\in\mathbb R^{B\times D_{in}\times H\times W}$. Stem và các lớp tích chập giảm dần độ phân giải, trong khi các khối `C3k2` trộn và tái sử dụng đặc trưng:

$$
Z_{\ell+1}=\operatorname{C3k2}\bigl(\operatorname{DownConv}(Z_\ell)\bigr).
$$

Các mức nông giữ thông tin về biên và vật nhỏ; các mức sâu biểu diễn ngữ cảnh rộng hơn. Khối `SPPF` ở vùng sâu dùng pooling lặp để gom ngữ cảnh ở nhiều vùng nhìn. Khối `C2PSA` sau đó cho các vị trí ảnh trao đổi thông tin bằng self-attention. Backbone xuất các mức đặc trưng $\{C_\ell\}$, chưa xuất vật thể cuối.

### Attention có sẵn: một vùng nhìn các vùng khác

Trong `C2PSA`, đặc trưng được chia thành một nhánh truyền thẳng $A$ và một nhánh attention $B$:

$$
(A,B)=\operatorname{Split}(\operatorname{Conv}(Z)),
\qquad Q=W_QB,\ K=W_KB,\ V=W_VB,
$$
$$
\operatorname{Attn}(B)
=W_O\left[\operatorname{softmax}\!\left(\frac{QK^\top}{\sqrt{d}}\right)V
+\operatorname{Pos}(V)\right],
$$
$$
B'=B+\operatorname{Attn}(B),\qquad
B''=B'+\operatorname{FFN}(B'),\qquad
Y=\operatorname{Conv}([A,B'']).
$$

$d$ là chiều khóa attention; $\operatorname{Pos}$ là phép tích chập theo kênh để bổ sung vị trí. Attention giúp trộn thông tin xa, **không tự tạo lời giải thích chắc chắn** cho từng dự đoán. YOLO26 còn có attention trong nhánh sâu của neck.

### Neck: nối chi tiết với ngữ nghĩa

Neck nhận các đặc trưng backbone. Nhánh từ sâu lên nông chuyển ngữ cảnh về mức chi tiết, rồi nhánh từ nông xuống sâu hợp nhất lại:

$$
F_{\ell}=G_{\ell}\bigl([C_{\ell},\operatorname{Up}(F_{\ell+1})]\bigr),
$$
$$
P_{\ell}=J_{\ell}\bigl([F_{\ell},\operatorname{Down}(P_{\ell-1})]\bigr).
$$

$G_\ell$ và $J_\ell$ là các khối `C3k2`; dấu $[\cdot,\cdot]$ là ghép kênh. Kết quả là một tập feature map $\{P_\ell\}$ để head tìm vật nhỏ, vừa và lớn. Neck chưa quyết định vật đó là vật liệu nào.

### Detection head: từ đặc trưng tới box và lớp

Ở mỗi mức $\ell$, head có nhánh hồi quy box $g_\ell$ và nhánh phân lớp $h_\ell$:

$$
D^{box}_{\ell}=g_{\ell}(P_{\ell}),\qquad
Z^{class}_{\ell}=h_{\ell}(P_{\ell}).
$$

Tại điểm lưới $a$ có stride $s_\ell$, $D^{box}_{\ell,a}=(l,t,r,b)$ mã hóa khoảng cách từ tâm tới cạnh box. Sau giải mã:

$$
\tilde b_{\ell,a}=s_\ell(a_x-l,\ a_y-t,\ a_x+r,\ a_y+b),
\qquad p_{\ell,a,k}=\sigma(Z^{class}_{\ell,a,k}).
$$

$k$ chạy trên các nhóm Nhựa, Giấy, Kim loại. Sau lọc điểm thấp, loại box chồng lặp và quy đổi về tọa độ ảnh gốc, detector trả:

$$
\mathcal D_\theta(I)=\{(b_j,c_j,p_j)\}_{j\in\mathcal J},
$$

trong đó $b_j$ là box ảnh gốc, $c_j$ là nhãn và $p_j$ là điểm dự đoán. YOLO26 học bằng loss định vị box và phân lớp trên các nhánh gán mẫu của nó. Điểm $p_j$ **chưa phải xác suất đúng đã hiệu chuẩn**.

## Phần sau mạng: từ dự đoán đến lời khuyên

Đặt $S_{AI}=\{m(c_j):j\in\mathcal J\}$ là các nhóm detector gợi ý sau khi ánh xạ nhãn qua $m$. Nếu người dùng bỏ nhóm $E$ và thêm nhóm $U$:

$$
S_{final}=(S_{AI}\setminus E)\cup U,
\qquad A=\operatorname{Lookup}(S_{final},\mathcal K).
$$

$A$ chứa việc nên làm, việc tránh làm và lưu ý tại Việt Nam theo từng nhóm. Trợ lý hỏi đáp hiện áp dụng quy tắc trên câu hỏi và $\mathcal K$; nó không phải Transformer ngôn ngữ. Ứng dụng hiển thị nguồn của gợi ý để người dùng phân biệt AI, ảnh minh họa và nhóm tự thêm.

## Model được học và đánh giá như thế nào?

### Loss trong lúc train

Với tập box thật $\mathcal G$ và dự đoán $\mathcal D_\theta$, thuật toán gán điểm lưới phù hợp cho từng vật thật. Mỗi nhánh head được tối ưu bằng ba phần:

$$
\mathcal L_{branch}
=\lambda_{box}\mathcal L_{box}
+\lambda_{cls}\mathcal L_{cls}
+\lambda_{dist}\mathcal L_{dist}.
$$

$\mathcal L_{box}$ đo độ khớp hình học của box; $\mathcal L_{cls}$ phạt logit lớp sai; $\mathcal L_{dist}$ phạt sai số khoảng cách từ điểm lưới tới các cạnh. YOLO26 có nhánh gán nhiều điểm cho một vật và nhánh gán chọn lọc hơn; tổng loss là tổng có trọng số của hai nhánh. **Loss giảm chỉ cho thấy tối ưu trên dữ liệu train**, không đủ để khẳng định model nhận diện tốt trên ảnh mới.

### Quy tắc xác định dự đoán đúng/sai

Trước hết đo mức chồng lấp giữa box dự đoán $b$ và box thật $g$:

$$
\operatorname{IoU}(b,g)=\frac{|b\cap g|}{|b\cup g|}.
$$

Ở ngưỡng chồng lấp $\tau$, một dự đoán là **TP** khi lớp đúng và box ghép một-một với box thật có $\operatorname{IoU}\ge\tau$. Box dự đoán dư hoặc sai lớp là **FP**; vật thật không được ghép là **FN**. Tính riêng cho từng lớp, vì điểm trung bình có thể che việc model bỏ sót một loại vật liệu.

### Metric chọn checkpoint

| Metric | Công thức hoặc cách hiểu | Trả lời câu hỏi gì? |
|---|---|---|
| Precision $P_k$ | $TP_k/(TP_k+FP_k)$ | Trong các box được báo là lớp $k$, bao nhiêu box đúng? |
| Recall $R_k$ | $TP_k/(TP_k+FN_k)$ | Trong các vật thật lớp $k$, model tìm được bao nhiêu? |
| $F_{1,k}$ | $2P_kR_k/(P_k+R_k)$ | Cân bằng precision và recall tại một ngưỡng confidence đã chốt. |
| $AP_k(\tau)$ | Diện tích dưới đường precision–recall của lớp $k$ tại ngưỡng IoU $\tau$. | Model xếp hạng detections của lớp đó tốt đến đâu khi quét nhiều ngưỡng confidence? |
| $mAP(\tau)$ | Trung bình $AP_k(\tau)$ qua các lớp. | Chất lượng phát hiện chung tại một chuẩn chồng lấp. |
| $mAP_{range}$ | Trung bình $mAP(\tau)$ trên một dải ngưỡng IoU. | Box có giữ chất lượng khi yêu cầu định vị chặt hơn không? |

Script `evaluate.py` xuất precision, recall, AP và mAP cho cả tập và từng lớp. Trong JSON của script, các tên `map50` và `map50_95` là hai quy ước mAP thông dụng; đây là **tên metric**, không phải giá trị cấu hình mạng. Cần đọc cả recall từng lớp và ảnh dự đoán sai, vì một mAP chung không mô tả hết lỗi của Nhựa, Giấy hoặc Kim loại.

### Metric khi chuẩn bị dùng thật tại Việt Nam

Sau khi khóa checkpoint và ngưỡng confidence $t$, kiểm tra trên tập ảnh Việt Nam chưa dùng để chọn model. Lúc này cần đo **precision, recall, $F_1$, TP/FP/FN tại đúng $t$ mà API sẽ dùng**, thay vì chỉ xem mAP tính qua nhiều ngưỡng. Script `evaluate_vn_field.py` xuất các số này theo lớp và theo bối cảnh ảnh.

Với ảnh âm tính không có vật thuộc các lớp AI, đo thêm:

$$
FPR_{image}=\frac{\#\{I\text{ âm tính nhưng model báo ít nhất một box}\}}
{\#\{I\text{ âm tính}\}}.
$$

Tách kết quả theo bối cảnh như hộ gia đình, quán nước, nền rối, thiếu sáng và vật ngoài phạm vi. Một metric tổng có thể đẹp trong khi một bối cảnh thường gặp ở Việt Nam vẫn thất bại. Đặc biệt phải xem **false negative** trên vật nhỏ và **false positive** khi thấy thủy tinh, pin hoặc bao bì nhiều lớp. Nếu không đạt tiêu chí đã định trước, chưa triển khai nhận diện như kết quả đáng tin cậy; thu thêm ảnh Việt Nam cho train/validation rồi thử lại trên holdout mới.

### Metric triển khai và điều chưa đo

Chất lượng phát hiện cần đi cùng **độ trễ suy luận**, nhất là khi chạy CPU. `benchmark.py` hiện đo median và p95 của thời gian gọi `predict` sau warmup, bao gồm tiền xử lý và hậu xử lý, trên **một ảnh**. Đây chỉ là phép đo kỹ thuật ban đầu; trước deploy phải lặp trên một tập ảnh Việt Nam nhiều kích thước và thiết bị mục tiêu, đồng thời xem bộ nhớ và kích thước checkpoint. Điểm confidence của detector chưa được kiểm tra hiệu chuẩn, vì vậy không diễn giải nó như xác suất đúng.

**Thứ tự đánh giá:** chọn cấu hình bằng SWiM3 validation → đánh giá SWiM3 test một lần → đánh giá VN-Field độc lập → quyết định khả năng triển khai. Tập test không dùng để chỉnh epoch, augmentation hoặc ngưỡng confidence.

## Ranh giới của kiến trúc đã chốt

- **Run chính:** fine-tune YOLO26s trên SWiM3 sạch; YOLO26n là đối chứng. Chọn checkpoint bằng validation.
- **Bước thêm:** Cross-domain Test trên ảnh ngoài SWiM3, ưu tiên ảnh Việt Nam; sau đó Domain Adaptation bằng ảnh Việt Nam đã gắn box và fine-tune từ checkpoint SWiM3. Chỉ triển khai sau khi kiểm tra trên holdout Việt Nam mới, độc lập với dữ liệu adaptation. Nếu model SWiM3 đã đạt cổng chất lượng, adaptation vẫn là phép thử có kiểm soát và chỉ giữ bản cải tiến nếu không gây suy giảm quan trọng.
- **Chưa có trong model:** ECA/CBAM hay Transformer mới do nhóm thêm. Nếu muốn thử attention mới, đó là một ablation riêng, không được gọi là cải tiến cho đến khi vượt baseline trên validation và đạt giới hạn độ trễ.
- **Có thể giải thích:** đường đi tensor, cách tạo box và lớp, vùng ảnh được đánh dấu, nguồn của lời khuyên. **Chưa giải thích nhân quả đầy đủ:** tại sao đúng các pixel đó làm mạng ra một nhãn cụ thể.
