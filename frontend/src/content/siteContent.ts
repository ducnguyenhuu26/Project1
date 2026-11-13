export type TeamMember = {
  name: string;
  role?: string;
  photo?: string;
  bio?: string;
  links?: { label: string; href: string }[];
};

export const siteContent = {
  siteName: 'SOICTERRA',
  descriptor: 'AI-Powered Waste Detection & Classification',
  tagline: 'VISION FOR A CLEANER FUTURE',
  affiliation: 'Đồ án 1 của sinh viên SoICT · Đại học Bách khoa Hà Nội (HUST)',
  projectStatement: 'Đồ án 1 do sinh viên Trường CNTT&TT, Đại học Bách khoa Hà Nội phát triển.',
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
    lead: 'Chai nhựa, tờ giấy, lon nước hay phần thức ăn thừa — mỗi ngày, chúng ta bỏ đi những vật dụng quen thuộc chỉ trong vài giây. Nhưng để phân loại đúng, cần trả lời hai câu hỏi: món đồ này thuộc nhóm rác nào, và được xử lý ra sao?',
    support: 'Giữa nhịp sống đô thị, phân loại rác tại nguồn bắt đầu từ một điều rất nhỏ: nhận biết đúng thứ đang cầm trên tay. SOICTERRA ứng dụng thị giác máy tính để biến lựa chọn ấy thành trải nghiệm trực quan, dễ tiếp cận.',
    quote: 'Từ câu hỏi tưởng chừng như đơn giản đó, dự án được hình thành với mong muốn biến những kiến thức được học trên giảng đường trở thành một dự án thực tế',
  },
  mission: {
    kicker: '01 / OUR PURPOSE',
    title: 'Không chỉ nhận diện',
    accent: 'Mà còn để hiểu và hành động',
    copy: 'SOICTERRA là Đồ án 1 của sinh viên Trường Công nghệ Thông tin và Truyền thông, Đại học Bách khoa Hà Nội. Hệ thống kết hợp object detection, kỹ thuật dữ liệu và giao diện web để biến ảnh rác thải thành kết quả nhận diện, nhãn vật liệu và hướng dẫn xử lý.',
    goals: [
      { title: 'NHÌN RÕ TỪNG VẬT THỂ', body: 'Phát hiện nhiều vật thể trong cùng ảnh, hiển thị vị trí và các lớp vật liệu được API hỗ trợ.' },
      { title: 'CHỦ ĐỘNG KIỂM SOÁT KẾT QUẢ', body: 'Xem lại từng phát hiện, điều chỉnh nhãn và loại bỏ vật thể ngay trong Scan Studio.' },
      { title: 'KẾT NỐI HƯỚNG DẪN HÀNH ĐỘNG', body: 'Tra cứu cách xử lý và lưu ý phù hợp với từng nhóm vật liệu ngay sau khi nhận diện.' },
    ],
  },
  technology: {
    kicker: '03 / ENGINEERING THAT MATTERS',
    title: 'CÔNG NGHỆ & NGHIÊN CỨU',
    description: 'Từ dữ liệu gán nhãn đến mô hình nhận diện, rồi biến dự đoán thành một công cụ người dùng có thể tương tác.',
    cards: [
      { number: '01 / DATA ENGINEERING', icon: '▱', title: 'BỘ DỮ LIỆU ĐA NGUỒN', body: 'Chuẩn hóa ảnh và bounding box từ nhiều bộ dữ liệu, kiểm tra nhãn và phân chia train / validation / test.' },
      { number: '02 / COMPUTER VISION', icon: '⌗', title: 'OBJECT DETECTION', body: 'Mô hình phát hiện vật thể xác định vị trí, nhãn lớp và độ tin cậy cho từng đối tượng trong ảnh.' },
      { number: '03 / FULL-STACK SYSTEM', icon: '⌘', title: 'TỪ MÔ HÌNH ĐẾN SẢN PHẨM', body: 'FastAPI điều phối inference và dữ liệu phân loại; React hiển thị kết quả và cho phép kiểm tra lại từng vật thể.' },
    ],
    flow: [
      ['ẢNH ĐẦU VÀO', 'JPEG · PNG · WebP'], ['MÔ HÌNH ĐANG CẤU HÌNH', 'Detector từ API'], ['PHÁT HIỆN', 'Box · Class · Confidence'], ['HƯỚNG DẪN', 'Knowledge Base'],
    ],
    note: 'Thông tin model, taxonomy và lớp vật liệu được đồng bộ trực tiếp từ API. Ảnh mẫu trình diễn trọn vẹn quy trình Scan Studio.',
  },
  library: {
    kicker: '04 / WASTE INTELLIGENCE',
    title: 'HIỂU RÁC, XỬ LÝ ĐÚNG',
    description: 'Chọn một nhóm vật liệu để khám phá cách phân loại, hướng dẫn xử lý và lưu ý an toàn từ thư viện SOICTERRA.',
  },
  team: {
    kicker: '05 / THE PEOPLE BEHIND SOICTERRA',
    title: 'Cùng kiến tạo',
    accent: 'Tương lai xanh hơn',
    description: 'Đằng sau giao diện và những khung nhận diện là hành trình học hỏi và làm việc không ngừng của sinh viên SoICT: tìm kiếm dữ liệu, thử nghiệm mô hình, viết phần mềm, kiểm chứng sai số và liên tục cải thiện trải nghiệm chất lượng người dùng. SOICTERRA là nơi kiến thức trên giảng đường được thử thách bằng một sản phẩm có thể sử dụng được.',
    empty: 'Hồ sơ đội ngũ SOICTERRA sẽ xuất hiện tại đây.',
    members: [{ name: 'Nguyễn Hữu Đức'}, { name: 'Nguyễn Sỹ Thành'}, {name: 'Nguyễn Hải Yến Nhi'}] as TeamMember[],
  },
  closing: {
    eyebrow: 'FROM THE CLASSROOM TO EVERYDAY LIFE',
    title: 'THỬ MỘT TẤM ẢNH. KHÁM PHÁ MỘT CÁCH NHÌN MỚI.',
    description: 'Bắt đầu từ những vật thể quen thuộc. Cùng khám phá cách dự án biến mỗi lần phân loại thành hành động có ý thức.',
    action: 'TRẢI NGHIỆM SCAN STUDIO',
  },
} as const;

// English editorial copy mirrors the Vietnamese page structure so either language
// can be expanded without changing the layout or API integration.
export const siteContentEn = {
  ...siteContent,
  descriptor: 'AI-Powered Waste Detection & Classification',
  tagline: 'VISION FOR A CLEANER FUTURE',
  affiliation: 'SoICT student project · Hanoi University of Science and Technology (HUST)',
  projectStatement: 'Project 1 developed by students of the School of Information and Communication Technology, HUST.',
  hero: { eyebrow: 'SOICTERRA · COMPUTER VISION · VIETNAM', description: 'From everyday discarded items to more responsible choices. SOICTERRA brings computer vision to a familiar challenge: recognizing waste, understanding each material group, and suggesting suitable next steps.', primaryAction: 'OPEN SCAN STUDIO', secondaryAction: 'OUR STORY' },
  story: { index: '00 / THE REASON WE STARTED', eyebrow: 'HANOI · STUDENT ENGINEERING PROJECT', title: 'EVERY OBJECT HAS A JOURNEY', heading: 'WASTE DOES NOT DISAPPEAR. IT JUST LEAVES OUR SIGHT.', lead: 'Plastic bottles, paper, drink cans, or leftover food — every day, familiar items are discarded in seconds. Sorting them well starts with two questions: what waste group does this item belong to, and how should it be handled?', support: 'In the rhythm of urban life, sorting waste at the source begins with one small step: recognizing what is in our hands. SOICTERRA applies computer vision to make that choice visual and accessible.', quote: 'That simple question inspired us to turn what we learned in class into a practical project.' },
  mission: { kicker: '01 / OUR PURPOSE', title: 'More than recognition', accent: 'Understand, then take action', copy: 'SOICTERRA is Project 1 by students of the School of Information and Communication Technology at Hanoi University of Science and Technology. The system combines object detection, data engineering, and a web interface to turn waste images into detections, material labels, and handling guidance.', goals: [{ title: 'SEE EACH OBJECT CLEARLY', body: 'Detect multiple objects in one image, show their locations, and list material classes supported by the API.' }, { title: 'STAY IN CONTROL OF RESULTS', body: 'Review each detection, correct its label, or remove it directly in Scan Studio.' }, { title: 'TURN GUIDANCE INTO ACTION', body: 'Explore handling guidance and practical notes for each material group after detection.' }] },
  technology: { kicker: '03 / ENGINEERING THAT MATTERS', title: 'TECHNOLOGY & RESEARCH', description: 'From labelled data to object detection, then turning predictions into an interactive tool.', cards: [{ number: '01 / DATA ENGINEERING', icon: '▱', title: 'MULTI-SOURCE DATASET', body: 'Normalize images and bounding boxes from multiple datasets, validate labels, and create train / validation / test splits.' }, { number: '02 / COMPUTER VISION', icon: '⌗', title: 'OBJECT DETECTION', body: 'The detector predicts each object’s location, class label, and confidence score.' }, { number: '03 / FULL-STACK SYSTEM', icon: '⌘', title: 'FROM MODEL TO PRODUCT', body: 'FastAPI serves inference and sorting data; React presents results and lets users review each object.' }], flow: [['INPUT IMAGE', 'JPEG · PNG · WebP'], ['CONFIGURED MODEL', 'Detector from API'], ['DETECTIONS', 'Box · Class · Confidence'], ['GUIDANCE', 'Knowledge Base']], note: 'Model details, taxonomy, and material classes are synchronized directly from the API. The sample image demonstrates the complete Scan Studio flow.' },
  library: { kicker: '04 / WASTE INTELLIGENCE', title: 'UNDERSTAND WASTE. SORT IT WELL.', description: 'Choose a material group to explore sorting, handling guidance, and safety notes from the SOICTERRA library.' },
  team: { kicker: '05 / THE PEOPLE BEHIND SOICTERRA', title: 'Building together', accent: 'A greener future', description: 'Behind the interface and detection boxes is the SoICT student team’s ongoing work: sourcing data, testing models, building software, checking errors, and improving the user experience. SOICTERRA puts classroom knowledge to the test in a usable product.', empty: 'SOICTERRA team profiles will appear here.', members: siteContent.team.members },
  closing: { eyebrow: 'FROM THE CLASSROOM TO EVERYDAY LIFE', title: 'TRY AN IMAGE. DISCOVER A NEW PERSPECTIVE.', description: 'Start with familiar objects. Explore how this project can make each sorting decision more informed.', action: 'TRY SCAN STUDIO' },
} as const;
