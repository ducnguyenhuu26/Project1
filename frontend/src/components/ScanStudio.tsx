import { useRef, useState, type DragEvent } from 'react';
import { ArrowRight, Check, CircleAlert, ImagePlus, LoaderCircle, RotateCcw, ScanLine, ShieldCheck, Sparkles, Trash2, Upload } from 'lucide-react';
import type { Detection, Material, Scan } from '../types';

const colors: Record<string, string> = { plastic: '#e39168', paper: '#d5bf76', metal: '#83afbb', glass: '#86bdcc', organic: '#9abe8e', battery: '#e58b82', e_waste: '#afa6d0' };
type Props = {
  file: File | null; preview: string; scan: Scan | null; materials: Material[]; supportedIds: string[];
  busy: boolean; error: string; onChoose: (file: File) => void; onAnalyze: () => void;
  onCorrect: (detection: Detection, id: string) => void; onExclude: (id: string) => void;
  onSelect: (id: string) => void; selected: string | null; onManual: (id: string) => void;
  active: string[]; manual: string[]; corrections: Record<string, string>; excluded: string[];
};

export function ScanStudio(p: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [dragging, setDragging] = useState(false);
  const material = (id: string) => p.materials.find(item => item.id === id);
  function drop(e: DragEvent) { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) p.onChoose(e.dataTransfer.files[0]); }
  return <section className="studio-section" id="studio" aria-labelledby="studio-title">
    <div className="section-heading"><div><span className="section-index">01 / THE SCAN STUDIO</span><h2 id="studio-title">Mọi món đồ<br/><em>có một câu chuyện.</em></h2></div><p>Chọn một bức ảnh để bắt đầu. Xem từng phát hiện, hiệu chỉnh nhãn và đọc hướng dẫn xử lý tương ứng.</p></div>
    <div className="studio-shell">
      <div className="studio-topline"><span><i className="live-dot"/> WASTE OBJECT ANALYSIS</span><span>JPEG · PNG · WEBP <b>/</b> MAX 10 MB</span></div>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={e => { if (e.target.files?.[0]) p.onChoose(e.target.files[0]); e.currentTarget.value = ''; }}/>
      <div className="studio-grid">
        <div className="scan-canvas">
          {!p.preview ? <button className={`upload-zone ${dragging ? 'is-dragging' : ''}`} onClick={() => input.current?.click()} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
            <span className="upload-corner corner-tl"/><span className="upload-corner corner-br"/><span className="upload-icon"><ImagePlus size={25}/></span>
            <strong>Thả ảnh vào không gian quét</strong><span>hoặc chọn ảnh từ thiết bị</span><span className="upload-choose"><Upload size={15}/> Chọn tệp ảnh</span><small>Chỉ nhận JPEG, PNG, WebP · ảnh tối đa 10 MB</small>
          </button> : <>
            <div className="image-frame"><img src={p.preview} alt={`Ảnh cần phân loại: ${p.file?.name ?? 'ảnh đã chọn'}`}/>
              {p.scan && showBoxes && <svg className="box-overlay" viewBox={`0 0 ${p.scan.image_width} ${p.scan.image_height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`Khung bao quanh ${p.scan.detections.filter(d => !p.excluded.includes(d.id)).length} vật thể`}>
                {p.scan!.detections.filter(d => !p.excluded.includes(d.id)).map((d, i) => { const id = p.corrections[d.id] ?? d.category_id ?? ''; const [x1,y1,x2,y2] = d.bbox_xyxy; return <g key={d.id} className="box-group" onClick={() => p.onSelect(id)} tabIndex={0} role="button" aria-label={`${material(id)?.name ?? d.label}, vật thể ${i + 1}`} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') p.onSelect(id); }}>
                  <rect x={x1} y={y1} width={x2-x1} height={y2-y1} fill="none" stroke={colors[id] ?? '#e39168'} strokeWidth={Math.max(2, p.scan!.image_width / 480)}/>
                  <text x={x1 + 5} y={Math.max(19, y1 - 6)} fill={colors[id] ?? '#e39168'} fontWeight="700" fontSize={Math.max(15, p.scan!.image_width / 48)}>{material(id)?.name ?? d.label}{d.confidence == null ? '' : ` ${Math.round(d.confidence * 100)}%`}</text>
                </g>; })}
              </svg>}
            </div>
            <div className="image-actions"><span><Check size={14}/> {p.file?.name} · {((p.file?.size ?? 0) / 1024 / 1024).toFixed(2)} MB</span><div><button onClick={() => input.current?.click()}><RotateCcw size={14}/> Đổi ảnh</button>{p.scan && <button onClick={() => setShowBoxes(v => !v)}>{showBoxes ? 'Ẩn khung' : 'Hiện khung'}</button>}</div></div>
          </>}
          {p.error && <div className="error-message" role="alert"><CircleAlert size={17}/><span>{p.error}</span></div>}
          <button className="analyze-button" disabled={!p.file || p.busy} onClick={p.onAnalyze}>{p.busy ? <><LoaderCircle className="spinner" size={17}/> Đang phân tích ảnh…</> : <><ScanLine size={17}/> Phân tích ảnh <ArrowRight size={16}/></>}</button>
          <p className="scan-footnote"><ShieldCheck size={14}/> Ảnh được gửi tới API để phân tích; lịch sử chỉ lưu nhãn trong trình duyệt.</p>
        </div>
        <div className="results-column">
          <div className="results-heading"><span>02 / KẾT QUẢ PHÂN TÍCH</span>{p.scan && <span>{p.scan.image_width} × {p.scan.image_height} PX</span>}</div>
          {!p.scan ? <div className="result-placeholder"><div className="placeholder-orbit"><ScanLine size={24}/></div><strong>Không gian kết quả</strong><p>Ảnh phân tích và hướng dẫn sẽ xuất hiện ở đây.</p><span>ĐANG CHỜ HÌNH ẢNH</span></div> : <div className="results-content">
            <div className={`mode-banner ${p.scan.mode === 'demo' ? 'is-demo' : ''}`}><span className="mode-led"/><span>{p.scan.mode === 'demo' ? 'CHẾ ĐỘ MINH HỌA · KHÔNG PHẢI KẾT QUẢ AI' : 'KẾT QUẢ TỪ MÔ HÌNH AI'}</span><small>{p.scan.mode === 'demo' ? 'DEMO' : 'REAL'}</small></div>
            <div className="model-metadata"><span>MODEL <b>{p.scan.model_version ?? (p.scan.mode === 'demo' ? 'BẢN MẪU' : 'KHÔNG CÓ')}</b></span><span>TAXONOMY <b>{p.scan.taxonomy_version}</b></span></div>
            {p.scan.warnings.map((warning, i) => <p className="result-warning" key={i}><CircleAlert size={15}/>{warning}</p>)}
            {p.scan.mode === 'real' && p.scan.detections.length === 0 && <p className="result-warning"><CircleAlert size={15}/>Không có phát hiện trong các lớp mô hình hiện hỗ trợ. Ảnh có thể chứa loại vật liệu khác; hãy tra cứu hoặc chọn nhãn thủ công.</p>}
            <div className="result-subhead"><strong>Vật thể trong ảnh</strong><span>{p.scan.detections.filter(d => !p.excluded.includes(d.id)).length} PHÁT HIỆN</span></div>
            <div className="detection-list">{p.scan.detections.filter(d => !p.excluded.includes(d.id)).map((d, i) => { const id = p.corrections[d.id] ?? d.category_id ?? ''; return <article className={`detection-card ${p.selected === id ? 'is-selected' : ''}`} key={d.id}>
              <button className="detection-select" onClick={() => p.onSelect(id)}><span className="detection-number">{String(i + 1).padStart(2, '0')}</span><span className="detection-material"><b>{material(id)?.name ?? d.label}</b><small>{p.corrections[d.id] ? 'NHÃN ĐÃ HIỆU CHỈNH' : d.origin === 'illustration' ? 'VÍ DỤ MINH HỌA' : d.origin === 'ai' ? 'MÔ HÌNH PHÁT HIỆN' : 'CHƯA XÁC ĐỊNH'}</small></span><span className="confidence">{d.confidence == null ? '—' : `${Math.round(d.confidence * 100)}%`}</span></button>
              <div className="detection-controls"><label className="sr-only" htmlFor={`correct-${d.id}`}>Sửa nhãn cho vật thể {i + 1}</label><select id={`correct-${d.id}`} value={id} onChange={e => p.onCorrect(d, e.target.value)}><option value="">Chưa xác định</option>{p.materials.map(m => <option key={m.id} value={m.id}>{m.name}{!p.supportedIds.includes(m.id) ? ' · chỉ tra cứu' : ''}</option>)}</select><button aria-label={`Loại bỏ vật thể ${i + 1}`} title="Loại bỏ khỏi kết quả" onClick={() => p.onExclude(d.id)}><Trash2 size={15}/></button></div>
            </article>; })}</div>
            {!p.scan.detections.length && <div className="no-detections"><Sparkles size={16}/><span>Thử tra cứu thư viện hoặc thêm một nhóm vật liệu thủ công.</span></div>}
            <div className="material-summary"><div className="result-subhead"><strong>Nhóm vật liệu</strong><span>GỢI Ý HIỆN TẠI</span></div>{p.active.length ? <div className="material-tags">{p.active.map(id => <button key={id} className={p.selected === id ? 'is-current' : ''} onClick={() => p.onSelect(id)}><i style={{ background: colors[id] ?? '#b7bdad' }}/>{material(id)?.name ?? id}<small>{p.manual.includes(id) ? 'TỰ CHỌN' : 'GỢI Ý'}</small></button>)}</div> : <p className="muted-copy">Chưa có vật liệu được chọn.</p>}</div>
            <label className="manual-select">TRA CỨU / THÊM THỦ CÔNG<select value="" onChange={e => { if (e.target.value) p.onManual(e.target.value); }}><option value="">+ Chọn nhóm vật liệu</option>{p.materials.filter(m => !p.active.includes(m.id)).map(m => <option key={m.id} value={m.id}>{m.name}{p.supportedIds.includes(m.id) ? ' · mô hình hỗ trợ' : ' · chỉ tra cứu'}</option>)}</select></label>
            {p.active.map(id => { const m = material(id); if (!m) return null; return <article className="advice-entry" key={id}><div className="advice-title"><span style={{ background: colors[id] ?? '#82917b' }}/><div><small>{p.manual.includes(id) || Object.values(p.corrections).includes(id) ? 'BẠN ĐÃ CHỌN / HIỆU CHỈNH' : 'HƯỚNG DẪN XỬ LÝ'}</small><h3>{m.name}</h3></div></div><p>{m.description}</p><div className="advice-columns"><div><b>NÊN LÀM</b><ul>{m.do.map((x, i) => <li key={i}>{x}</li>)}</ul></div><div><b>TRÁNH LÀM</b><ul>{m.avoid.map((x, i) => <li key={i}>{x}</li>)}</ul></div></div><div className="local-tip"><b>LƯU Ý · VIỆT NAM</b><p>{m.caution} {m.vn_tip}</p></div></article>; })}
          </div>}
        </div>
      </div>
    </div>
  </section>;
}
