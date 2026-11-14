import { ArrowUp, MessageCircle, X } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import type { ChatMessage } from '../types';
import { useLanguage } from '../lib/language';

type ChatStatus = { configured: boolean; provider: string; model: string };
const API = (import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || '';

export function ChatAssistant({ messages, busy, onAsk }: { messages: ChatMessage[]; busy: boolean; onAsk: (message:string)=>void }) {
  const {t}=useLanguage();
  const [open,setOpen]=useState(false);
  const [text,setText]=useState('');
  const [status,setStatus]=useState<ChatStatus|null>(null);

  useEffect(()=>{
    const controller=new AbortController();
    fetch(`${API}/api/v1/chat/status`,{signal:controller.signal})
      .then(response=>{if(!response.ok)throw new Error('status unavailable');return response.json() as Promise<ChatStatus>;})
      .then(setStatus)
      .catch(()=>{if(!controller.signal.aborted)setStatus({configured:false,provider:'Groq',model:''});});
    return ()=>controller.abort();
  },[]);

  function submit(e:FormEvent){e.preventDefault();if(text.trim()&&!busy){onAsk(text.trim());setText('');}}
  const statusLabel=status===null?t('Đang kiểm tra AI…','Checking AI…'):
    status.configured?`${status.provider} · ${status.model}`:t('Groq chưa cấu hình · KB dự phòng','Groq not configured · KB fallback');
  return <>
    <button className="chat-launch" aria-label={open?t('Đóng trợ lý','Close assistant'):t('Mở trợ lý AI','Open AI assistant')} aria-expanded={open} onClick={()=>setOpen(!open)}>
      {open?<X size={17}/>:<MessageCircle size={17}/>}<span>{open?t('Đóng','Close'):t('Trợ lý AI','AI assistant')}</span>
    </button>
    {open&&<aside className="chat-panel" aria-label={t('Trợ lý AI và thư viện kiến thức','AI assistant and knowledge library')}>
      <div className="chat-panel-head"><div><span>{t('TRỢ LÝ AI / THƯ VIỆN KIẾN THỨC','AI ASSISTANT / KNOWLEDGE LIBRARY')}</span><small className={`chat-status${status?.configured?' is-ready':''}`} role="status">{statusLabel}</small></div><button aria-label={t('Đóng trợ lý','Close assistant')} onClick={()=>setOpen(false)}><X size={17}/></button></div>
      <div className="chat-presets"><button onClick={()=>setText(t('Có nên đốt rác không?','Should I burn waste?'))}>{t('Có nên đốt rác?','Can waste be burned?')}</button><button onClick={()=>setText(t('Pin cũ xử lý thế nào?','How should old batteries be handled?'))}>{t('Xử lý pin cũ','Old batteries')}</button></div>
      <div className="chat-log" aria-live="polite">{messages.map((m,i)=><div className={`chat-line ${m.role}`} key={i}><p>{m.text}</p>{m.role==='assistant'&&m.source&&<small className="chat-source">{m.source==='groq'?m.groundedIn==='WasteWise curated knowledge base'?'Groq AI · tham khảo KB':'Groq AI · kiến thức chung':m.groundedIn==='SOICTERRA safety guidance'?t('Hướng dẫn an toàn','Safety guidance'):'KB dự phòng'}</small>}</div>)}{busy&&<p className="chat-line assistant">{t('Đang trả lời…','Thinking…')}</p>}</div>
      <form onSubmit={submit}><label className="sr-only" htmlFor="chat-input">{t('Câu hỏi về phân loại rác','Waste sorting question')}</label><input id="chat-input" value={text} onChange={e=>setText(e.target.value)} placeholder={t('Hỏi về cách xử lý…','Ask how to handle an item…')}/><button disabled={busy||!text.trim()} aria-label={t('Gửi câu hỏi','Send question')}><ArrowUp size={17}/></button></form>
      <small className="chat-foot">{t('AI có thể dùng kiến thức chung; nguồn được ghi dưới từng câu trả lời. Hãy xác minh hướng dẫn tiếp nhận tại địa phương.','AI may use general knowledge; each answer shows its source. Confirm local collection guidance.')}</small>
    </aside>}
  </>;
}
