import { ArrowUpRight, Menu, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { siteContent } from '../content/siteContent';

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll(); window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  const close = () => setOpen(false);
  return <header className={`topbar${scrolled ? ' scrolled' : ''}`}>
    <div className="wrap nav-inner">
      <div className="brand"><span className="hustword">SoICT</span><span className="brand-sep" aria-hidden="true"/><a href="#top" aria-label={`${siteContent.siteName} — về đầu trang`}><span className="wwlogo">{siteContent.siteName}</span><span className="brand-small">STUDENT PROJECT · HUST</span></a></div>
      <button className="hamb" aria-label={open ? 'Đóng menu' : 'Mở menu'} aria-expanded={open} aria-controls="navlinks" onClick={() => setOpen(!open)}>{open ? <X size={23}/> : <Menu size={23}/>}</button>
      <nav className={`navlinks${open ? ' open' : ''}`} id="navlinks" aria-label="Điều hướng chính">
        <a onClick={close} href="#story">Câu chuyện</a><a onClick={close} href="#mission">Mục tiêu</a><a onClick={close} href="#studio">Scan Studio</a><a onClick={close} href="#library">Tra cứu</a><a onClick={close} href="#tech">Công nghệ</a><a onClick={close} href="#team">Nhóm thực hiện</a>
        <a className="nav-cta" onClick={close} href="#studio">Bắt đầu <ArrowUpRight size={15}/></a>
      </nav>
    </div>
  </header>;
}
