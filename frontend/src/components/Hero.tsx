import { ArrowRight, ScanLine } from 'lucide-react';
import { siteContent } from '../content/siteContent';

export function Hero({ onSample, supportedCount }: { onSample: () => void; supportedCount: number }) {
  return <section className="hero" id="top" aria-labelledby="hero-title">
    <div className="hero-photo" role="img" aria-label="Ảnh minh họa ba vật thể với khung thị giác máy tính; artwork demo, không phải kết quả suy luận"/>
    <div className="hero-art-label"><span>DEMO VISUAL</span><b>ARTWORK · NOT MODEL OUTPUT</b></div>
    <div className="hero-stripe" aria-hidden="true"/>
    <div className="wrap hero-inner"><div className="hero-content">
      <div className="eyebrow intro1">{siteContent.hero.eyebrow}<i aria-hidden="true"/></div>
      <h1 className="intro2" id="hero-title"><span>NHÌN THẤY RÁC.</span><span><em>HIỂU CÁCH XỬ LÝ.</em></span></h1>
      <p className="hero-desc intro3">{siteContent.hero.description}</p>
      <div className="actions intro3"><a className="btn btn-primary" href="#studio"><ScanLine size={16}/>&nbsp; {siteContent.hero.primaryAction} <span>↗</span></a><a className="btn" href="#story">{siteContent.hero.secondaryAction} ↗</a></div>
      <button className="hero-demo-link" onClick={onSample}><ArrowRight size={14}/> Thử ảnh minh họa qua API thật (nếu demo mode)</button>
      <div className="hero-meta intro3"><div><strong>CV</strong> Object detection</div><div><strong>{supportedCount.toString().padStart(2,'0')}</strong> Lớp API hỗ trợ</div><div><strong>HUST</strong> Project 01</div></div>
    </div></div>
  </section>;
}
