import { useEffect, useRef } from 'react';

export function useReveal<T extends HTMLElement>() {
  const ref=useRef<T>(null);
  useEffect(()=>{
    const node=ref.current;
    if(!node)return;
    const targets=node.querySelectorAll<HTMLElement>('.reveal');
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)){
      targets.forEach(target=>target.classList.add('shown'));
      return;
    }
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add('shown');observer.unobserve(entry.target);}
    }),{threshold:.1});
    targets.forEach(target=>observer.observe(target));
    return()=>observer.disconnect();
  },[]);
  return ref;
}
