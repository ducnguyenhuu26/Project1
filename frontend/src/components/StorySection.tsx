import { useReveal } from '../lib/useReveal';
import { siteContent, siteContentEn } from '../content/siteContent';
import { useLanguage } from '../lib/language';

export function StorySection() {
  const ref=useReveal<HTMLElement>(); const {language}=useLanguage(); const c=(language==='en'?siteContentEn:siteContent).story;
  const leadParts=c.lead.split(language==='en'?/(what waste group does this item belong to|how should it be handled)/g:/(thuộc nhóm rác nào|được xử lý ra sao)/g);
  return <section className="story" id="story" aria-labelledby="story-title" ref={ref}>
    <div className="wrap story-grid"><div className="reveal"><div className="story-index">{c.index}</div><p className="story-eyebrow" style={{marginTop:32}}>{c.eyebrow}</p></div>
      <div className="reveal"><span className="story-eyebrow">{c.title}</span><h2 className="story-h" id="story-title">{language==='en'?<>WASTE DOES NOT DISAPPEAR.<br/><em>IT JUST LEAVES OUR SIGHT.</em></>:<>Rác không biến mất<br/><em>Nó chỉ rời khỏi tầm&nbsp;mắt</em></>}</h2>
        <p className="story-lead">{leadParts.map((part,i)=>part==='thuộc nhóm rác nào'||part==='được xử lý ra sao'||part==='what waste group does this item belong to'||part==='how should it be handled'?<em key={i}>{part}</em>:part)}</p><div className="story-rule"/><p className="story-support">{c.support}</p><p className="story-quote">{c.quote}</p>
      </div>
    </div>
  </section>;
}
