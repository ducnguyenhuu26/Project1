# Kiến trúc đầy đủ của WasteWise VN và mức độ giải thích được

Tài liệu [architecture-math.md](architecture-math.md) đặc tả **mạng YOLO26**: 24 module chính, các tensor trung gian, attention C2PSA, detection head và loss. Tài liệu này đặc tả **hệ thống của dự án** sau mạng đó. Hai thứ này cần được trình bày tách bạch khi bảo vệ.

## 1. Chốt thành phần nào là mạng học sâu

| Thành phần | Đầu vào → đầu ra | Có học tham số từ dữ liệu? | Trạng thái |
|---|---|---|---|
| YOLO26s, backbone + neck + head | ảnh RGB → box, lớp, điểm lớp | Có; fine-tune ba lớp | Mạng chính, chờ GPU train đầy đủ |
| YOLO26n | ảnh RGB → box, lớp, điểm lớp | Có; fine-tune ba lớp | Đối chứng gọn, đã chạy CPU smoke |
| C2PSA tại layer 10 và PSABlock tại layer 22 | feature map → feature map | Có | **Có sẵn trong YOLO26 gốc**, không phải đóng góp riêng |
| Tổng hợp, chỉnh sửa, tra cứu lời khuyên | detections + lựa chọn người dùng → hướng dẫn | Không | Đã triển khai bằng quy tắc và JSON |
| Trợ lý tra cứu | câu hỏi + nhóm vật liệu → câu trả lời | Không | Đã triển khai bằng quy tắc và JSON; không phải LLM |

**Model hiện tại không có block CNN/Transformer/attention do dự án tự thêm.** Đây là quyết định kỹ thuật cho run chính trước khi có đối chứng chất lượng. Không nên gọi toàn bộ hệ thống là “YOLO26 backbone + mạng riêng”: YOLO26 ở đây là *complete detector*, gồm backbone, neck và head. Phần riêng của dự án là luồng chuyển detection thành tư vấn và tương tác có nguồn gốc rõ ràng.

## 2. Đồ thị đầu vào đến đầu ra cuối

Cho ảnh $I\in[0,255]^{H_0\times W_0\times3}$. Tiền xử lý $T$ hiệu chỉnh EXIF, chuyển RGB, resize/letterbox và chuẩn hóa:

$$
X=T(I)\in[0,1]^{B\times3\times H\times W}.
$$

Detector ba lớp $F_\theta$ gồm backbone $B_\theta$, neck $N_\theta$ và head $H_\theta$:

$$
(C_3,C_4,C_5)=B_\theta(X),\qquad
(P_3,P_4,P_5)=N_\theta(C_3,C_4,C_5),
$$
$$
(D_3,Z_3,D_4,Z_4,D_5,Z_5)=H_\theta(P_3,P_4,P_5).
$$

Tại ảnh vuông $640\times640$, $P_3,P_4,P_5$ có stride $(8,16,32)$ và không gian $(80^2,40^2,20^2)$. Mỗi điểm có bốn số hồi quy box và ba logit lớp. Sau giải mã, ngưỡng và khử box trùng, adapter thu được

$$
\mathcal D_\theta(I)=\{(b_j,c_j,s_j)\}_{j=1}^{M},
\quad b_j\in[0,W_0]\times[0,H_0]\times[0,W_0]\times[0,H_0],
\quad c_j\in\{0,1,2\}.
$$

Các box là tọa độ ảnh gốc; $s_j$ là điểm mô hình, chưa hiệu chuẩn thành xác suất đúng. Tập nhóm mà AI gợi ý là $S_{AI}=\{m(c_j):j=1,\ldots,M\}$, với $m(0)=\text{plastic}$, $m(1)=\text{paper}$, $m(2)=\text{metal}$. Số khung ước tính mỗi nhóm là $\hat n_k=\sum_j\mathbf1[c_j=k]$; đây không phải số lượng đồ vật chắc chắn.

Trên UI, người dùng có thể bỏ nhóm $E$ và thêm nhóm $U$. Tập dùng để xem lời khuyên là

$$
S_{final}=(S_{AI}\setminus E)\cup U.
$$

Mỗi nhóm giữ nguồn gốc hiển thị: `AI`, `minh họa` hoặc `bạn thêm`. Đây là chỉnh sửa ở tầng ứng dụng; **không thay đổi trọng số** $\theta$ và không sửa box dự đoán. Các nhóm pin, thủy tinh, hữu cơ chỉ có thể vào $U$ hoặc tra cứu thủ công, vì detector chưa được học các lớp đó.

Với cơ sở tri thức $\mathcal K$ trong `backend/knowledge.json`, thẻ hướng dẫn là phép tra cứu

$$
A(S_{final},\mathcal K)=\{\mathcal K[m].(\text{do},\text{avoid},\text{caution},\text{vn\_tip}):m\in S_{final}\}.
$$

Trợ lý hiện tại trả $R(q,S_{final},\mathcal K)$: áp dụng quy tắc cảnh báo an toàn cho câu hỏi về đốt rác trước, rồi FAQ/khớp từ vật liệu, sau cùng trả lời theo nhóm đang chọn hoặc báo chưa có hướng dẫn. $R$ là hàm quy tắc, không có Transformer ngôn ngữ và không học tham số. Đầu ra cuối cho người dùng là **ảnh có box + danh sách nhóm + thẻ hành động + câu trả lời tra cứu**, không phải chỉ vector lớp của YOLO.

## 3. “Giải thích được” nghĩa là gì ở bản này?

Có thể truy vết từng quyết định ở mức ứng dụng:

1. **Gợi ý vật liệu:** box $b_j$ cho thấy vùng ảnh mà detector gắn lớp $c_j$ và điểm $s_j$; UI cho phép ẩn lớp gợi ý sai.
2. **Nguồn của một nhóm:** chỉ rõ nhóm đến từ model, ảnh minh họa hay người dùng thêm. `DemoDetector` không được xem là chứng cứ AI.
3. **Lời khuyên:** với nhóm $m$, nội dung lấy từ mục $\mathcal K[m]$ có trường hành động và cảnh báo riêng, thay vì sinh ra từ logit không kiểm soát.
4. **Giới hạn suy luận:** ảnh RGB không chứng minh mã nhựa, thành phần kim loại, độ sạch, khả năng tái chế hoặc cách xử lý hợp pháp tại từng địa phương.

Đây là **giải thích ở mức vùng ảnh và nguồn quy tắc**, chưa phải giải thích nhân quả bên trong CNN. Attention map của C2PSA không mặc nhiên là bằng chứng “model nhìn vào đây vì vậy dự đoán nhựa”. Muốn đánh giá giải thích thị giác sâu hơn cần thí nghiệm riêng như occlusion sensitivity/Grad-CAM và kiểm tra độ ổn định; hiện code chưa triển khai hay kiểm chứng chúng.

## 4. Phần mở rộng mạng có thể thử sau baseline

Để kiểm tra giả thuyết vật nhỏ và bối cảnh nhầm lẫn ở ảnh rác Việt Nam, một **ứng viên ablation** là thêm channel attention nhẹ vào feature map $P_4$ trước Detect. Ví dụ ECA:

$$
z_c=\frac{1}{H_4W_4}\sum_{u,v}P_{4,c,u,v},\qquad
a=\sigma(\operatorname{Conv1D}_{k}(z)),\qquad
P'_4=P_4\odot a.
$$

Block này học trọng số theo kênh, không tạo ma trận attention không gian $1600\times1600$ ở P4. Nhưng đó **mới là thiết kế thí nghiệm, chưa có trong checkpoint, YAML hoặc training code hiện tại**. Nếu triển khai, cần giữ baseline YOLO26s cùng split/seed/augmentation, nạp lại phần trọng số tương thích, đo mAP50:95/recall từng lớp và latency, rồi chỉ chọn nếu validation thực sự cải thiện. Không khẳng định một block thêm sẽ tốt hơn trước khi có số đo.

**Kiến trúc để train ngày mai:** YOLO26s 3 lớp là ứng viên chính; YOLO26n cùng protocol là đối chứng. Chốt checkpoint theo validation; test chỉ dùng sau khi chọn. Nếu muốn đóng góp ở cấp mạng, ECA ở P4 là một ablation riêng cần triển khai và đo, không thuộc mô hình chính đã chốt.
