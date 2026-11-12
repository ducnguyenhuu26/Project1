# Chiến lược dữ liệu Việt Nam cho WasteWise VN

## Trạng thái 12/11/2026

- **Đã có local:** SWiM3, 6.363 ảnh thực trong ba split; bản dẫn xuất sạch `datasets/swim3_clean` có 5.127/372/384 ảnh train/validation/test. Đây là baseline phát hiện ba lớp Plastic/Paper/Metal, **chưa có chứng cứ tập này được chụp tại Việt Nam**. Xem [data-audit.md](data-audit.md).
- **Chưa có local:** tập ảnh Việt Nam có bounding box được kiểm toán và quyền sử dụng rõ ràng. Chưa đánh giá độ chính xác tại Việt Nam; CPU smoke chỉ kiểm tra pipeline.
- **Không tự gộp:** ảnh báo chí chưa có nhãn box, ảnh phân loại toàn ảnh, ảnh rác sông/đường phố và bộ dữ liệu ba lớp vật liệu sinh hoạt không phải cùng một miền dữ liệu.

## Các nguồn Việt Nam đã xác minh ở mức trang công bố

| Nguồn | Bằng chứng và nhãn | Mức phù hợp |
|---|---|---|
| [pLitterStreet](https://github.com/gicait/pLitter) / [Zenodo](https://zenodo.org/records/8288500) | Nhóm tác giả xác nhận có ảnh ở Cần Thơ; hơn 13.000 ảnh **tổng cộng từ nhiều nước**, box COCO, bối cảnh camera gắn xe và rác nhựa ven đường. Trang Zenodo ghi archive ảnh 13,7 GB. Chưa xác định số ảnh Việt Nam hoặc cách lọc địa điểm trong archive. | Có thể dùng lát cắt Cần Thơ để kiểm tra ngoài miền **nhựa ven đường** sau khi xác nhận metadata. Không phải tập chính cho Nhựa/Giấy/Kim loại trong ảnh sinh hoạt. |
| [RiverPlasticDataset](https://github.com/KhimCathleenSaddi/RiverPlasticDataset) / [bài báo](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025WR040605) | Bài báo nêu **206 ảnh, 2.401 annotation** cho tập Việt Nam tại TP.HCM; ảnh và box của vật trôi trên sông, phân lớp chi tiết gồm chai/túi nhựa, bao bì, lon, chai thủy tinh. | Có nguồn Việt Nam rõ, nhưng góc nhìn sông khác ảnh người dùng. Chỉ dùng như phép thử chuyển miền; cần kiểm tra bản phát hành và mapping trước khi sử dụng. |
| [VN-trash, Vo và cộng sự (2019)](https://www.mendeley.com/catalogue/74fa7a4e-2353-343e-a47f-37d849f776fc/) | Công bố mô tả 5.904 ảnh Việt Nam, ba lớp **hữu cơ/vô cơ/y tế**, tác vụ **classification toàn ảnh**. Chưa xác minh được bản tải công khai/giấy phép. | Không nạp thẳng vào YOLO ba lớp vật liệu: thiếu bounding box và ontology không khớp. |
| [Công trình Hanoi 2026](https://docs.lib.purdue.edu/cib-conferences/vol2/iss1/48/) | Nhóm tác giả báo cáo 21.329 ảnh, trong đó 6.171 ảnh rác bẩn chụp ở Hà Nội; dùng YOLOv8s. Trang công bố chưa cho thấy link tải bộ ảnh/nhãn. | Rất gần bối cảnh Việt Nam; cần liên hệ tác giả hoặc tìm bản phát hành hợp lệ trước khi dùng. Không tính là dữ liệu đã có. |
| [householdWaste, ĐH Công nghệ Đồng Nai](https://universe.roboflow.com/dong-nai-technology-university/householdwaste) | Card công khai ghi 230 ảnh detection, CC BY 4.0, nhưng nhãn hiển thị chỉ `Waste` và `ư`; không có mô tả nguồn chụp. | Không đạt nhãn vật liệu; không dùng cho run chính. |

Một [dự án Roboflow/GitHub](https://github.com/PhucHuwu/YOLOv8_Detecting_and_Classifying_Waste) có 9.413 ảnh với box và bảy nhãn, trong đó có paper/plastic/metal. Tên workspace tiếng Việt **không chứng minh ảnh chụp tại Việt Nam**; cần truy xuất nguồn ảnh, bản dataset gốc và kiểm toán trùng ảnh trước khi xem là tập VN.

## Quyết định dữ liệu cho lần train gần nhất

1. Chạy baseline YOLO26s/n trên `swim3_clean`, báo cáo rõ đó là kết quả **trong miền SWiM3**. Giữ test SWiM3 đóng tới khi chọn checkpoint bằng validation.
2. Tạo **VN-Field** riêng từ ảnh do nhóm tự chụp/có quyền dùng. Chụp bằng điện thoại đúng luồng ứng dụng: bàn bếp, góc phân loại, chai/lon/hộp tại hộ gia đình, quán nước hoặc khu thu gom có phép. Có cả cảnh nhiều vật, vật nhỏ, nền rối, thiếu sáng và vật ngoài ba lớp. Ghi nguồn, địa điểm ở mức không định danh, thiết bị và phiên chụp.
3. Mục tiêu ban đầu: khoảng **150–300 ảnh có box để đánh giá ngoài miền**, rồi bổ sung train nếu lỗi có hệ thống. Số này là kế hoạch thu thập, **không phải dữ liệu đang có**. Tách theo phiên/địa điểm/chủ thể chụp; ảnh cùng một cảnh hoặc video không rơi vào nhiều split.
4. Gắn box cho **mọi vật thuộc ba lớp** có thể nhận diện trong ảnh, không chỉ vật chính. Ghi `uncertain/ignore` cho đồ nhiều lớp hoặc khó xác định thay vì ép nhãn. Vật như pin, thủy tinh, thức ăn vẫn có thể xuất hiện để đo false positive nhưng không tự thành lớp AI. Rà soát ontology SWiM3: `wood` không nên coi là giấy, ly/hộp tráng phủ phải có quy ước nhất quán.
5. Đánh giá riêng `SWiM3-test` và `VN-Field-test`: mAP50:95, recall từng lớp, precision/false positives ở cảnh có vật ngoài ba lớp, lỗi theo nhóm bối cảnh. Nếu cần adaptation, dùng `VN-Field-train/val` riêng rồi đánh giá lại trên một `VN-Field-test` chưa từng xem để tune.

Ảnh bài báo chỉ có thể trở thành dữ liệu định lượng khi có quyền sử dụng, ảnh gốc, box được gán/kiểm tra và quy trình chống trùng. Không dùng ảnh báo chí chưa nhãn để công bố mAP hoặc gộp vào test cuối.

## Cổng nghiệm thu trước khi dùng thật ở Việt Nam

**Train xong trên SWiM3 không đồng nghĩa được triển khai thật.** Khóa checkpoint và ngưỡng confidence bằng validation trước khi mở `VN-Field-test`. Tập này cần có ảnh sinh hoạt chụp bằng điện thoại ở nhiều phiên/địa điểm, ảnh nhiều vật, nhựa/giấy/kim loại nhỏ hoặc bị che, ánh sáng kém, bao bì Việt Nam, và ảnh âm tính chỉ chứa vật ngoài ba lớp. Định danh phiên chụp để tránh ảnh gần trùng giữa các tập.

Cấu trúc để chấm ở ngưỡng triển khai:

```text
datasets/vn_field/test/
  images/household/anh_001.jpg
  images/drink_shop/anh_002.jpg
  images/negative/anh_003.jpg
  labels/household/anh_001.txt
  labels/drink_shop/anh_002.txt
  labels/negative/anh_003.txt  # file rỗng: không có vật thuộc ba lớp
```

Mọi ảnh phải có file nhãn YOLO tương ứng. Nhãn chỉ dùng `0=Plastic`, `1=Paper`, `2=Metal`; mỗi vật thuộc ba lớp cần được gắn box. Ảnh âm tính có file nhãn rỗng, không phải file thiếu. Với vật nhiều lớp hoặc không xác định được, quy tắc nhãn/loại ảnh phải được chốt trước khi chấm.

```powershell
.\.venv\Scripts\python.exe ml\scripts\evaluate_vn_field.py --model DUONG_DAN_BEST_PT --images datasets\vn_field\test\images --conf 0.25 --out outputs\vn_field_test.json
```

Script xuất TP/FP/FN, precision, recall, F1 **theo từng lớp và từng bối cảnh**, cùng tỷ lệ ảnh âm tính bị báo nhầm. Đây là đo ở ngưỡng thực tế của API; vẫn chạy `evaluate.py` riêng với YAML của VN-Field để có mAP50:95 chuẩn. Không dùng từ “accuracy” toàn cục cho detection vì nó che mất lỗi bỏ sót và báo nhầm.

**Tiêu chí chấp nhận cần đăng ký trước khi xem test.** Mốc kỹ thuật đề xuất cho pilot: ít nhất 100 vật được gắn box mỗi lớp và 50 ảnh âm tính; tại ngưỡng cố định, mỗi lớp đạt precision và recall ít nhất 0,80, và không quá 10% ảnh âm tính có báo nhầm. Đây là mục tiêu sản phẩm sơ bộ, không phải chuẩn khoa học hay cam kết chất lượng; cần xem khoảng bất định, kiểm tra lỗi nguy hiểm và phân bố bối cảnh trước khi mở rộng. Nếu mẫu không đủ, trạng thái là *chưa đủ bằng chứng*, không coi là pass.

Nếu không đạt: **không bật chế độ nhận diện như tính năng đáng tin cậy cho người dùng thật**. Phân tích lỗi, thu thập thêm `VN-Field-train/val`, sửa nhãn/ontology và fine-tune; giữ test cũ để báo cáo lịch sử, tạo **test Việt Nam mới** cho quyết định sau khi đã điều chỉnh. Trong thời gian đó chỉ dùng demo có cảnh báo và tra cứu/chỉnh sửa thủ công. Không lấy điểm trên `VN-Field-test` để chọn epoch, confidence hay augmentation.

## Bước Domain Adaptation sau Cross-domain Test

Quy trình đầy đủ: **SWiM3 train → Cross-domain Test → Domain Adaptation → VN holdout mới → WasteWise VN**. Cross-domain Test trước adaptation là phép đo độ tổng quát hóa của checkpoint SWiM3. Ảnh đã dùng để ra quyết định adaptation được lưu như bằng chứng ban đầu; không dùng lại chúng như tập test cuối của bản model đã thích nghi.

Sau khi có ảnh Việt Nam được cấp quyền và gắn box, tách theo phiên/địa điểm thành `VN-Field-train`, `VN-Field-val` và `VN-Field-test-new`. Ảnh cùng cảnh, ảnh chụp liên tiếp hoặc bản augmentation phải nằm cùng một nhóm. Giữ nguyên ontology và thứ tự nhãn Plastic/Paper/Metal. Có thể áp dụng augmentation ánh sáng, xoay/góc chụp và nền ở mức hợp lý **chỉ trong train**, không làm biến dạng validation/test.

`train.py --init-checkpoint` bắt đầu **run fine-tune mới** từ trọng số `best.pt` đã chọn trên SWiM3. Nó khác `--resume-checkpoint`, vốn tiếp tục optimizer và lịch huấn luyện của run bị gián đoạn. Ví dụ sau chỉ chạy khi đã có VN-Field được gắn nhãn và kiểm toán:

```powershell
.\.venv\Scripts\python.exe ml\scripts\train.py --data datasets\vn_field\data.yaml --init-checkpoint DUONG_DAN_SWIM3_BEST_PT --device 0 --name waste_yolo26s_vn_adapt --lr0 0.001
.\.venv\Scripts\python.exe ml\scripts\evaluate.py --model runs\train\waste_yolo26s_vn_adapt\weights\best.pt --data datasets\vn_field\data.yaml --split val --device 0 --out outputs\vn_adapt_val.json
```

Chọn epoch/augmentation bằng `VN-Field-val`. Sau đó so **cả** checkpoint SWiM3 và checkpoint adapted trên cùng tập `VN-Field-test-new`, đồng thời kiểm tra lại SWiM3-test để phát hiện quên kiến thức cũ. Nếu thích nghi miền làm giảm chất lượng SWiM3 quá mức, cân nhắc trộn một phần SWiM3-train vào train adaptation hoặc giữ checkpoint gốc; tuyệt đối không đưa SWiM3-test hoặc VN test vào train. Ngưỡng `--lr0` trong ví dụ là điểm khởi đầu cần chọn bằng validation, không phải giá trị đã được xác nhận.
