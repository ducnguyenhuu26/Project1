import { useState } from 'react';
import { ArrowRight, RotateCcw, ScanLine } from 'lucide-react';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';

export function Hero({ onSample, supportedCount }: { onSample: () => void; supportedCount: number }) {
  const { language, t } = useLanguage(); const content = language === 'en' ? siteContentEn : siteContent;
  const [scanRun,setScanRun]=useState(0);
  return <section className="hero" id="top" aria-labelledby="hero-title">
    <div className="hero-photo" role="img" aria-label={t('Ảnh minh họa chai nhựa, giấy và lon kim loại','Illustration of a plastic bottle, paper, and a metal can')}/>
    <div className="hero-vision" aria-hidden="true" key={scanRun}>
      <span className="hero-vision-sweep"/>
      <span className="hero-detection hero-detection-plastic"><b>PLASTIC <i>01</i></b></span>
      <span className="hero-detection hero-detection-paper"><b>PAPER <i>02</i></b></span>
      <span className="hero-detection hero-detection-metal"><b>METAL <i>03</i></b></span>
      <span className="hero-vision-complete">SCAN COMPLETE <b>03 / 03</b></span>
    </div>
    <div className="hero-art-label"><span>SOICTERRA / VISUAL STORY</span><b>{t('MINH HỌA NHẬN DIỆN','ILLUSTRATIVE SCAN')}</b></div>
    <div className="hero-stripe" aria-hidden="true"/>
    <div className="wrap hero-inner"><div className="hero-content">
      <div className="eyebrow intro1">{content.hero.eyebrow}<i aria-hidden="true"/></div>
      <h1 className="intro2" id="hero-title">{language==='en'?<><span>SEE THE WASTE </span><span><em>UNDERSTAND THE NEXT STEP</em></span></>:<><span>NHÌN THẤY RÁC </span><span><em>HIỂU CÁCH XỬ LÝ</em></span></>}</h1>
      <p className="hero-desc intro3">{content.hero.description}</p>
      <div className="actions intro3"><a className="btn btn-primary" href="#studio"><ScanLine size={16}/>&nbsp; {content.hero.primaryAction} <span>↗</span></a><a className="btn" href="#story">{content.hero.secondaryAction} ↗</a></div>
      <div className="hero-quick-actions"><button className="hero-demo-link" onClick={onSample}><ArrowRight size={14}/> {t('Chạy ảnh mẫu qua Scan Studio','Run sample in Scan Studio')}</button><button className="hero-replay" onClick={()=>setScanRun(value=>value+1)} aria-label={t('Phát lại hiệu ứng quét minh họa','Replay the illustrative scan')}><RotateCcw size={13}/>{t('Xem lại màn quét','Replay scan')}</button></div>
      <div className="hero-meta intro3"><div><strong>CV</strong> Object detection</div><div><strong>{supportedCount.toString().padStart(2,'0')}</strong> {t('Lớp API hỗ trợ','API classes supported')}</div><div><strong>HUST</strong> Project 01</div></div>
    </div></div>
  </section>;
}
