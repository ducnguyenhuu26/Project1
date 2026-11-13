import { useReveal } from '../lib/useReveal';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';
import type { Health, Knowledge, Scan } from '../types';

export function TechnologySection({health,knowledge,scan,supportedIds}:{health:Health|null;knowledge:Knowledge|null;scan:Scan|null;supportedIds:string[]}){
  const ref=useReveal<HTMLElement>();const {language,t}=useLanguage();const c=(language==='en'?siteContentEn:siteContent).technology;const mode=scan?.mode??health?.mode;
  const stats=[
    {tag:'API / DETECTOR MODE',value:mode?.toUpperCase()??t('ĐANG KẾT NỐI','CONNECTING'),caption:mode==='demo'?t('Luồng ảnh mẫu trình diễn qua API','Sample image flow via API'):t('Trạng thái dịch vụ FastAPI','FastAPI service status')},
    {tag:'MODEL VERSION',value:mode==='demo'?t('ẢNH MẪU','SAMPLE'):scan?.model_version??health?.model_version??t('ĐANG CẬP NHẬT','UPDATING'),caption:mode==='demo'?t('Kết quả trình diễn','Demo result'):t('Phiên bản do dịch vụ nhận diện cung cấp','Version reported by the detection service')},
    {tag:'SUPPORTED CLASSES',value:supportedIds.length?String(supportedIds.length).padStart(2,'0'):t('ĐANG TẢI','LOADING'),caption:supportedIds.length?supportedIds.join(' · '):t('Đồng bộ từ API','Synced from API')},
    {tag:'TAXONOMY VERSION',value:scan?.taxonomy_version??knowledge?.taxonomy_version??t('ĐANG TẢI','LOADING'),caption:t('Đồng bộ từ FastAPI','Synced from FastAPI')},
  ];
  return <section className="tech" id="tech" aria-labelledby="tech-title" ref={ref}><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">{c.kicker}</div><h2 className="section-title" id="tech-title">{c.title}</h2></div><p className="section-sub">{c.description}</p></div>
    <div className="tech-grid reveal">{c.cards.map(card=><article className="tech-card" key={card.number}><span className="number">{card.number}</span><div className="icon" aria-hidden="true">{card.icon}</div><h3>{card.title}</h3><p>{card.body}</p></article>)}</div>
    <div className="flow reveal" aria-label={t('Đường đi dữ liệu','Data flow')}>{c.flow.map((item,i)=><div className="flow-group" key={item[0]}><div className="flow-step"><span>{String(i+1).padStart(2,'0')}</span><b>{item[0]}</b><small>{item[1]}</small></div>{i<c.flow.length-1&&<span className="arrow" aria-hidden="true">→</span>}</div>)}</div>
    <div className="stats reveal" aria-label="Thông tin runtime từ API">{stats.map(stat=><article className="stat" key={stat.tag}><div className="tag">{stat.tag}</div><strong>{stat.value}</strong><small>{stat.caption}</small></article>)}</div>
    <p className="tiny tech-note">{c.note}</p>
  </div></section>;
}
