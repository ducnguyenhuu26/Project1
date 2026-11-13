import { siteContent, siteContentEn } from '../content/siteContent';
import { useReveal } from '../lib/useReveal';
import { useLanguage } from '../lib/language';

export function TeamSection(){
  const ref=useReveal<HTMLElement>();const {language,t}=useLanguage();const c=(language==='en'?siteContentEn:siteContent).team;
  return <section className="team" id="team" aria-labelledby="team-title" ref={ref}><div className="wrap">
    <div className="team-head reveal"><div><div className="mission-kicker">{c.kicker}</div><h2 className="mission-title" id="team-title">{c.title}<br/><span>{c.accent}</span></h2></div><p>{c.description}</p></div>
    <div className="team-list reveal">{c.members.length?c.members.map((member,i)=><article className="member-card" key={`${member.name}-${i}`}><span className="member-id">{t('ĐỘI NGŨ','TEAM')} / {String(i+1).padStart(2,'0')}</span>{member.photo?<img className="member-photo" src={member.photo} alt={member.name}/>:<span className="member-avatar" aria-hidden="true">{String(i+1).padStart(2,'0')}</span>}<div><h3>{member.name}</h3>{(member.role||member.bio)&&<p>{[member.role,member.bio].filter(Boolean).join(' · ')}</p>}{member.links?.map(link=><a href={link.href} key={link.href}>{link.label}</a>)}</div></article>):<div className="team-placeholder"><b>SOICTERRA / {t('ĐỘI NGŨ','TEAM')}</b><p>{c.empty}</p></div>}</div>
  </div></section>;
}
