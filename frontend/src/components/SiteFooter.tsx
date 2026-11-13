import { ArrowUpRight, Facebook, Github, Mail, Linkedin, Youtube } from 'lucide-react';
import { siteContent, siteContentEn } from '../content/siteContent';
import { contactLinks } from '../content/contactLinks';
import { useLanguage } from '../lib/language';
import { PrivacyHistory } from './KnowledgeSections';
import type { HistoryEntry, Knowledge } from '../types';

export function SiteFooter({history,materials,onClear}:{history:HistoryEntry[];materials:Knowledge['materials'];onClear:()=>void}){
  const {language,t}=useLanguage(); const content=language==='en'?siteContentEn:siteContent;
  const contacts=[{key:'facebook',label:'Facebook',Icon:Facebook},{key:'github',label:'GitHub',Icon:Github},{key:'email',label:'Email',Icon:Mail},{key:'linkedin',label:'LinkedIn',Icon:Linkedin},{key:'youtube',label:'YouTube',Icon:Youtube}] as const;
  const contactButtons=contacts.map(({key,label,Icon})=>{const href=contactLinks[key];return href?<a className="contact-button" href={href} key={key} target={key==='email'?undefined:'_blank'} rel={key==='email'?undefined:'noreferrer'}><Icon size={16}/>{label}<ArrowUpRight size={12}/></a>:<span className="contact-button unconfigured" key={key} title={t('Thêm đường dẫn trong frontend/src/content/contactLinks.ts','Add a URL in frontend/src/content/contactLinks.ts')}><Icon size={16}/>{label}<span className="contact-add">+</span></span>;});
  return <footer className="footer" id="about"><div className="wrap"><div className="footer-inner"><div>
    <div className="eyebrow footer-eyebrow">STUDENT PROJECT · SOICT · HUST</div><h2>{content.siteName} <span className="footer-slash">/</span></h2><p>{content.descriptor}. {t('Thị giác máy tính đồng hành cùng phân loại rác trong đô thị Việt Nam.','Computer vision supporting waste sorting in Vietnamese cities.')}</p><p className="site-affiliation">{content.projectStatement}</p>
    <div className="footer-links"><a href="#story">{t('Câu chuyện','Our story')}</a><a href="#studio">Scan Studio</a><a href="#library">{t('Tra cứu','Library')}</a><a href="#team">{t('Nhóm thực hiện','Our team')}</a><a href="#top">{t('Đầu trang','Back to top')} <ArrowUpRight size={13}/></a></div>
    <div className="footer-contact"><b>{t('KẾT NỐI VỚI CHÚNG TÔI','CONNECT WITH US')}</b><div>{contactButtons}</div><small>{t('Thêm liên kết chính thức để kích hoạt từng nút.','Add your official links to activate each button.')}</small></div>
  </div><div className="footer-mark" aria-hidden="true">ST</div></div><PrivacyHistory history={history} materials={materials} onClear={onClear}/><div className="copy"><span>© 2026 SOICTERRA · {content.tagline}</span><span>{content.affiliation}</span></div></div></footer>;
}
