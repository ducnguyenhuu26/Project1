import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { ArrowRight, ImagePlus, LoaderCircle, RotateCcw, ScanLine, ShieldCheck, Trash2, Upload, X } from 'lucide-react';
import type { Detection, Material, Scan } from '../types';
import { useReveal } from '../lib/useReveal';

const palette:Record<string,string>={plastic:'#d91e35',paper:'#d5a829',metal:'#389783',glass:'#629cb4',organic:'#5a9470',battery:'#a95d57',textile:'#9878a0',e_waste:'#756a98'};
type Props={file:File|null;preview:string;scan:Scan|null;materials:Material[];supportedIds:string[];busy:boolean;error:string;onChoose:(file:File)=>void;onAnalyze:()=>void;onDemo:()=>void;onCorrect:(d:Detection,id:string)=>void;onExclude:(id:string)=>void;onSelect:(id:string)=>void;selected:string|null;onManual:(id:string)=>void;active:string[];manual:string[];corrections:Record<string,string>;excluded:string[]};

export function ScanStudio(p:Props){
  const section=useReveal<HTMLElement>();const input=useRef<HTMLInputElement>(null);const [showBoxes,setShowBoxes]=useState(true);const[dragging,setDragging]=useState(false);
  const material=(id:string)=>p.materials.find(m=>m.id===id);
  function drop(e:DragEvent){e.preventDefault();setDragging(false);const f=e.dataTransfer.files[0];if(f)p.onChoose(f);}
  function boxKey(e:KeyboardEvent<SVGGElement>,id:string){if(e.key==='Enter'||e.key===' '){e.preventDefault();p.onSelect(id);}}
  const presentDetections=p.scan?.detections.filter(d=>!p.excluded.includes(d.id))??[];
  const current=material(p.selected??'');
  const warnings=p.scan?.warnings??[];
  return <section ref={section} className="section" id="studio" aria-labelledby="studio-title"><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">02 / INTERACTIVE SCAN EXPERIENCE</div><h2 className="section-title" id="studio-title">SCAN STUDIO</h2></div><p className="section-sub">Tải ảnh thật để phân tích qua FastAPI hoặc khám phá ảnh mẫu. Kết quả demo luôn được đánh dấu minh họa.</p></div>
    <div className="scan-panel reveal">
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={e=>{if(e.target.files?.[0])p.onChoose(e.target.files[0]);e.currentTarget.value='';}}/>
      <button className={`upload-box${dragging?' drag':''}`} type="button" onClick={()=>input.current?.click()} onDragOver={e=>{e.preventDefault();setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={drop} aria-label="Kéo thả ảnh hoặc chọn ảnh để phân loại">
        <span className="upload-icon"><ImagePlus size={47} strokeWidth={1.2}/></span><span className="upload-heading">Đưa ảnh vào hệ thống</span><span className="upload-help">Kéo và thả ảnh vào đây<br/>hoặc chọn từ thiết bị của bạn.</span><span className="choose"><Upload size={15}/> &nbsp; Chọn ảnh từ thiết bị</span><span className="upload-note">JPG, PNG, WebP · tối đa 10 MB<br/>Ảnh được gửi tới máy chủ để phân tích.</span>
      </button>
      <div className={`preview${p.busy?' is-scanning':''}`}>
        {p.preview?<img src={p.preview} alt={`Ảnh cần phân loại: ${p.file?.name??'ảnh đã chọn'}`}/>:<div className="preview-placeholder"><ImagePlus size={29}/><strong>Ảnh sẽ xuất hiện tại đây</strong><span>CHỜ ẢNH ĐẦU VÀO</span></div>}
        {p.scan&&p.preview&&showBoxes&&<svg className="box-overlay" viewBox={`0 0 ${p.scan.image_width} ${p.scan.image_height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${presentDetections.length} bounding box${presentDetections.length===1?'':'es'} từ API`}>
          {presentDetections.map((d,i)=>{const id=p.corrections[d.id]??d.category_id??'';const[x1,y1,x2,y2]=d.bbox_xyxy;return <g key={d.id} onClick={()=>p.onSelect(id)} onKeyDown={e=>boxKey(e,id)} tabIndex={0} role="button" aria-label={`${material(id)?.name??d.label}, vật thể ${i+1}`}>
            <rect x={x1} y={y1} width={x2-x1} height={y2-y1} fill="none" stroke={palette[id]??'#cb1028'} strokeWidth={Math.max(2,p.scan!.image_width/420)}/>
            <text x={x1+5} y={Math.max(20,y1-6)} fill={palette[id]??'#cb1028'} fontFamily="Arial,sans-serif" fontWeight="700" fontSize={Math.max(14,p.scan!.image_width/48)}>{material(id)?.name??d.label}{p.scan!.mode==='real'&&d.confidence!=null?` ${Math.round(d.confidence*100)}%`:''}</text>
          </g>;})}
        </svg>}
        {p.busy&&<span className="scan-beam" aria-hidden="true"/>}
        <span className="corner tl" aria-hidden="true"/><span className="corner br" aria-hidden="true"/>
        <div className="preview-top"><span className="tiny-pill" id="photo-label">{p.file?p.file.name.slice(0,38):'PHOTO INPUT'}</span><span className={`tiny-pill demo-pill`}>{p.scan?.mode==='real'?'REAL MODEL':p.scan?.mode==='demo'?'DEMO VISUAL':p.file?'READY':'WAITING'}</span></div>
        <div className="preview-bottom"><span>{p.scan?`${p.scan.detections.length} detections · ${p.scan.image_width} × ${p.scan.image_height}`:p.file?`${(p.file.size/1024/1024).toFixed(2)} MB · preview`:'Bounding boxes · class · confidence'}</span><span>⌗ &nbsp; SOICTERRA</span></div>
      </div>
      <div className="results" aria-live="polite">
        <h3 className="results-title">{p.busy?'ĐANG PHÂN TÍCH…':p.scan?`KẾT QUẢ (${presentDetections.length})`:'KẾT QUẢ PHÂN TÍCH'}</h3>
        {p.scan?<>
          <div className="result-meta"><span className={`badge ${p.scan.mode==='demo'?'demo':''}`}>{p.scan.mode==='demo'?'DEMO — KHÔNG PHẢI KẾT QUẢ AI':'REAL · MODEL RESULT'}</span><span className="badge">{p.scan.model_version??'NO MODEL VERSION'}</span></div>
          <div className="results-note">Taxonomy {p.scan.taxonomy_version} · {p.scan.supported_category_ids.length} lớp được API hỗ trợ.</div>
          {warnings.map((w,i)=><p className="result-warning" role="status" key={i}>{w}</p>)}
          {p.scan.mode==='real'&&!p.scan.detections.length&&<p className="result-warning">Không có phát hiện thuộc lớp mô hình đang hỗ trợ. Hãy thử tra cứu hoặc thêm nhãn thủ công.</p>}
          <div className="result-list" aria-label="Danh sách vật thể được trả về từ API">{presentDetections.map((d,i)=>{const id=p.corrections[d.id]??d.category_id??'';return <article className={`result-card${p.selected===id?' selected':''}`} key={d.id}>
            <button className="result-select" onClick={()=>p.onSelect(id)}><span className="result-icon" style={{color:palette[id]??'#cb1028'}}>{String(i+1).padStart(2,'0')}</span><span className="result-text"><b>{material(id)?.name??d.label}</b><small>{p.corrections[d.id]?'Nhãn đã hiệu chỉnh':d.origin==='illustration'?'Phát hiện minh họa':d.origin==='ai'?'AI detection':'Nguồn API'}</small></span><span className="score">{p.scan!.mode==='real'&&d.confidence!=null?`${Math.round(d.confidence*100)}%`:'—'}</span></button>
            <div className="result-actions"><label className="sr-only" htmlFor={`correction-${d.id}`}>Sửa nhãn vật thể {i+1}</label><select id={`correction-${d.id}`} value={id} onChange={e=>p.onCorrect(d,e.target.value)}><option value="">Chưa xác định</option>{p.materials.map(m=><option key={m.id} value={m.id}>{m.name}{p.supportedIds.includes(m.id)?'':' · tra cứu tay'}</option>)}</select><button title="Loại bỏ vật thể này" aria-label={`Loại bỏ vật thể ${i+1}`} onClick={()=>p.onExclude(d.id)}><X size={15}/></button></div>
          </article>;})}</div>
          {!p.scan!.detections.length&&<div className="result-empty">Ảnh có thể chứa vật liệu ngoài phạm vi hiện hỗ trợ. Chọn một nhóm bên dưới để tra cứu thủ công.</div>}
          <div className="result-count">{p.active.length} nhóm vật liệu đang được xem xét · {p.manual.length} nhãn tự chọn</div>
          <label className="manual-field">THÊM NHÓM VẬT LIỆU THỦ CÔNG<select value="" onChange={e=>e.target.value&&p.onManual(e.target.value)}><option value="">+ Chọn để tra cứu</option>{p.materials.filter(m=>!p.active.includes(m.id)).map(m=><option key={m.id} value={m.id}>{m.name}{p.supportedIds.includes(m.id)?' · model hỗ trợ':' · chỉ tra cứu'}</option>)}</select></label>
          {p.active.length>0&&<div className="result-summary">{p.active.map(id=>{const m=material(id);return m?<p key={id}><b>{m.name}:</b> {m.do[0]} {m.caution}</p>:null})}</div>}
          {current&&<div className="feedback"><b>{current.name.toLocaleUpperCase('vi')} / HƯỚNG DẪN</b><br/><p>{current.description}</p><strong>✓ NÊN LÀM</strong><p>{current.do.join(' ')}</p><strong>! LƯU Ý</strong><p>{current.avoid.join(' ')} {current.caution} {current.vn_tip}</p></div>}
        </>:<>
          <div className="results-note">Kết quả có confidence, lớp và hướng dẫn theo từng vật thể.</div>
          <div className="result-empty">{p.busy?'Đang chờ phản hồi FastAPI.':'Chọn ảnh để bắt đầu. Ảnh minh họa cũng gửi qua API, không tạo dự đoán giả.'}</div>
        </>}
        {p.error&&<div className="feedback error-feedback" role="alert"><b>KHÔNG THỂ PHÂN TÍCH</b><br/>{p.error}</div>}
        <button className="choose" disabled={!p.file||p.busy} onClick={p.onAnalyze}>{p.busy?<><LoaderCircle size={15} className="spin"/> Đang gửi ảnh…</>:<><ScanLine size={15}/> Phân tích ảnh <ArrowRight size={15}/></>}</button>
        {p.scan&&<div className="studio-tools-inline"><button className="textbtn" onClick={()=>setShowBoxes(v=>!v)}>{showBoxes?'Ẩn khung nhận diện':'Hiện khung nhận diện'}</button><button className="textbtn" onClick={()=>input.current?.click()}><RotateCcw size={13}/> Đổi ảnh</button></div>}
      </div>
    </div>
    <div className="studio-tools"><span className="tiny"><ShieldCheck size={13}/> API mode, taxonomy và lớp hỗ trợ lấy từ phản hồi FastAPI. Ảnh mẫu luôn được ghi rõ demo.</span><button className="textbtn" onClick={p.onDemo} disabled={p.busy}><ScanLine size={13}/> Chạy ảnh minh họa</button></div>
  </div></section>;
}
