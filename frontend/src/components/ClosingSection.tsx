import { ArrowRight } from 'lucide-react';
import { siteContent } from '../content/siteContent';
export function ClosingSection(){const c=siteContent.closing;return <section className="project-end"><div className="wrap project-end-inner"><div><div className="story-eyebrow closing-eyebrow">{c.eyebrow}</div><h2>{c.title}</h2><p>{c.description}</p></div><a href="#studio" className="btn">{c.action} <ArrowRight size={15}/></a></div></section>;}
