import { useReveal } from '../lib/useReveal';
import { siteContent } from '../content/siteContent';

export function StorySection() {
  const ref=useReveal<HTMLElement>(); const c=siteContent.story;
  return <section className="story" id="story" aria-labelledby="story-title" ref={ref}>
    <div className="wrap story-grid"><div className="reveal"><div className="story-index">{c.index}</div><p className="story-eyebrow" style={{marginTop:32}}>{c.eyebrow}</p></div>
      <div className="reveal"><span className="story-eyebrow">{c.title}</span><h2 className="story-h" id="story-title">RÁC KHÔNG BIẾN MẤT.<br/><em>NÓ CHỈ RỜI KHỎI TẦM MẮT.</em></h2>
        <p className="story-lead">{c.lead}</p><div className="story-rule"/><p className="story-support">{c.support}</p><p className="story-quote">{c.quote}</p>
      </div>
    </div>
  </section>;
}
