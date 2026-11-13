import { useReveal } from '../lib/useReveal';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';
import type { Health, Scan } from '../types';

function modelName(version:string|null|undefined){return version?.match(/yolo\d+[a-z]?/i)?.[0]?.toUpperCase()??'YOLO26S';}

export function TechnologySection({health,scan,supportedIds}:{health:Health|null;scan:Scan|null;supportedIds:string[]}){
  const ref=useReveal<HTMLElement>();const {language,t}=useLanguage();const c=(language==='en'?siteContentEn:siteContent).technology;const mode=scan?.mode??health?.mode;
  const classNames:Record<string,[string,string]>={plastic:['Nhựa','Plastic'],paper:['Giấy / bìa','Paper / cardboard'],metal:['Kim loại','Metal'],glass:['Thủy tinh','Glass'],organic:['Hữu cơ','Organic'],textile:['Vải / dệt may','Textile']};
  const modelVersion=scan?.model_version??health?.model_version;
  const stats:Array<{tag:string;value:string;caption:string;kind?:'classes'}>=[
    {tag:t('TRẠNG THÁI HỆ THỐNG','SYSTEM STATUS'),value:mode==='real'?t('AI THẬT','LIVE AI'):mode==='demo'?'DEMO':t('ĐANG KẾT NỐI','CONNECTING'),caption:mode==='demo'?t('Đang trình diễn bằng ảnh mẫu','Showing the sample image'):t('Dịch vụ FastAPI','FastAPI service')},
    {tag:t('MÔ HÌNH NHẬN DIỆN','DETECTION MODEL'),value:mode==='demo'?t('ẢNH MẪU','SAMPLE'):modelName(modelVersion),caption:mode==='demo'?t('Chế độ demo không gọi mô hình','The demo does not run the model'):t('Đang chạy qua FastAPI','Running through FastAPI')},
    {tag:t('NHÓM RÁC NHẬN DIỆN','DETECTABLE WASTE GROUPS'),value:supportedIds.length?String(supportedIds.length).padStart(2,'0'):t('ĐANG TẢI','LOADING'),caption:supportedIds.map(id=>classNames[id]?.[language==='en'?1:0]??id.replaceAll('_',' ')).join(' · '),kind:'classes'},
  ];
  return <section className="tech" id="tech" aria-labelledby="tech-title" ref={ref}><div className="wrap">
    <div className="section-head reveal"><div><div className="section-n">{c.kicker}</div><h2 className="section-title" id="tech-title">{c.title}</h2></div><p className="section-sub">{c.description}</p></div>
    <div className="tech-grid reveal">{c.cards.map(card=><article className="tech-card" key={card.number}><span className="number">{card.number}</span><div className="icon" aria-hidden="true">{card.icon}</div><h3>{card.title}</h3><p>{card.body}</p></article>)}</div>
    <div className="flow reveal" aria-label={t('Đường đi dữ liệu','Data flow')}>{c.flow.map((item,i)=><div className="flow-group" key={item[0]}><div className="flow-step"><span>{String(i+1).padStart(2,'0')}</span><b>{i===1?t('MÔ HÌNH AI','AI DETECTOR'):item[0]}</b><small>{i===1?mode==='real'?t('Đang chạy qua FastAPI','Serving through FastAPI'):mode==='demo'?t('Chế độ ảnh mẫu','Sample image mode'):t('Chờ kết nối API','Waiting for API'):i===2?t('Khung · Lớp · Độ tin cậy','Boxes · Classes · Confidence'):i===3?t('Thư viện hướng dẫn','Guidance library'):item[1]}</small></div>{i<c.flow.length-1&&<span className="arrow" aria-hidden="true">→</span>}</div>)}</div>
    <div className="stats reveal" aria-label={t('Thông tin hệ thống nhận diện','Detection system information')}>{stats.map(stat=><article className={`stat${stat.kind?` stat-${stat.kind}`:''}`} key={stat.tag}><div className="tag">{stat.tag}</div><strong className="stat-value">{stat.value}</strong><small className={stat.kind==='classes'?'stat-classes':undefined}>{stat.caption}</small></article>)}</div>
    <p className="tiny tech-note">{t('Trạng thái dịch vụ và các nhóm rác hỗ trợ được đồng bộ từ FastAPI. Ảnh mẫu dùng để minh họa quy trình Scan Studio.','Service status and supported waste groups are synchronized from FastAPI. The sample image illustrates the Scan Studio flow.')}</p>
  </div></section>;
}
