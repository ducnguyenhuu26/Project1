import { useReveal } from '../lib/useReveal';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';

export function MissionSection() {
  const ref=useReveal<HTMLElement>(); const {language}=useLanguage(); const c=(language==='en'?siteContentEn:siteContent).mission;
  return <section className="mission" id="mission" aria-labelledby="mission-title" ref={ref}><div className="wrap">
    <div className="mission-top reveal"><div><div className="mission-kicker">{c.kicker}</div><h2 className="mission-title" id="mission-title">{c.title}<br/><span>{c.accent}</span></h2></div><p className="mission-copy">{c.copy}</p></div>
    <div className="mission-grid reveal">{c.goals.map((goal,i)=><article className="mission-card" key={goal.title}><span className="mission-num">{String(i+1).padStart(2,'0')}</span><h3>{goal.title}</h3><p>{goal.body}</p></article>)}</div>
  </div></section>;
}
