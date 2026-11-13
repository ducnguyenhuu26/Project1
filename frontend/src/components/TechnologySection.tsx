import { useReveal } from '../lib/useReveal';
import { siteContent } from '../content/siteContent';
import type { Health, Knowledge, Scan } from '../types';

export function TechnologySection({health,knowledge,scan,supportedIds}:{health:Health|null;knowledge:Knowledge|null;scan:Scan|null;supportedIds:string[]}){
  const ref=useReveal<HTMLElement>();const c=siteContent.technology;
  const stats=[
    {tag:'API / DETECTOR MODE',value:scan?.mode??health?.mode?.toUpperCase()??'CONNECTING',caption:health?.mode==='demo'?'Demo detections are illustrative':'Mode returned by FastAPI'},
    {tag:'MODEL VERSION',value:scan?.model_version??health?.model_version??'NOT AVAILABLE',caption:health?.model_status??'Read from live API response'},
    {tag:'SUPPORTED CLASSES',value:String(supportedIds.length).padStart(2,'0'),caption:supportedIds.length?supportedIds.join(' · '):'Reported by health / scan API'},
    {tag:'TAXONOMY VERSION',value:scan?.taxonomy_version??knowledge?.taxonomy_version??'NOT AVAILABLE',caption:'Returned by the current backend'},
  ];
  return <section className="tech" id="tech" aria-labelledby="tech-title" ref={ref}><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">{c.kicker}</div><h2 className="section-title" id="tech-title">{c.title}</h2></div><p className="section-sub">{c.description}</p></div>
    <div className="tech-grid reveal">{c.cards.map(card=><article className="tech-card" key={card.number}><span className="number">{card.number}</span><div className="icon" aria-hidden="true">{card.icon}</div><h3>{card.title}</h3><p>{card.body}</p></article>)}</div>
    <div className="flow reveal" aria-label="Đường đi dữ liệu">{c.flow.map((item,i)=><div className="flow-group" key={item[0]}><div className="flow-step"><span>{String(i+1).padStart(2,'0')}</span><b>{item[0]}</b><small>{item[1]}</small></div>{i<c.flow.length-1&&<span className="arrow" aria-hidden="true">→</span>}</div>)}</div>
    <div className="stats reveal" aria-label="Thông tin runtime từ API">{stats.map(stat=><article className="stat" key={stat.tag}><div className="tag">{stat.tag}</div><strong>{stat.value}</strong><small>{stat.caption}</small></article>)}</div>
    <p className="tiny tech-note">{c.note}</p>
  </div></section>;
}
