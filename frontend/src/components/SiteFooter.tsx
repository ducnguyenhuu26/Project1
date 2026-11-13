import { ArrowUpRight } from 'lucide-react';
import { siteContent } from '../content/siteContent';
import { PrivacyHistory } from './KnowledgeSections';
import type { HistoryEntry, Knowledge } from '../types';

export function SiteFooter({history,materials,onClear}:{history:HistoryEntry[];materials:Knowledge['materials'];onClear:()=>void}){
  return <footer className="footer" id="about"><div className="wrap"><div className="footer-inner"><div>
    <div className="eyebrow footer-eyebrow">STUDENT PROJECT · SOICT · HUST</div><h2>{siteContent.siteName} <span className="footer-slash">/</span></h2><p>{siteContent.descriptor}. Dự án học thuật về computer vision và sinh thái đô thị.</p><p className="site-disclaimer">{siteContent.independentNotice}</p>
    <div className="footer-links"><a href="#story">Câu chuyện</a><a href="#studio">Scan Studio</a><a href="#library">Tra cứu</a><a href="#team">Nhóm thực hiện</a><a href="#top">Đầu trang <ArrowUpRight size={13}/></a></div>
  </div><div className="footer-mark" aria-hidden="true">ST</div></div><PrivacyHistory history={history} materials={materials} onClear={onClear}/><div className="copy"><span>© 2026 SOICTERRA · {siteContent.tagline}</span><span>{siteContent.affiliation}</span></div></div></footer>;
}
