export type TeamMember = {
  name: string;
  role: string;
  photo?: string;
  bio: string;
  links?: { label: string; href: string }[];
};

export const siteContent = {
  siteName: 'SOICTERRA',
  descriptor: 'AI-Powered Waste Detection & Classification',
  tagline: 'VISION FOR A CLEANER FUTURE',
  affiliation: 'Dự án sinh viên SoICT · Đại học Bách khoa Hà Nội (HUST)',
  independentNotice: 'Dự án học thuật độc lập, không phải nền tảng chính thức hoặc sản phẩm được Đại học Bách khoa Hà Nội chứng thực.',
  hero: {
    eyebrow: 'SOICTERRA · COMPUTER VISION · VIETNAM',
    description: 'Từ những món đồ bị bỏ đi mỗi ngày đến những lựa chọn có trách nhiệm hơn. SOICTERRA đưa thị giác máy tính vào một vấn đề gần gũi: nhận diện rác, hiểu đặc điểm từng nhóm và gợi ý cách xử lý phù hợp.',
    primaryAction: 'MỞ SCAN STUDIO',
    secondaryAction: 'CÂU CHUYỆN SOICTERRA',
  },
  story: {
    index: '00 / THE REASON WE STARTED',
    eyebrow: 'HANOI · STUDENT ENGINEERING PROJECT',
    title: 'MỖI VẬT THỂ ĐỀU CÓ MỘT HÀNH TRÌNH',
    heading: 'RÁC KHÔNG BIẾN MẤT. NÓ CHỈ RỜI KHỎI TẦM MẮT.',
    lead: 'Mỗi ngày, chúng ta bỏ đi những chai nhựa, tờ giấy, lon nước hay phần thức ăn còn lại. Một hành động chỉ mất vài giây, nhưng câu hỏi đằng sau nó không hề đơn giản: món đồ này thuộc nhóm rác nào, và nên được xử lý ra sao?',
    support: 'Giữa nhịp sống đô thị, phân loại rác tại nguồn thường bắt đầu từ một điều rất nhỏ: nhận biết đúng thứ đang cầm trên tay. Với sinh viên kỹ thuật, đó cũng là điểm khởi đầu cho một câu hỏi lớn hơn — liệu công nghệ thị giác máy tính có thể giúp lựa chọn ấy trở nên trực quan và dễ tiếp cận hơn?',
    quote: 'Từ câu hỏi đó, SOICTERRA được hình thành: một đồ án sinh viên đưa AI ra khỏi bài thực hành và đến gần những tình huống đời sống.',
  },
  mission: {
    kicker: '01 / OUR PURPOSE',
    title: 'KHÔNG CHỈ NHẬN DIỆN.',
    accent: 'CÒN ĐỂ HIỂU VÀ HÀNH ĐỘNG.',
    copy: 'SOICTERRA được phát triển trong khuôn khổ Đồ án 1 tại Trường Công nghệ Thông tin và Truyền thông, Đại học Bách khoa Hà Nội. Dự án kết hợp object detection, kỹ thuật dữ liệu và giao diện web để chuyển một tấm ảnh đời thường thành thông tin có thể sử dụng. Đây là nguyên mẫu học thuật của sinh viên, không thay thế hướng dẫn phân loại chính thức tại địa phương.',
    goals: [
      { title: 'NHÌN RÕ TỪNG VẬT THỂ', body: 'Phát hiện nhiều vật thể trong cùng ảnh, chỉ ra vị trí và nhóm vật liệu mà mô hình hiện hỗ trợ.' },
      { title: 'CHO PHÉP CON NGƯỜI KIỂM TRA', body: 'AI có thể mắc lỗi. Giao diện cho phép xem lại từng phát hiện, điều chỉnh nhãn và loại bỏ vật thể.' },
      { title: 'HƯỚNG ĐẾN HÀNH ĐỘNG THỰC TẾ', body: 'Kết quả nối với thư viện kiến thức để đưa ra gợi ý xử lý và cảnh báo, với giới hạn được trình bày rõ ràng.' },
    ],
  },
  technology: {
    kicker: '03 / ENGINEERING THAT MATTERS',
    title: 'CÔNG NGHỆ & NGHIÊN CỨU',
    description: 'Từ dữ liệu gán nhãn đến mô hình nhận diện, rồi biến dự đoán thành một công cụ người dùng có thể tương tác.',
    cards: [
      { number: '01 / DATA ENGINEERING', icon: '▱', title: 'BỘ DỮ LIỆU ĐA NGUỒN', body: 'Chuẩn hóa ảnh và bounding box từ nhiều bộ dữ liệu, kiểm tra nhãn và phân chia train / validation / test.' },
      { number: '02 / COMPUTER VISION', icon: '⌗', title: 'OBJECT DETECTION', body: 'Mô hình phát hiện vật thể trả về từng bounding box và lớp dự đoán theo checkpoint đang được cấu hình.' },
      { number: '03 / FULL-STACK SYSTEM', icon: '⌘', title: 'TỪ MÔ HÌNH ĐẾN SẢN PHẨM', body: 'FastAPI điều phối inference và dữ liệu phân loại; React hiển thị kết quả và cho phép kiểm tra lại từng vật thể.' },
    ],
    flow: [
      ['ẢNH ĐẦU VÀO', 'JPEG · PNG · WebP'], ['MÔ HÌNH ĐANG CẤU HÌNH', 'Detector từ API'], ['PHÁT HIỆN', 'Box · Class · Confidence'], ['HƯỚNG DẪN', 'Knowledge Base'],
    ],
    note: 'Số lớp và model version bên dưới lấy từ API hiện hành. Không hiển thị kết quả benchmark chưa được xác minh; ảnh demo luôn được đánh dấu minh họa.',
  },
  library: {
    kicker: '04 / WASTE INTELLIGENCE',
    title: 'HIỂU RÁC, XỬ LÝ ĐÚNG',
    description: 'Chọn một nhóm rác để khám phá hướng dẫn từ thư viện kiến thức. Tư vấn thực tế còn phụ thuộc quy định thu gom và điều kiện địa phương.',
  },
  team: {
    kicker: '05 / THE PEOPLE BEHIND SOICTERRA',
    title: 'ĐƯỢC XÂY DỰNG BỞI',
    accent: 'NHỮNG NGƯỜI ĐANG HỌC CÁCH TẠO RA KHÁC BIỆT.',
    description: 'Đằng sau giao diện và những khung nhận diện là hành trình của sinh viên SoICT: tìm kiếm dữ liệu, thử nghiệm mô hình, viết phần mềm, kiểm chứng sai số và liên tục cải thiện trải nghiệm. SOICTERRA là nơi kiến thức trên giảng đường được thử thách bằng một sản phẩm có thể sử dụng.',
    empty: 'Thông tin thành viên sẽ được cập nhật khi nhóm cung cấp tên, vai trò và nội dung đã xác minh.',
    members: [] as TeamMember[],
  },
  closing: {
    eyebrow: 'FROM THE CLASSROOM TO EVERYDAY LIFE',
    title: 'THỬ MỘT TẤM ẢNH. KHÁM PHÁ MỘT CÁCH NHÌN MỚI.',
    description: 'Hãy bắt đầu từ những vật thể rất đỗi quen thuộc. Một lần nhận diện có thể mở ra thêm một câu hỏi đúng về thói quen phân loại rác của chúng ta.',
    action: 'TRẢI NGHIỆM SCAN STUDIO',
  },
} as const;
