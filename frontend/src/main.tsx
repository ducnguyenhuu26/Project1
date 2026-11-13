import { StrictMode, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { SiteHeader } from './components/SiteHeader';
import { Hero } from './components/Hero';
import { StorySection } from './components/StorySection';
import { MissionSection } from './components/MissionSection';
import { ScanStudio } from './components/ScanStudio';
import { TechnologySection } from './components/TechnologySection';
import { KnowledgeSections } from './components/KnowledgeSections';
import { TeamSection } from './components/TeamSection';
import { ClosingSection } from './components/ClosingSection';
import { SiteFooter } from './components/SiteFooter';
import { ChatAssistant } from './components/ChatAssistant';
import { getHealth, getKnowledge, postChat, postScan } from './lib/api';
import type { ChatMessage, Detection, Health, HistoryEntry, Knowledge, Scan } from './types';
import './style.css';

const allowedTypes=['image/jpeg','image/png','image/webp'];
const initialChat:ChatMessage[]=[{role:'assistant',text:'Chào bạn! Hỏi mình về nhựa, giấy, kim loại hoặc cách xử lý rác nhé.'}];
function readHistory():HistoryEntry[]{try{const value=JSON.parse(localStorage.getItem('wastewise-history')||'[]');return Array.isArray(value)?value:[];}catch{return[];}}
function saveHistory(value:HistoryEntry[]){try{localStorage.setItem('wastewise-history',JSON.stringify(value));}catch{/* Local history is an optional convenience. */}}

function App(){
  const[knowledge,setKnowledge]=useState<Knowledge|null>(null);const[health,setHealth]=useState<Health|null>(null);const[healthError,setHealthError]=useState(false);const[libraryError,setLibraryError]=useState(false);
  const[file,setFile]=useState<File|null>(null);const[preview,setPreview]=useState('');const[scan,setScan]=useState<Scan|null>(null);const[selected,setSelected]=useState<string|null>(null);
  const[manual,setManual]=useState<string[]>([]);const[excluded,setExcluded]=useState<string[]>([]);const[corrections,setCorrections]=useState<Record<string,string>>({});const[busy,setBusy]=useState(false);const[error,setError]=useState('');
  const[chat,setChat]=useState<ChatMessage[]>(initialChat);const[chatBusy,setChatBusy]=useState(false);const[history,setHistory]=useState<HistoryEntry[]>(readHistory);const[scanId,setScanId]=useState<string|null>(null);
  const requestRef=useRef<AbortController|null>(null);const requestVersion=useRef(0);
  useEffect(()=>{getKnowledge().then(setKnowledge).catch(()=>setLibraryError(true));getHealth().then(setHealth).catch(()=>setHealthError(true));return()=>requestRef.current?.abort();},[]);
  useEffect(()=>{if(!file){setPreview('');return;}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url);},[file]);
  const materials=knowledge?.materials??[];
  const supportedIds=scan?.supported_category_ids??health?.supported_category_ids??knowledge?.categories.filter(c=>c.detection_supported).map(c=>c.id)??[];
  const active=useMemo(()=>[...new Set([...(scan?.detections.filter(d=>!excluded.includes(d.id)).map(d=>corrections[d.id]??d.category_id).filter((id):id is string=>!!id)??[]),...manual])],[scan,excluded,corrections,manual]);

  function choose(next:File){
    requestVersion.current++;requestRef.current?.abort();requestRef.current=null;setBusy(false);
    if(!allowedTypes.includes(next.type)){setError('Chỉ nhận ảnh JPEG, PNG hoặc WebP.');return false;}
    if(next.size>10*1024*1024){setError('Ảnh phải nhỏ hơn 10 MB.');return false;}
    setError('');setFile(next);setScan(null);setManual([]);setExcluded([]);setCorrections({});setSelected(null);setScanId(null);return true;
  }
  async function analyzeFile(target:File){
    requestRef.current?.abort();const version=++requestVersion.current;const controller=new AbortController();requestRef.current=controller;setBusy(true);setError('');setFile(target);setScan(null);setManual([]);setExcluded([]);setCorrections({});setSelected(null);
    const timeout=window.setTimeout(()=>controller.abort(),60_000);
    try{
      const result=await postScan(target,controller.signal);if(version!==requestVersion.current)return;
      setScan(result);setSelected(result.detections[0]?.category_id??null);const id=crypto.randomUUID();setScanId(id);const detected=result.detections.map(d=>d.category_id).filter((v):v is string=>!!v);const next=[{id,when:new Date().toLocaleString('vi-VN'),detected,final:detected,corrected:false},...history].slice(0,12);setHistory(next);saveHistory(next);
    }catch(e){if(version!==requestVersion.current)return;setError(e instanceof DOMException&&e.name==='AbortError'?'Quá thời gian chờ phân tích (60 giây). Hãy thử lại với ảnh nhỏ hơn.':e instanceof TypeError?'Không kết nối được máy chủ. Kiểm tra API rồi thử lại.':e instanceof Error?e.message:'Đã có lỗi xảy ra. Hãy thử lại.');}
    finally{window.clearTimeout(timeout);if(version===requestVersion.current){setBusy(false);requestRef.current=null;}}
  }
  function analyze(){if(file&&!busy)void analyzeFile(file);}
  async function runDemo(){
    if(busy)return;
    document.getElementById('studio')?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
    try{const response=await fetch('/sample.png');if(!response.ok)throw new Error();const blob=await response.blob();const demo=new File([blob],'wastewise-sample.png',{type:'image/png'});if(choose(demo))void analyzeFile(demo);}
    catch{setError('Không tải được ảnh minh họa. Hãy chọn một ảnh từ thiết bị.');document.getElementById('studio')?.scrollIntoView({behavior:'smooth',block:'start'});}
  }
  function updateHistory(ids:string[]){if(!scanId)return;setHistory(previous=>{const next=previous.map(item=>item.id===scanId?{...item,final:ids,corrected:ids.slice().sort().join('|')!==(item.detected??[]).slice().sort().join('|')}:item);saveHistory(next);return next;});}
  function correctObject(d:Detection,id:string){const next={...corrections,[d.id]:id};setCorrections(next);setSelected(id||null);const adjusted=(scan?.detections??[]).filter(item=>!excluded.includes(item.id)).map(item=>next[item.id]??item.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...adjusted,...manual])]);}
  function excludeObject(id:string){const nextExcluded=[...excluded,id];setExcluded(nextExcluded);const remaining=(scan?.detections??[]).filter(item=>!nextExcluded.includes(item.id)).map(item=>corrections[item.id]??item.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...remaining,...manual])]);}
  function toggleManual(id:string){const next=manual.includes(id)?manual.filter(value=>value!==id):[...manual,id];setManual(next);setSelected(id);const detected=(scan?.detections??[]).filter(d=>!excluded.includes(d.id)).map(d=>corrections[d.id]??d.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...detected,...next])]);}
  async function ask(message:string){if(chatBusy)return;setChat(v=>[...v,{role:'user',text:message}]);setChatBusy(true);try{const answer=await postChat(message,active);setChat(v=>[...v,{role:'assistant',text:answer.answer||'Chưa có câu trả lời.'}]);}catch{setChat(v=>[...v,{role:'assistant',text:'Trợ lý tra cứu hiện không kết nối được.'}]);}finally{setChatBusy(false);}}
  function clearHistory(){try{localStorage.removeItem('wastewise-history');}catch{/* Local history is optional. */}setHistory([]);}

  return <><SiteHeader/><main id="main-content">
    <Hero onSample={runDemo} supportedCount={supportedIds.length}/>
    <StorySection/><MissionSection/>
    <ScanStudio file={file} preview={preview} scan={scan} materials={materials} supportedIds={supportedIds} busy={busy} error={error} onChoose={choose} onAnalyze={analyze} onDemo={runDemo} onCorrect={correctObject} onExclude={excludeObject} onSelect={setSelected} selected={selected} onManual={toggleManual} active={active} manual={manual} corrections={corrections} excluded={excluded}/>
    {libraryError&&<p className="connection-notice" role="status">Không tải được thư viện kiến thức từ API. Hãy kiểm tra kết nối để tra cứu.</p>}
    <TechnologySection health={healthError?null:health} knowledge={knowledge} scan={scan} supportedIds={supportedIds}/>
    <KnowledgeSections knowledge={knowledge} supportedIds={supportedIds}/><TeamSection/><ClosingSection/>
  </main><SiteFooter history={history} materials={materials} onClear={clearHistory}/><ChatAssistant messages={chat} busy={chatBusy} onAsk={ask}/></>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
