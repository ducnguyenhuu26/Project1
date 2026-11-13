import { ArrowRight, ScanLine } from 'lucide-react';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';

export function Hero({ onSample, supportedCount }: { onSample: () => void; supportedCount: number }) {
  const { language, t } = useLanguage(); const content = language === 'en' ? siteContentEn : siteContent;
  return <section className="hero" id="top" aria-labelledby="hero-title">
    <div className="hero-photo" role="img" aria-label="Artwork SOICTERRA: ba nhóm rác trong khung thị giác máy tính, hình minh họa giao diện"/>
    <div className="hero-art-label"><span>SOICTERRA / VISUAL STORY</span><b>ARTWORK </b></div>
    <div className="hero-stripe" aria-hidden="true"/>
    <div className="wrap hero-inner"><div className="hero-content">
      <div className="eyebrow intro1">{content.hero.eyebrow}<i aria-hidden="true"/></div>
      <h1 className="intro2" id="hero-title">{language==='en'?<><span>SEE THE WASTE </span><span><em>UNDERSTAND THE NEXT STEP</em></span></>:<><span>NHÌN THẤY RÁC </span><span><em>HIỂU CÁCH XỬ LÝ</em></span></>}</h1>
      <p className="hero-desc intro3">{content.hero.description}</p>
      <div className="actions intro3"><a className="btn btn-primary" href="#studio"><ScanLine size={16}/>&nbsp; {content.hero.primaryAction} <span>↗</span></a><a className="btn" href="#story">{content.hero.secondaryAction} ↗</a></div>
      <button className="hero-demo-link" onClick={onSample}><ArrowRight size={14}/> {t('Chạy ảnh mẫu qua Scan Studio','Run sample in Scan Studio')}</button>
      <div className="hero-meta intro3"><div><strong>CV</strong> Object detection</div><div><strong>{supportedCount.toString().padStart(2,'0')}</strong> {t('Lớp API hỗ trợ','API classes supported')}</div><div><strong>HUST</strong> Project 01</div></div>
    </div></div>
  </section>;
}
