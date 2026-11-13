import { ArrowUpRight, Recycle, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { useMemo, useState, type CSSProperties } from 'react';
import type { Knowledge } from '../types';
const palette: Record<string,string> = { plastic:'#d0835f', paper:'#afa36b', metal:'#6e9ca5', glass:'#76a7b2', organic:'#82996f', battery:'#aa6862', e_waste:'#827b9d' };

export function KnowledgeSections({ knowledge, supportedIds }: { knowledge: Knowledge | null; supportedIds: string[] }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all'|'supported'|'lookup'>('all');
  const materials = knowledge?.materials ?? [];
  const matches = useMemo(() => materials.filter(m => {
    const textMatch = [m.name,m.id,...m.examples,...(m.synonyms ?? [])].join(' ').toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi'));
    const category = knowledge?.categories.find(c => c.material_id === m.id || c.id === m.id);
    return textMatch && (filter === 'all' || (filter === 'supported' ? supportedIds.includes(m.id) && category?.detection_supported !== false : !supportedIds.includes(m.id)));
  }), [materials, query, filter, knowledge, supportedIds]);
  return <>
    <section className="library-section" id="library" aria-labelledby="library-title"><div className="section-heading"><div><span className="section-index">02 / WASTE INTELLIGENCE</span><h2 id="library-title">Biết vật liệu.<br/><em>Chọn cách phù hợp.</em></h2></div><p>Kiến thức tham khảo theo từng nhóm vật liệu. Gợi ý nhận diện phụ thuộc checkpoint đang chạy; các mục khác vẫn có thể tra cứu thủ công.</p></div>
      <div className="library-tools"><div className="library-search"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm chai nhựa, pin, giấy…" aria-label="Tìm vật liệu"/></div><div className="library-filters" aria-label="Lọc thư viện">{(['all','supported','lookup'] as const).map((key,i)=><button className={filter===key?'active':''} key={key} onClick={()=>setFilter(key)}>{['Tất cả','Mô hình hỗ trợ','Tra cứu tay'][i]}</button>)}</div></div>
      {!knowledge && <p className="library-status" role="status">Đang kết nối thư viện kiến thức…</p>}
      <div className="library-grid">{matches.map((m,index)=>{const supported=supportedIds.includes(m.id); return <details className="material-card" key={m.id}><summary><div className="material-symbol" style={{'--material-color':palette[m.id]??'#8a977e'} as CSSProperties}><span>{String(index+1).padStart(2,'0')}</span><Recycle size={25}/></div><div className="material-card-title"><small>{supported?'CHECKPOINT HIỆN HÀNH':'THƯ VIỆN THỦ CÔNG'}</small><strong>{m.name}</strong><span>{m.examples.slice(0,2).join(' · ')}</span></div><ArrowUpRight size={17} className="material-arrow"/></summary><div className="material-detail"><p>{m.description}</p><b>NÊN LÀM</b><p>{m.do.join(' ')}</p><b>TRÁNH / LƯU Ý</b><p>{m.avoid.join(' ')} {m.caution}</p><div className="material-tip"><ShieldCheck size={15}/>{m.vn_tip}</div></div></details>;})}</div>
      {knowledge && !matches.length && <p className="library-status">Không tìm thấy vật liệu phù hợp.</p>}
    </section>
    <section className="research-section" id="story"><div className="research-index"><span className="section-index">03 / APPLIED COMPUTER VISION</span><Sparkles size={20}/></div><div className="research-main"><h2>Thị giác máy tính.<br/><em>Gắn với đời sống.</em></h2><p>WasteWise VN là dự án sinh viên về nhận diện vật thể và phân loại chất thải. Ảnh được gửi tới FastAPI để xử lý bằng cấu hình mô hình đang có; nhãn vật liệu giúp mở ra hướng dẫn rõ ràng hơn.</p><div className="research-facts"><div><span>01</span><b>OBJECT DETECTION</b><small>Phát hiện nhiều vật thể trong cùng khung hình</small></div><div><span>02</span><b>HUMAN IN THE LOOP</b><small>Hiệu chỉnh nhãn và loại bỏ phát hiện từng vật</small></div><div><span>03</span><b>GROUNDED GUIDANCE</b><small>Tra cứu theo thư viện kiến thức của dự án</small></div></div><p className="research-note">Số lớp thực sự được hỗ trợ lấy trực tiếp từ API. Kết quả demo luôn được đánh dấu là minh họa; hệ thống không xác định độ sạch, thành phần hóa học hay quy định thu gom tại địa phương.</p></div></section>
  </>;
}

export function PrivacyHistory({ history, materials, onClear }: { history: { id?:string; when:string; detected?:string[]; final?:string[]; corrected?:boolean }[]; materials: Knowledge['materials']; onClear:()=>void }) {
  return <section className="history-section" id="privacy"><div className="history-intro"><span className="section-index">04 / DATA & HISTORY</span><h2>Ảnh để phân tích.<br/><em>Lịch sử ở trình duyệt.</em></h2><p>Ảnh được gửi tới máy chủ để phân tích. Lịch sử chỉ lưu thời gian và nhãn tóm tắt trong localStorage trên trình duyệt này; bạn có thể xóa bất cứ lúc nào.</p></div><div className="history-list"><div className="history-list-head"><b>LẦN QUÉT GẦN ĐÂY</b><button onClick={onClear}>Xóa lịch sử</button></div>{history.length?history.map((entry,i)=><div className="history-entry" key={entry.id??i}><time>{entry.when}</time><span>{entry.corrected?'ĐÃ HIỆU CHỈNH · ':''}{(entry.final??entry.detected??[]).map(id=>materials.find(m=>m.id===id)?.name??id).join(' · ')||'Chưa xác định'}</span></div>):<p>Chưa có lần quét nào.</p>}</div></section>;
}
