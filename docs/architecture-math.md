# Đặc tả toán học YOLO26 cho WasteWise VN

Tài liệu này đối chiếu trực tiếp `ultralytics==8.4.210` đang cài: `cfg/models/26/yolo26.yaml`, `nn/modules/{block,conv,head}.py`, `utils/{loss,tal}.py`. Mô hình chính là **YOLO26s fine-tune 3 lớp**; YOLO26n có cùng đồ thị nhưng ít kênh. Công thức dưới đây là forward của detector; `AdviceEngine` tra cứu JSON, không phải mạng học sâu.

## 1. Input và ký hiệu

Ảnh gốc RGB có kích thước $H_0\times W_0$. Letterbox tạo tensor
$$
X_0\in[0,1]^{B\times3\times640\times640},\qquad
r=\min(640/W_0,640/H_0),\quad p_x=(640-rW_0)/2,\quad p_y=(640-rH_0)/2.
$$
Ở đây cố định 640×640 để mô tả training và tính shape. Khi predict một ảnh chữ nhật, Ultralytics có thể dùng padding chữ nhật tối thiểu, nên $H,W$ và số điểm lưới thay đổi; công thức và ba stride vẫn giữ nguyên.
Ký hiệu tensor theo thứ tự $B\times C\times H\times W$, batch $B$. Với $Y$ có $C$ kênh, `Conv(k,s)` là
$$
\mathcal C_{k,s}(Y)_{b,o,u,v}=\operatorname{SiLU}\!\left(\operatorname{BN}\!\left(
\sum_{c=1}^{C}\sum_{i,j=0}^{k-1}K_{o,c,i,j}Y_{b,c,su+i,sv+j}
\right)\right).
$$
Padding giữ kích thước khi $s=1$; $s=2$ giảm đôi chiều không gian. DWConv dùng một kernel cho từng kênh, rồi conv $1\times1$ mới trộn các kênh. Concat ghép theo chiều $C$; Up nhân đôi $H,W$ bằng nearest-neighbor.

Ground truth của mỗi vật trong file YOLO là $(c,x_c,y_c,w,h)$, với tọa độ chuẩn hóa trong $[0,1]$. Khi huấn luyện, box được chuyển về $(x_1,y_1,x_2,y_2)$ ở không gian ảnh đầu vào; $c\in\{0,1,2\}$ ứng với Plastic/Paper/Metal.

## 2. Toàn bộ 24 module chính ở input 640×640

Cột shape là **đầu ra**; `n/s` cho số kênh của YOLO26n và YOLO26s. Mọi `C3k2` và `C2PSA` khai báo `repeats=2` trong YAML nhưng depth multiplier 0,5 làm **một khối lặp bên trong** cho cả n và s. Tầng 23 nhận ba tensor, không có một shape feature-map duy nhất.

| i | Từ layer | Phép toán | $H\times W$ | $C_n/C_s$ |
|---:|---|---|---:|---:|
| 0 | ảnh | Conv $3\times3,s=2$ | 320×320 | 16 / 32 |
| 1 | 0 | Conv $3\times3,s=2$ | 160×160 | 32 / 64 |
| 2 | 1 | C3k2, Bottleneck, expansion $e=.25$ | 160×160 | 64 / 128 |
| 3 | 2 | Conv $3\times3,s=2$ | 80×80 | 64 / 128 |
| 4 | 3 | C3k2, Bottleneck, $e=.25$ | 80×80 | 128 / 256 |
| 5 | 4 | Conv $3\times3,s=2$ | 40×40 | 128 / 256 |
| 6 | 5 | C3k2, C3k | 40×40 | 128 / 256 |
| 7 | 6 | Conv $3\times3,s=2$ | 20×20 | 256 / 512 |
| 8 | 7 | C3k2, C3k | 20×20 | 256 / 512 |
| 9 | 8 | SPPF $k=5,n=3$, residual | 20×20 | 256 / 512 |
| 10 | 9 | C2PSA, 1 PSABlock | 20×20 | 256 / 512 |
| 11 | 10 | Up ×2 | 40×40 | 256 / 512 |
| 12 | 11, 6 | Concat | 40×40 | 384 / 768 |
| 13 | 12 | C3k2, C3k | 40×40 | 128 / 256 |
| 14 | 13 | Up ×2 | 80×80 | 128 / 256 |
| 15 | 14, 4 | Concat | 80×80 | 256 / 512 |
| 16 | 15 | C3k2, C3k = $P_3$ | 80×80 | 64 / 128 |
| 17 | 16 | Conv $3\times3,s=2$ | 40×40 | 64 / 128 |
| 18 | 17, 13 | Concat | 40×40 | 192 / 384 |
| 19 | 18 | C3k2, C3k = $P_4$ | 40×40 | 128 / 256 |
| 20 | 19 | Conv $3\times3,s=2$ | 20×20 | 128 / 256 |
| 21 | 20, 10 | Concat | 20×20 | 384 / 768 |
| 22 | 21 | C3k2, Bottleneck + PSABlock = $P_5$ | 20×20 | 256 / 512 |
| 23 | 16, 19, 22 | Detect, ba lớp | 8.400 điểm | 7 số/điểm |

Ví dụ cho **YOLO26s**: $P_3\in\mathbb R^{B\times128\times80\times80}$, $P_4\in\mathbb R^{B\times256\times40\times40}$, $P_5\in\mathbb R^{B\times512\times20\times20}$. Ở **YOLO26n**, các kênh tương ứng là 64, 128, 256. Backbone là 0–10; neck FPN/PAN là 11–22; detection head là 23. YAML COCO trước fine-tune có khoảng 10,01 triệu tham số ở s và 2,57 triệu ở n; head ba lớp làm số tham số thay đổi.

## 3. Bên trong mỗi CNN block

### Bottleneck và C3k2

`Bottleneck` với shortcut (nếu số kênh vào/ra bằng nhau) tính
$$
\mathcal B(U)=U+\mathcal C_{3,1}^{c'\to c}\bigl(\mathcal C_{3,1}^{c\to c'}(U)\bigr),
$$
Ở Bottleneck, $c'=\lfloor e_Bc\rfloor$ với $e_B=0.5$ mặc định; bỏ $+U$ nếu không đủ điều kiện shortcut. C3k cũng dùng bottleneck nhưng bọc trong CSP gồm hai nhánh và conv $1\times1$ hợp nhất. Trong C3k2 có cờ c3k=True, khối trong là C3k chứa hai bottleneck. Ở tầng 22, cờ attn=True thay khối trong bằng Bottleneck rồi PSABlock.

Cho đầu vào $U\in\mathbb R^{B\times C_{in}\times h\times w}$, đầu ra $C_{out}$, đặt $c=\lfloor eC_{out}\rfloor$. `C3k2` thực hiện
$$
(A,B)=\operatorname{chunk}_C(\mathcal C_{1,1}^{C_{in}\to2c}(U)),\qquad
B_1=\mathcal M(B),\qquad
\operatorname{C3k2}(U)=\mathcal C_{1,1}^{3c\to C_{out}}([A,B,B_1]).
$$
Vì số lặp thực tế bằng 1, tensor nối có $3c$ kênh; với $r$ lặp tổng quát sẽ là $(2+r)c$. Expansion ngoài của C3k2 là $e=.25$ ở tầng 2/4 và $e=.5$ ở các tầng còn lại. Đây là phép nối feature maps.

### SPPF

Với $U=X_8$ ở tầng 8, cho $V_0=\operatorname{ConvBN}_{1\times1}(U)$ giảm một nửa kênh, không dùng SiLU ở conv này. Sau đó
$$
V_j=\operatorname{MaxPool}_{5\times5,s=1}(V_{j-1}),\ j=1,2,3,\qquad
X_9=U+\mathcal C_{1,1}([V_0,V_1,V_2,V_3]).
$$
Các nhánh $5,9,13$ về receptive field được tạo bằng ba lần pool 5×5 liên tiếp.

## 4. Attention: chính xác tensor nào đi vào, ra

YOLO26 dùng spatial multi-head self-attention bên trong CNN, không có ViT encoder tách riêng. Ở tầng 10, đầu vào $X_9$ có $C=256$ kênh với n hoặc $C=512$ kênh với s, không gian 20×20. C2PSA giảm/chia kênh:
$$
(A,B_0)=\operatorname{split}\bigl(\mathcal C_{1,1}^{C\to C}(X_9)\bigr),\quad
A,B_0\in\mathbb R^{B\times c\times20\times20},\quad c=C/2.
$$
Nhánh $A$ đi thẳng; $B_0$ qua một `PSABlock`. Với `n`, $c=128$, số head $h=2$; với `s`, $c=256$, $h=4$. Mỗi head có $d_v=64$, $d_k=\lfloor0.5d_v\rfloor=32$; số vị trí $N=400$.

Conv $1\times1$ sinh $Q,K,V$ từ chính $B_0$:
$$
Q,K\in\mathbb R^{B\times h\times32\times400},\qquad
V\in\mathbb R^{B\times h\times64\times400}.
$$
Với vị trí $i,j$ và head $a$:
$$
\alpha^{(a)}_{ij}=\frac{\exp((q_i^{(a)})^\top k_j^{(a)}/\sqrt{32})}
{\sum_{t=1}^{400}\exp((q_i^{(a)})^\top k_t^{(a)}/\sqrt{32})},\qquad
o_i^{(a)}=\sum_{j=1}^{400}\alpha^{(a)}_{ij}v_j^{(a)}.
$$
Tensor $h\times400\times400$ cho phép một vùng 20×20 nhìn các vùng còn lại. Implementation cộng thêm **positional encoding depthwise conv 3×3 trên $V$**, rồi chiếu bằng conv $1\times1$:
$$
T=\operatorname{Proj}_{1\times1}\bigl(\operatorname{ConcatHeads}(o)+\operatorname{DWConv}_{3\times3}(V)\bigr).
$$
`PSABlock` có hai residual:
$$
B_1=B_0+T,\qquad
B_2=B_1+\operatorname{ConvBN}_{1\times1}^{2c\to c}\!\left(
\mathcal C_{1,1}^{c\to2c}(B_1)\right),\qquad
X_{10}=\mathcal C_{1,1}([A,B_2]).
$$
Tầng 22 lặp lại PSABlock trên nhánh sâu của C3k2 sau một Bottleneck: hidden $c=128,h=2$ với n hoặc $c=256,h=4$ với s, vẫn ở 20×20. Vì thế có hai vị trí attention, tầng 10 và 22; không phải mọi C3k2 đều có attention.

## 5. Neck đa tỉ lệ

Gọi $U_i$ là đầu ra tầng $i$. Nhánh top-down truyền ngữ nghĩa từ P5 về P3:
$$
U_{13}=\operatorname{C3k2}([\operatorname{Up}_2(U_{10}),U_6]),\qquad
P_3=U_{16}=\operatorname{C3k2}([\operatorname{Up}_2(U_{13}),U_4]).
$$
Nhánh bottom-up đưa thông tin vị trí chi tiết trở lại mức trung/big:
$$
P_4=U_{19}=\operatorname{C3k2}([\mathcal C_{3,2}(P_3),U_{13}]),\qquad
P_5=U_{22}=\operatorname{C3k2}_{\rm attn}([\mathcal C_{3,2}(P_4),U_{10}]).
$$
Điểm quan trọng: detector dùng cả 80×80 cho vật nhỏ và 20×20 cho vật lớn; không phân loại dựa trên một vector toàn ảnh.

## 6. Head, decode và output cuối

Ở mỗi mức $\ell\in\{3,4,5\}$, với input $P_\ell$ có $C_\ell$ kênh, **nhánh box** YOLO26s là
$$
D_\ell=\operatorname{Conv2d}_{1\times1}^{32\to4}\circ
\mathcal C_{3,1}^{32\to32}\circ\mathcal C_{3,1}^{C_\ell\to32}(P_\ell)
\in\mathbb R^{B\times4\times H_\ell\times W_\ell}.
$$
**Nhánh lớp** dùng hai cụm depthwise separable conv:
$$
Z_\ell=\operatorname{Conv2d}_{1\times1}^{128\to3}\circ
[\operatorname{DWConv}_{3\times3}^{128}\to\mathcal C_{1,1}^{128\to128}]\circ
[\operatorname{DWConv}_{3\times3}^{C_\ell}\to\mathcal C_{1,1}^{C_\ell\to128}](P_\ell)
\in\mathbb R^{B\times3\times H_\ell\times W_\ell}.
$$
YOLO26n dùng 16 kênh ở nhánh box; nhánh lớp có 64 kênh khi dựng YAML mới với `nc=3`. Checkpoint n mini đã lưu trong repo giữ 80 kênh trung gian ở nhánh lớp từ quá trình transfer, nhưng **đầu ra cuối vẫn đúng 3 lớp**. Mỗi mức có cả head *one-to-many* và bản sao *one-to-one* để huấn luyện. Runtime API hiện chọn one-to-many mặc định, rồi lọc box theo confidence/NMS; chế độ one-to-one NMS-free chưa được bật.

Mỗi điểm lưới $(u,v)$ có tâm $a=(u+0.5,v+0.5)$. Bốn số $D_\ell$ là khoảng cách $d=(l,t,r,b)$ từ tâm điểm đến bốn cạnh. Box trong ảnh letterbox là
$$
\tilde b=\bigl(s_\ell(a_x-l),\ s_\ell(a_y-t),\ s_\ell(a_x+r),\ s_\ell(a_y+b)\bigr),
\qquad s_3=8,\ s_4=16,\ s_5=32.
$$
Điểm lớp là $p_k=\sigma(Z_{\ell,k,u,v})$, $k\in\{0,1,2\}$. reg_max=1 nghĩa là bốn khoảng cách được hồi quy trực tiếp, không qua 16-bin DFL. Tổng số điểm là
$$
80^2+40^2+20^2=8400,\qquad
\text{raw output cho ba lớp: }\mathbb R^{B\times(4+3)\times8400}.
$$
Đây là tensor thô, **không phải 8.400 vật thể cuối**. Sau threshold, chọn lớp và khử box chồng lấp, còn $M\le8400$ detections. Ultralytics đưa box từ letterbox về pixel ảnh gốc:
$$
x_i=\operatorname{clip}((\tilde x_i-p_x)/r,0,W_0),\qquad
y_i=\operatorname{clip}((\tilde y_i-p_y)/r,0,H_0).
$$
API trả $\{(b_j,c_j,p_j)\}_{j=1}^{M}$ với bbox_xyxy trên ảnh gốc. UI vẽ SVG cùng hệ tọa độ $(W_0,H_0)$. Phần lời khuyên là phép tra cứu $A=g(\{c_j\},q,\mathcal K)$, với $q$ là lựa chọn thủ công và $\mathcal K$ là knowledge base; đó không phải output trực tiếp của YOLO.

## 7. Khi train, tối ưu cái gì?

Cho $y_{a,k}$ là target mềm cho điểm lưới $a$, và $w_a=\sum_k y_{a,k}$. Task-aligned assignment xếp ứng viên dựa trên điểm lớp và IoU, theo dạng $m_{a,g}=p_{a,c_g}^{0.5}\operatorname{IoU}(b_a,b_g)^6$; nhánh one-to-many giữ nhiều ứng viên, nhánh one-to-one chọn một. Đây là cách gắn ground truth lên 8.400 vị trí, không phải mọi vị trí đều là vật thật.

Với tập positive $\mathcal F$, implementation có ba thành phần:
$$
L_{\rm box}=\frac{\sum_{a\in\mathcal F}w_a[1-\operatorname{CIoU}(b_a,b_a^*)]}{\max(1,\sum_a w_a)},\quad
L_{\rm cls}=\frac{\sum_{a,k}\operatorname{BCEWithLogits}(z_{a,k},y_{a,k})}{\max(1,\sum_{a,k}y_{a,k})},
$$
$$
L_{\rm L1}=\frac{\sum_{a\in\mathcal F}w_a\,\|\bar d_a-\bar d_a^*\|_1/4}{\max(1,\sum_a w_a)},\qquad
L_{\rm branch}=7.5L_{\rm box}+0.5L_{\rm cls}+1.5L_{\rm L1}.
$$
$\bar d$ là bốn khoảng cách chuẩn hóa theo stride và kích thước ảnh. Hệ số 1.5 nằm ở biến `dfl` của Ultralytics nhưng **với `reg_max=1` nó nhân L1**, không phải DFL. Loss hai nhánh gộp lại:
$$
L=\alpha L_{\rm one\text{-}to\text{-}many}+(1-\alpha)L_{\rm one\text{-}to\text{-}one}.
$$
Trong mã phiên bản hiện tại, $\alpha$ bắt đầu ở 0,8 và giảm dần về mức cuối 0,1. Đó là lý do log mini train có `box_loss`, `cls_loss`, `l1_loss`.

Nguồn đối chiếu: [YAML YOLO26 chính thức](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/models/26/yolo26.yaml), [mô tả kiến trúc](https://docs.ultralytics.com/guides/yolo-architecture), và source `block.py`, `head.py`, `loss.py`, `tal.py` của `ultralytics==8.4.210` trong môi trường dự án.
