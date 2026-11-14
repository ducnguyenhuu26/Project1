import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent, type PointerEvent } from 'react';
import { ArrowRight, ImagePlus, LoaderCircle, RotateCcw, ScanLine, ShieldCheck, Upload, X } from 'lucide-react';
import type { Detection, ItemSession, Material, Scan } from '../types';
import { useReveal } from '../lib/useReveal';
import { useLanguage } from '../lib/language';
import { RecommendationWizard } from './RecommendationWizard';
import { imagePoint, regionFromPoints, type ImagePoint, type Region } from '../lib/region';

const palette:Record<string,string>={plastic:'#d91e35',paper:'#d5a829',metal:'#389783',glass:'#629cb4',organic:'#5a9470',battery:'#a95d57',textile:'#9878a0',e_waste:'#756a98'};
const modelName=(version:string)=>version.match(/yolo\d+[a-z]?/i)?.[0]?.toUpperCase()??'YOLO26S';
type Props={file:File|null;preview:string;scan:Scan|null;scanContextKey:string|null;materials:Material[];supportedIds:string[];busy:boolean;error:string;regionBusy:boolean;regionError:string;onRegion:(box:Region)=>void;onChoose:(file:File)=>void;onAnalyze:()=>void;onDemo:()=>void;onCorrect:(d:Detection,id:string)=>void;onExclude:(id:string)=>void;onSelect:(id:string)=>void;selected:string|null;onManual:(id:string)=>void;active:string[];manual:string[];corrections:Record<string,string>;excluded:string[]};

export function ScanStudio(p:Props){
  const {t}=useLanguage();
  const section=useReveal<HTMLElement>();const input=useRef<HTMLInputElement>(null);const [showBoxes,setShowBoxes]=useState(true);const[dragging,setDragging]=useState(false);
  const [drawMode,setDrawMode]=useState(false);const [draft,setDraft]=useState<{start:ImagePoint;end:ImagePoint}|null>(null);
  const draftRef=useRef<{start:ImagePoint;end:ImagePoint}|null>(null);
  const [drawError,setDrawError]=useState('');
  const [sessions,setSessions]=useState<Record<string,ItemSession>>({});
  useEffect(()=>{setSessions({});},[p.scanContextKey]);
  const emptySession:ItemSession={confirmedObjectId:'',answers:{},recommendation:null};
  const sessionKey=p.selected&&p.selected!=='manual'&&p.scanContextKey?`${p.scanContextKey}:${p.selected}`:p.scanContextKey?`${p.scanContextKey}:manual`:'manual';
  const session=sessions[sessionKey]??emptySession;
  const updateSession=(next:ItemSession)=>setSessions(previous=>({...previous,[sessionKey]:next}));
  const clearSession=(id:string)=>{if(p.scanContextKey)setSessions(previous=>({...previous,[`${p.scanContextKey}:${id}`]:emptySession}));};
  const material=(id:string)=>p.materials.find(m=>m.id===id);
  function drop(e:DragEvent){e.preventDefault();setDragging(false);const f=e.dataTransfer.files[0];if(f)p.onChoose(f);}
  function boxKey(e:KeyboardEvent<SVGGElement>,id:string){if(e.key==='Enter'||e.key===' '){e.preventDefault();p.onSelect(id);}}
  function point(e:PointerEvent<SVGSVGElement>,clamp=false){return p.scan?imagePoint(e.clientX,e.clientY,e.currentTarget.getBoundingClientRect(),p.scan.image_width,p.scan.image_height,clamp):null;}
  function pointerDown(e:PointerEvent<SVGSVGElement>){if(!drawMode||p.regionBusy)return;const start=point(e);if(!start)return;e.preventDefault();e.currentTarget.setPointerCapture?.(e.pointerId);draftRef.current={start,end:start};setDraft(draftRef.current);setDrawError('');}
  function pointerMove(e:PointerEvent<SVGSVGElement>){if(!draftRef.current)return;const end=point(e,true);if(!end)return;draftRef.current={...draftRef.current,end};setDraft(draftRef.current);}
  function pointerUp(e:PointerEvent<SVGSVGElement>){if(!draftRef.current)return;const end=point(e,true)??draftRef.current.end;const box=regionFromPoints(draftRef.current.start,end);draftRef.current=null;setDraft(null);e.currentTarget.releasePointerCapture?.(e.pointerId);if(box[2]-box[0]<16||box[3]-box[1]<16){setDrawError('Vùng khoanh quá nhỏ; hãy kéo rộng ít nhất 16 pixel mỗi chiều.');return;}setDrawMode(false);p.onRegion(box);}
  const presentDetections=p.scan?.detections.filter(d=>!p.excluded.includes(d.id))??[];
  const selectedDetection=presentDetections.find(d=>d.id===p.selected);
  const selectedCategory=selectedDetection?(p.corrections[selectedDetection.id]??selectedDetection.category_id??''):p.manual.at(-1)??'';
  const detectedCategoryId=selectedDetection?.category_id??'';
  const selectedCorrection=selectedDetection?p.corrections[selectedDetection.id]:undefined;
  const recommendationSource=selectedDetection?.category_id?(selectedCorrection!==undefined&&selectedCorrection!==selectedDetection.category_id?'corrected':'detected'):'manual';
  const warnings=(p.scan?.warnings??[]).map(w=>p.scan?.mode==='demo'&&/minh họa/i.test(w)?'Ảnh mẫu trình diễn quy trình nhận diện với các khung vật thể minh họa.':w);
  return <section ref={section} className="section" id="studio" aria-labelledby="studio-title"><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">02 / INTERACTIVE SCAN EXPERIENCE</div><h2 className="section-title" id="studio-title">SCAN STUDIO</h2></div><p className="section-sub">{t('Tải ảnh để phân tích qua FastAPI hoặc chạy ảnh mẫu trong chế độ demo.','Upload an image for FastAPI analysis, or run the sample in demo mode.')}</p></div>
    <div className="scan-panel reveal">
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={e=>{if(e.target.files?.[0])p.onChoose(e.target.files[0]);e.currentTarget.value='';}}/>
      <button className={`upload-box${dragging?' drag':''}`} type="button" onClick={()=>input.current?.click()} onDragOver={e=>{e.preventDefault();setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={drop} aria-label={t('Kéo thả ảnh hoặc chọn ảnh để phân loại','Drop or choose an image to classify')}>
        <span className="upload-icon"><ImagePlus size={47} strokeWidth={1.2}/></span><span className="upload-heading">{t('Đưa ảnh vào hệ thống','Add an image')}</span><span className="upload-help">{t('Kéo và thả ảnh vào đây','Drag and drop an image here')}<br/>{t('hoặc chọn từ thiết bị của bạn.','or choose it from your device.')}</span><span className="choose"><Upload size={15}/> &nbsp; {t('Chọn ảnh từ thiết bị','Choose an image')}</span><span className="upload-note">JPG, PNG, WebP · {t('tối đa','up to')} 10 MB<br/>{t('Ảnh được gửi tới máy chủ để phân tích.','Images are sent to the server for analysis.')}</span>
      </button>
      <div className={`preview${p.busy?' is-scanning':''}`}>
        {p.preview?<img src={p.preview} alt={`${t('Ảnh cần phân loại','Image to classify')}: ${p.file?.name??t('ảnh đã chọn','selected image')}`}/>:<div className="preview-placeholder"><ImagePlus size={29}/><strong>{t('Ảnh sẽ xuất hiện tại đây','Your image will appear here')}</strong><span>{t('CHỜ ẢNH ĐẦU VÀO','WAITING FOR IMAGE')}</span></div>}
        {p.scan&&p.preview&&(showBoxes||drawMode)&&<svg className={`box-overlay${drawMode?' draw-mode':''}`} viewBox={`0 0 ${p.scan.image_width} ${p.scan.image_height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={drawMode?'Kéo để khoanh vùng vật thể bị bỏ sót':`${presentDetections.length} bounding box${presentDetections.length===1?'':'es'} từ API`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={()=>{draftRef.current=null;setDraft(null);}}>
          {drawMode&&<rect className="draw-hit-area" x="0" y="0" width={p.scan.image_width} height={p.scan.image_height} fill="transparent"/>}
          {showBoxes&&presentDetections.map((d,i)=>{const category=p.corrections[d.id]??d.category_id??'';const[x1,y1,x2,y2]=d.bbox_xyxy;return <g key={d.id} onClick={()=>!drawMode&&p.onSelect(d.id)} onKeyDown={e=>!drawMode&&boxKey(e,d.id)} tabIndex={drawMode?-1:0} role="button" aria-pressed={p.selected===d.id} aria-label={`${material(category)?.name??d.label}, vật thể ${i+1}`}>
            <rect x={x1} y={y1} width={x2-x1} height={y2-y1} fill="none" stroke={p.selected===d.id?'#ffffff':palette[category]??'#cb1028'} strokeWidth={p.selected===d.id?4:Math.max(2,p.scan!.image_width/420)}/>
            <text x={x1+5} y={Math.max(20,y1-6)} fill={palette[category]??'#cb1028'} fontFamily="Arial,sans-serif" fontWeight="700" fontSize={Math.max(14,p.scan!.image_width/48)}>{String(i+1).padStart(2,'0')} · {d.label}{p.scan!.mode==='real'&&d.confidence!=null?` ${Math.round(d.confidence*100)}%`:''}</text>
          </g>;})}
          {draft&&<rect className="draft-region" x={Math.min(draft.start.x,draft.end.x)} y={Math.min(draft.start.y,draft.end.y)} width={Math.abs(draft.end.x-draft.start.x)} height={Math.abs(draft.end.y-draft.start.y)}/>}
        </svg>}
        {p.busy&&<span className="scan-beam" aria-hidden="true"/>}
        <span className="corner tl" aria-hidden="true"/><span className="corner br" aria-hidden="true"/>
        <div className="preview-top"><span className="tiny-pill" id="photo-label">{p.file?p.file.name.slice(0,38):'PHOTO INPUT'}</span><span className={`tiny-pill demo-pill`}>{p.scan?.mode==='real'?'AI · LIVE':p.scan?.mode==='demo'?'ẢNH MẪU · DEMO':p.file?'READY':'WAITING'}</span></div>
        <div className="preview-bottom"><span>{p.scan?`${p.scan.detections.length} detections · ${p.scan.image_width} × ${p.scan.image_height}`:p.file?`${(p.file.size/1024/1024).toFixed(2)} MB · preview`:'Bounding boxes · class · confidence'}</span><span>⌗ &nbsp; SOICTERRA</span></div>
      </div>
      <div className="results" aria-live="polite">
        <h3 className="results-title">{p.busy?'ĐANG PHÂN TÍCH…':p.scan?`KẾT QUẢ (${presentDetections.length})`:'KẾT QUẢ PHÂN TÍCH'}</h3>
        {p.scan?<>
          <div className="result-meta"><span className={`badge ${p.scan.mode==='demo'?'demo':''}`}>{p.scan.mode==='demo'?'DEMO · ẢNH MẪU':'AI · KẾT QUẢ MÔ HÌNH'}</span>{p.scan.mode==='demo'?<span className="badge">TRÌNH DIỄN API</span>:p.scan.model_version&&<span className="badge">{modelName(p.scan.model_version)}</span>}</div>
          <div className="results-note">Taxonomy {p.scan.taxonomy_version} · {p.scan.supported_category_ids.length} lớp được API hỗ trợ.</div>
          {warnings.map((w,i)=><p className="result-warning" role="status" key={i}>{w}</p>)}
          <button className="choose region-action" type="button" aria-pressed={drawMode} disabled={p.regionBusy} onClick={()=>{setDrawMode(value=>!value);setDraft(null);draftRef.current=null;setDrawError('');}}>{p.regionBusy?'Đang nhận diện lại vùng…':drawMode?'Hủy khoanh vùng':'Khoanh vật thể bị bỏ sót'}</button>
          {drawMode&&<p className="results-note" role="status">Kéo trực tiếp trên ảnh để chọn một vùng hình chữ nhật. YOLO sẽ nhận diện lại riêng vùng này.</p>}
          {(drawError||p.regionError)&&<p className="result-warning" role="alert">{drawError||p.regionError} Bạn vẫn có thể tra cứu KB thủ công.</p>}
          {p.scan.mode==='real'&&!p.scan.detections.length&&<p className="result-warning">{t('Không có phát hiện thuộc lớp mô hình đang hỗ trợ. Hãy thử tra cứu hoặc thêm nhãn thủ công.','No objects matched the model’s supported classes. Try the library or add a manual label.')}</p>}
          <div className="result-list" aria-label="Danh sách vật thể được trả về từ API">{presentDetections.map((d,i)=>{const id=p.corrections[d.id]??d.category_id??'';return <article className={`result-card${p.selected===d.id?' selected':''}`} key={d.id}>
            <button className="result-select" aria-pressed={p.selected===d.id} aria-label={`Chọn vật thể ${i+1}: ${material(id)?.name??d.label}`} onClick={()=>p.onSelect(d.id)}><span className="result-icon" style={{color:palette[id]??'#cb1028'}}>{String(i+1).padStart(2,'0')}</span><span className="result-text"><b>{material(id)?.name??d.label}</b><small>{p.corrections[d.id]?`Đã sửa nhãn · YOLO gợi ý: ${d.label}`:d.origin==='manual'?'Vùng khoanh · chưa nhận diện':d.origin==='illustration'?'Phát hiện minh họa':d.origin==='ai'?'Nhãn YOLO':'Nguồn API'}</small>{sessions[`${p.scanContextKey}:${d.id}`]?.recommendation?.status==='complete'&&<small>Đã có hướng dẫn</small>}</span><span className="score">{p.scan!.mode==='real'&&d.confidence!=null?`${Math.round(d.confidence*100)}% · độ tin cậy mô hình`:'—'}</span></button>
            <div className="result-actions"><label className="sr-only" htmlFor={`correction-${d.id}`}>Sửa nhãn vật thể {i+1}</label><select id={`correction-${d.id}`} value={id} onChange={e=>{clearSession(d.id);p.onCorrect(d,e.target.value);}}><option value="">Chưa xác định</option>{p.materials.map(m=><option key={m.id} value={m.id}>{m.name}{p.supportedIds.includes(m.id)?'':' · tra cứu tay'}</option>)}</select><button title="Loại bỏ vật thể này" aria-label={`Loại bỏ vật thể ${i+1}`} onClick={()=>{clearSession(d.id);p.onExclude(d.id);}}><X size={15}/></button></div>
          </article>;})}</div>
          {!presentDetections.length&&<div className="result-empty">Không có vật thể đang chọn. Tra cứu toàn bộ thư viện bên dưới.</div>}
          <button className="textbtn" type="button" onClick={()=>p.onSelect('manual')}>Không tìm thấy / tra cứu toàn bộ</button>
          <button className="choose guidance-jump" type="button" aria-controls="studio-guidance" onClick={()=>document.getElementById('studio-guidance')?.scrollIntoView({behavior:'smooth',block:'start'})}>{session.recommendation?.status==='complete'?'Xem lời khuyên cho vật thể này':'Chọn đồ vật để xem lời khuyên'} <ArrowRight size={15}/></button>
          <div className="result-count">{p.active.length} nhóm vật liệu đang được xem xét · {p.manual.length} nhãn tự chọn</div>
          {p.scan.summary.length>0&&<div className="results-note" aria-live="polite">Tóm tắt đang chọn: {p.scan.summary.map(row=>`${row.name} × ${row.estimated_count}`).join(' · ')}</div>}
          <label className="manual-field">THÊM NHÓM VẬT LIỆU THỦ CÔNG<select value="" onChange={e=>e.target.value&&p.onManual(e.target.value)}><option value="">+ Chọn để tra cứu</option>{p.materials.filter(m=>!p.active.includes(m.id)).map(m=><option key={m.id} value={m.id}>{m.name}{p.supportedIds.includes(m.id)?' · model hỗ trợ':' · chỉ tra cứu'}</option>)}</select></label>
        </>:<>
          <div className="results-note">Kết quả có confidence, lớp và hướng dẫn theo từng vật thể.</div>
          <div className="result-empty">{p.busy?'Đang chờ phản hồi FastAPI. Bạn vẫn có thể tra cứu KB.':'Chọn ảnh để bắt đầu hoặc tra cứu KB thủ công.'}</div>
          <button className="textbtn" type="button" onClick={()=>p.onSelect('manual')}>Tra cứu toàn bộ KB</button>
          {p.selected==='manual'&&<button className="choose guidance-jump" type="button" aria-controls="studio-guidance" onClick={()=>document.getElementById('studio-guidance')?.scrollIntoView({behavior:'smooth',block:'start'})}>Mở tra cứu KB <ArrowRight size={15}/></button>}
        </>}
        {p.error&&<div className="feedback error-feedback" role="alert"><b>KHÔNG THỂ PHÂN TÍCH</b><br/>{p.error}</div>}
        <button className="choose" disabled={!p.file||p.busy} onClick={p.onAnalyze}>{p.busy?<><LoaderCircle size={15} className="spin"/> Đang gửi ảnh…</>:<><ScanLine size={15}/> Phân tích ảnh <ArrowRight size={15}/></>}</button>
        {p.scan&&<div className="studio-tools-inline"><button className="textbtn" onClick={()=>setShowBoxes(v=>!v)}>{showBoxes?'Ẩn khung nhận diện':'Hiện khung nhận diện'}</button><button className="textbtn" onClick={()=>input.current?.click()}><RotateCcw size={13}/> Đổi ảnh</button></div>}
      </div>
    </div>
    {(p.scan||p.selected==='manual')&&<div className="studio-guidance" id="studio-guidance">
      <div className="studio-guidance-intro"><span className="section-n">HƯỚNG XỬ LÝ</span><h3>LỜI KHUYÊN CHO TỪNG ĐỒ VẬT</h3><p>Chọn đúng vật thể từ KB, trả lời câu hỏi về tình trạng, rồi xem hướng dẫn xử lý và lưu ý an toàn.</p></div>
      {selectedDetection&&<p className="result-warning">Vật thể {String(p.scan!.detections.findIndex(d=>d.id===selectedDetection.id)+1).padStart(2,'0')} · YOLO gợi ý: {selectedDetection.label} ({selectedDetection.category_id??'chưa xác định'}). Nhóm đang chọn: {selectedCategory||'chưa xác định'}. Đây là gợi ý; hãy chọn đúng đồ vật.</p>}
      <RecommendationWizard key={`${sessionKey}:${selectedCategory}`} categoryId={selectedCategory} detectedCategoryId={detectedCategoryId} source={recommendationSource} session={session} onSessionChange={updateSession}/>
    </div>}
    <div className="studio-tools"><span className="tiny"><ShieldCheck size={13}/> API mode, taxonomy và lớp hỗ trợ được đồng bộ từ FastAPI. Ảnh mẫu trình diễn quy trình qua cùng API.</span><button className="textbtn" onClick={p.onDemo} disabled={p.busy||p.regionBusy}><ScanLine size={13}/> Chạy ảnh mẫu qua API</button></div>
  </div></section>;
}
