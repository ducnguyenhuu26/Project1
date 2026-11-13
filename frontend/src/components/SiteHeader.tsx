import { ArrowUpRight, Menu, X } from 'lucide-react';
import { useState } from 'react';

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return <header className="site-header">
    <a className="wordmark" href="#top" aria-label="WasteWise VN — về đầu trang"><span className="wordmark-symbol">W<span>·</span></span><span><b>WASTEWISE</b><small>HÀ NỘI · FUTURE LAB</small></span></a>
    <button className="menu-toggle" aria-label={open ? 'Đóng menu' : 'Mở menu'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X/> : <Menu/>}</button>
    <nav className={open ? 'site-nav is-open' : 'site-nav'} aria-label="Điều hướng chính">
      <a onClick={close} href="#studio">Scan Studio</a><a onClick={close} href="#library">Tra cứu</a><a onClick={close} href="#story">Công nghệ</a>
      <a className="nav-cta" onClick={close} href="#studio">Bắt đầu <ArrowUpRight size={15}/></a>
    </nav>
  </header>;
}
