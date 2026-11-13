import { ArrowUpRight, Menu, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { siteContent } from '../content/siteContent';
import { useLanguage } from '../lib/language';

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { language, setLanguage, t } = useLanguage();
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll(); window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  const close = () => setOpen(false);
  return <header className={`topbar${scrolled ? ' scrolled' : ''}`}>
    <div className="wrap nav-inner">
      <div className="brand"><span className="hustword">SoICT</span><span className="brand-sep" aria-hidden="true"/><a href="#top" aria-label={`${siteContent.siteName} — về đầu trang`}><span className="wwlogo">{siteContent.siteName}</span><span className="brand-small">STUDENT PROJECT · HUST</span></a></div>
      <button className="hamb" aria-label={open ? t('Đóng menu','Close menu') : t('Mở menu','Open menu')} aria-expanded={open} aria-controls="navlinks" onClick={() => setOpen(!open)}>{open ? <X size={23}/> : <Menu size={23}/>}</button>
      <nav className={`navlinks${open ? ' open' : ''}`} id="navlinks" aria-label={t('Điều hướng chính','Main navigation')}>
        <a onClick={close} href="#story">{t('Câu chuyện','Our story')}</a><a onClick={close} href="#mission">{t('Mục tiêu','Purpose')}</a><a onClick={close} href="#studio">Scan Studio</a><a onClick={close} href="#library">{t('Tra cứu','Library')}</a><a onClick={close} href="#tech">{t('Công nghệ','Technology')}</a><a onClick={close} href="#team">{t('Về chúng tôi','Our team')}</a>
        <button className="language-toggle" onClick={() => setLanguage(language === 'vi' ? 'en' : 'vi')} aria-label={t('Chuyển sang tiếng Anh','Switch to Vietnamese')}>{language === 'vi' ? 'VI' : 'EN'} <span>{language === 'vi' ? 'EN' : 'VI'}</span></button>
        <a className="nav-cta" onClick={close} href="#studio">{t('Thử ngay','Try it')} <ArrowUpRight size={15}/></a>
      </nav>
    </div>
  </header>;
}
