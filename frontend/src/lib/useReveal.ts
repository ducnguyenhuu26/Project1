import { useEffect, useRef } from 'react';

export function useReveal<T extends HTMLElement>() {
  const ref=useRef<T>(null);
  useEffect(()=>{
    const node=ref.current;
    if(!node)return;
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)){
      node.querySelectorAll<HTMLElement>('.reveal').forEach(target=>target.classList.add('shown'));
      return;
    }
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add('shown');observer.unobserve(entry.target);}
    }),{threshold:.1});
    const observeTargets=(root:ParentNode)=>root.querySelectorAll<HTMLElement>('.reveal').forEach(target=>observer.observe(target));
    observeTargets(node);
    const mutations=new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(added=>{
      if(!(added instanceof HTMLElement))return;
      if(added.matches('.reveal'))observer.observe(added);
      observeTargets(added);
    })));
    mutations.observe(node,{childList:true,subtree:true});
    return()=>{observer.disconnect();mutations.disconnect();};
  },[]);
  return ref;
}
