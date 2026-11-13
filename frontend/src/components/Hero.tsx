import { ArrowDown, ArrowUpRight, ScanLine } from 'lucide-react';

export function Hero({ onSample }: { onSample: () => void }) {
  return <section className="hero" id="top" aria-labelledby="hero-title">
    <div className="hero-copy">
      <div className="eyebrow"><i/> BÁCH KHOA FUTURE LAB <span>·</span> PROJECT 01</div>
      <h1 id="hero-title">NHÌN THẤY RÁC.<br/><em>Hiểu cách xử lý.</em></h1>
      <p className="hero-lede">Một tấm ảnh mở ra nhiều lựa chọn tốt hơn. Nhận diện vật thể, xem gợi ý phân loại và tìm hiểu cách xử lý an toàn.</p>
      <div className="hero-actions"><a className="button button-bright" href="#studio"><ScanLine size={17}/> Mở Scan Studio <ArrowUpRight size={16}/></a><button className="button button-quiet" onClick={onSample}>Khám phá ảnh minh họa <ArrowUpRight size={15}/></button></div>
      <div className="hero-caption"><span>01 — 03</span><span>NHẬN DIỆN · HIỂU VẬT LIỆU · XỬ LÝ CÓ Ý THỨC</span></div>
    </div>
    <div className="hero-visual" role="img" aria-label="Minh họa nghệ thuật về phố Hà Nội, vòng tuần hoàn tái chế và khung quét thị giác máy tính">
      <div className="visual-meta"><span>HANOI / 21°01′N</span><span>FIELD NOTE 01</span></div>
      <img src="/urban-ecology.svg" alt=""/>
      <div className="scan-reticle reticle-one"/><div className="scan-reticle reticle-two"/>
      <div className="visual-label"><span className="live-dot"/> URBAN ECOLOGY <b>01 / 04</b></div>
      <div className="visual-index">WW—01</div>
    </div>
    <a className="scroll-cue" href="#studio"><span>CUỘN ĐỂ KHÁM PHÁ</span><ArrowDown size={14}/></a>
  </section>;
}
