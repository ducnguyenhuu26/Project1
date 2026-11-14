import { useMemo, useState } from 'react';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useReveal } from '../lib/useReveal';
import { useLanguage } from '../lib/language';
import { RecommendationWizard } from './RecommendationWizard';
import { EnvironmentalNews } from './EnvironmentalNews';
import type { HistoryEntry, Knowledge } from '../types';

export function KnowledgeSections({knowledge,supportedIds}:{knowledge:Knowledge|null;supportedIds:string[]}){
  const {language,t}=useLanguage(); const content=(language==='en'?siteContentEn:siteContent).library;
  const[active,setActive]=useState('');const[query,setQuery]=useState('');const[filter,setFilter]=useState<'all'|'supported'|'manual'>('all');const ref=useReveal<HTMLElement>();const materials=knowledge?.materials??[];
  const matches=useMemo(()=>materials.filter(m=>{const text=[m.name,m.id,...m.examples,...(m.synonyms??[])].join(' ').toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi'));const covered=supportedIds.includes(m.id)||knowledge?.categories.some(c=>c.material_id===m.id&&supportedIds.includes(c.id))===true;return text&&(filter==='all'||(filter==='supported'?covered:!covered));}),[materials,query,filter,supportedIds,knowledge]);
  const selected=matches.find(m=>m.id===active)??matches[0];
  const selectedSupported=selected?(supportedIds.includes(selected.id)||knowledge?.categories.some(c=>c.material_id===selected.id&&supportedIds.includes(c.id))===true):false;
  return <section className="section library" id="library" aria-labelledby="library-title" ref={ref}><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">{content.kicker}</div><h2 className="section-title" id="library-title">{content.title}</h2></div><p className="section-sub">{content.description}</p></div>
    <EnvironmentalNews />
    <RecommendationWizard />
    {!knowledge&&<p className="library-state" role="status">{t('Đang kết nối thư viện kiến thức…','Connecting to the knowledge library…')}</p>}
    {knowledge&&<><div className="library-controls reveal"><label className="library-search">{t('TÌM TRONG THƯ VIỆN','SEARCH THE LIBRARY')}<input value={query} onChange={e=>setQuery(e.target.value)} placeholder={t('chai nhựa, pin, giấy…','plastic bottle, battery, paper…')}/></label><div className="library-filters" role="group" aria-label={t('Lọc nhóm vật liệu','Filter material groups')}>{([{id:'all',label:t('Tất cả','All')},{id:'supported',label:t('Model hỗ trợ','AI supported')},{id:'manual',label:t('Tra cứu tay','Lookup')} ] as const).map(x=><button key={x.id} className={filter===x.id?'active':''} aria-pressed={filter===x.id} onClick={()=>setFilter(x.id)}>{x.label}</button>)}</div></div>
      <div className="categories reveal" role="group" aria-label="Chọn nhóm vật liệu">{matches.map((m,i)=>{const covered=supportedIds.includes(m.id)||knowledge.categories.some(c=>c.material_id===m.id&&supportedIds.includes(c.id));return <button className={`catbtn${(selected?.id===m.id)?' active':''}`} key={m.id} aria-pressed={selected?.id===m.id} onClick={()=>setActive(m.id)}>{m.name}<span className="category-index">{String(i+1).padStart(2,'0')} · {covered?'AI':'LOOKUP'}</span></button>;})}</div>
      {!matches.length?<p className="library-state">{t('Không tìm thấy vật liệu phù hợp với bộ lọc.','No materials match this filter.')}</p>:<div className="guide reveal" aria-live="polite"><div className="guide-left"><div className="kicker">MATERIAL / {String((materials.findIndex(m=>m.id===selected?.id)+1)||1).padStart(2,'0')}</div><h3>{selected?.name.toLocaleUpperCase(language==='vi'?'vi':'en')}</h3><p>{selected?.description}</p><span className="guide-status">{selectedSupported?t('MODEL HỖ TRỢ','MODEL SUPPORTED'):t('TRA CỨU THỦ CÔNG','MANUAL LOOKUP')}</span></div><div className="guide-right"><b>✓ {t('NÊN LÀM','DO')}</b><p>{selected?.do.join(' ')}</p><hr className="guide-divider"/><b>× {t('TRÁNH LÀM','AVOID')}</b><p>{selected?.avoid.join(' ')}</p><b>! {t('LƯU Ý','NOTE')}</b><p>{selected?.caution} {selected?.vn_tip}</p><div className="library-examples">{selected?.examples.slice(0,4).join(' · ')}</div></div></div>}
    </>}
  </div></section>;
}
export function PrivacyHistory({history,materials,onClear}:{history:HistoryEntry[];materials:Knowledge['materials'];onClear:()=>void}){
  const {t}=useLanguage();
  return <section className="privacy-history" id="privacy" aria-label={t('Lịch sử gần đây','Recent history')}><div className="privacy-copy"><b>{t('QUYỀN RIÊNG TƯ / LỊCH SỬ','PRIVACY / HISTORY')}</b><p>{t('Ảnh được gửi tới máy chủ để phân tích. Lịch sử chỉ lưu thời gian và nhãn trong trình duyệt này (`localStorage`); không lưu ảnh.','Images are sent to the server for analysis. This browser stores only timestamps and labels in localStorage; images are not saved.')}</p></div><div className="privacy-list"><div className="privacy-list-head"><strong>{t('LẦN QUÉT GẦN ĐÂY','RECENT SCANS')}</strong><button onClick={onClear} disabled={!history.length}>{t('Xóa','Clear')}</button></div>{history.length?history.slice(0,5).map((h,i)=><p key={h.id??i}><time>{h.when}</time><span>{h.corrected?t('ĐÃ HIỆU CHỈNH · ','CORRECTED · '):''}{(h.final??h.detected??[]).map(id=>materials.find(m=>m.id===id)?.name??id).join(' · ')||t('Chưa xác định','Unclassified')}</span></p>):<p>{t('Chưa có lần quét nào.','No scans yet.')}</p>}</div></section>;
}
