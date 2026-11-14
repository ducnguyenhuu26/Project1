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
import { getHealth, getKnowledge, postChat, postRegionScan, postScan } from './lib/api';
import type { Region } from './lib/region';
import { mergeRegionScan } from './lib/regionScan';
import type { ChatMessage, Detection, Health, HistoryEntry, Knowledge, Scan } from './types';
import './style.css';
import { LanguageProvider, useLanguage } from './lib/language';

const allowedTypes=['image/jpeg','image/png','image/webp'];
const initialChat:ChatMessage[]=[{role:'assistant',text:'Chào bạn! Hỏi mình về nhựa, giấy, kim loại hoặc cách xử lý rác nhé.'}];
function readHistory():HistoryEntry[]{try{const value=JSON.parse(localStorage.getItem('wastewise-history')||'[]');return Array.isArray(value)?value:[];}catch{return[];}}
function saveHistory(value:HistoryEntry[]){try{localStorage.setItem('wastewise-history',JSON.stringify(value));}catch{/* Local history is an optional convenience. */}}

function App(){
  const { language, t } = useLanguage();
  const[knowledge,setKnowledge]=useState<Knowledge|null>(null);const[health,setHealth]=useState<Health|null>(null);const[healthError,setHealthError]=useState(false);const[libraryError,setLibraryError]=useState(false);
  const[file,setFile]=useState<File|null>(null);const[preview,setPreview]=useState('');const[scan,setScan]=useState<Scan|null>(null);const[selected,setSelected]=useState<string|null>(null);
  const[manual,setManual]=useState<string[]>([]);const[excluded,setExcluded]=useState<string[]>([]);const[corrections,setCorrections]=useState<Record<string,string>>({});const[busy,setBusy]=useState(false);const[error,setError]=useState('');
  const[regionBusy,setRegionBusy]=useState(false);const[regionError,setRegionError]=useState('');
  const[chat,setChat]=useState<ChatMessage[]>(()=>language==='en'?[{role:'assistant',text:'Hello! Ask me about plastic, paper, metal, or waste handling.'}]:initialChat);const[chatBusy,setChatBusy]=useState(false);const[history,setHistory]=useState<HistoryEntry[]>(readHistory);const[scanId,setScanId]=useState<string|null>(null);
  const requestRef=useRef<AbortController|null>(null);const regionRequestRef=useRef<AbortController|null>(null);const requestVersion=useRef(0);
  useEffect(()=>{getKnowledge().then(setKnowledge).catch(()=>setLibraryError(true));getHealth().then(setHealth).catch(()=>setHealthError(true));return()=>{requestRef.current?.abort();regionRequestRef.current?.abort();};},[]);
  useEffect(()=>{if(!file){setPreview('');return;}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url);},[file]);
  const materials=knowledge?.materials??[];
  const supportedIds=scan?.supported_category_ids??health?.supported_category_ids??knowledge?.categories.filter(c=>c.detection_supported).map(c=>c.id)??[];
  const active=useMemo(()=>[...new Set([...(scan?.detections.filter(d=>!excluded.includes(d.id)).map(d=>corrections[d.id]??d.category_id).filter((id):id is string=>!!id)??[]),...manual])],[scan,excluded,corrections,manual]);

  function choose(next:File){
    requestVersion.current++;requestRef.current?.abort();requestRef.current=null;regionRequestRef.current?.abort();setRegionBusy(false);setRegionError('');setBusy(false);
    if(!allowedTypes.includes(next.type)){setError(t('Chỉ nhận ảnh JPEG, PNG hoặc WebP.','Only JPEG, PNG, or WebP images are accepted.'));return false;}
    if(next.size>10*1024*1024){setError(t('Ảnh phải nhỏ hơn 10 MB.','Image must be smaller than 10 MB.'));return false;}
    setError('');setFile(next);setScan(null);setManual([]);setExcluded([]);setCorrections({});setSelected(null);setScanId(null);return true;
  }
  async function analyzeFile(target:File){
    requestRef.current?.abort();regionRequestRef.current?.abort();setRegionBusy(false);setRegionError('');const version=++requestVersion.current;const controller=new AbortController();requestRef.current=controller;setBusy(true);setError('');setFile(target);setScan(null);setManual([]);setExcluded([]);setCorrections({});setSelected(null);
    const timeout=window.setTimeout(()=>controller.abort(),60_000);
    try{
      const result=await postScan(target,controller.signal);if(version!==requestVersion.current)return;
      setScan(result);setSelected(result.detections[0]?.id??'manual');const id=crypto.randomUUID();setScanId(id);const detected=result.detections.map(d=>d.category_id).filter((v):v is string=>!!v);const next=[{id,when:new Date().toLocaleString('vi-VN'),detected,final:detected,corrected:false},...history].slice(0,12);setHistory(next);saveHistory(next);
    }catch(e){if(version!==requestVersion.current)return;setError(e instanceof DOMException&&e.name==='AbortError'?t('Quá thời gian chờ phân tích (60 giây). Hãy thử lại với ảnh nhỏ hơn.','Analysis timed out (60 seconds). Try a smaller image.'):e instanceof TypeError?t('Không kết nối được máy chủ. Kiểm tra API rồi thử lại.','Could not connect to the server. Check the API and try again.'):e instanceof Error?e.message:t('Đã có lỗi xảy ra. Hãy thử lại.','Something went wrong. Please try again.'));}
    finally{window.clearTimeout(timeout);if(version===requestVersion.current){setBusy(false);requestRef.current=null;}}
  }
  function analyze(){if(file&&!busy)void analyzeFile(file);}
  async function analyzeRegion(box:Region){
    if(!file||!scan||regionBusy)return;
    regionRequestRef.current?.abort();const controller=new AbortController();regionRequestRef.current=controller;
    const version=requestVersion.current;setRegionBusy(true);setRegionError('');
    const timeout=window.setTimeout(()=>{controller.abort();if(version===requestVersion.current)setRegionError('Nhận diện lại vùng quá 60 giây. Hãy thử vùng nhỏ hơn hoặc tra cứu KB thủ công.');},60_000);
    try{
      const result=await postRegionScan(file,box,controller.signal);
      if(version!==requestVersion.current||controller.signal.aborted)return;
      const merged=mergeRegionScan(scan,result,box,()=>crypto.randomUUID());
      setScan(merged.scan);
      setSelected(merged.added[0].id);
    }catch(e){
      if(version!==requestVersion.current||controller.signal.aborted)return;
      setRegionError(e instanceof Error?e.message:'Không thể nhận diện lại vùng khoanh. Hãy thử lại hoặc tra cứu KB thủ công.');
    }finally{window.clearTimeout(timeout);if(version===requestVersion.current){setRegionBusy(false);regionRequestRef.current=null;}}
  }
  async function runDemo(){
    if(busy||regionBusy)return;
    document.getElementById('studio')?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
    try{const response=await fetch('/sample.png');if(!response.ok)throw new Error();const blob=await response.blob();const demo=new File([blob],'wastewise-sample.png',{type:'image/png'});if(choose(demo))void analyzeFile(demo);}
    catch{setError(t('Không tải được ảnh minh họa. Hãy chọn một ảnh từ thiết bị.','Could not load the sample image. Choose an image from your device.'));document.getElementById('studio')?.scrollIntoView({behavior:'smooth',block:'start'});}
  }
  function updateHistory(ids:string[]){if(!scanId)return;setHistory(previous=>{const next=previous.map(item=>item.id===scanId?{...item,final:ids,corrected:ids.slice().sort().join('|')!==(item.detected??[]).slice().sort().join('|')}:item);saveHistory(next);return next;});}
  function correctObject(d:Detection,id:string){const next={...corrections,[d.id]:id};setCorrections(next);setSelected(d.id);const adjusted=(scan?.detections??[]).filter(item=>!excluded.includes(item.id)).map(item=>next[item.id]??item.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...adjusted,...manual])]);}
  function excludeObject(id:string){const nextExcluded=[...excluded,id];setExcluded(nextExcluded);if(selected===id)setSelected(scan?.detections.find(d=>!nextExcluded.includes(d.id))?.id??'manual');const remaining=(scan?.detections??[]).filter(item=>!nextExcluded.includes(item.id)).map(item=>corrections[item.id]??item.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...remaining,...manual])]);}
  function toggleManual(id:string){const next=manual.includes(id)?manual.filter(value=>value!==id):[...manual,id];setManual(next);setSelected('manual');const detected=(scan?.detections??[]).filter(d=>!excluded.includes(d.id)).map(d=>corrections[d.id]??d.category_id).filter((v):v is string=>!!v);updateHistory([...new Set([...detected,...next])]);}
  async function ask(message:string){if(chatBusy)return;const history=chat.slice(-8);setChat(v=>[...v,{role:'user',text:message}]);setChatBusy(true);try{const answer=await postChat(message,active,history);setChat(v=>[...v,{role:'assistant',text:answer.answer||t('Chưa có câu trả lời.','No answer is available yet.'),source:answer.assistant,groundedIn:answer.grounded_in}]);}catch{setChat(v=>[...v,{role:'assistant',text:t('Trợ lý tra cứu hiện không kết nối được.','The assistant is currently unavailable.') }]);}finally{setChatBusy(false);}}
  function clearHistory(){try{localStorage.removeItem('wastewise-history');}catch{/* Local history is optional. */}setHistory([]);}

  return <><SiteHeader/><main id="main-content">
    <Hero onSample={runDemo} supportedCount={supportedIds.length}/>
    <StorySection/><MissionSection/>
    <ScanStudio file={file} preview={preview} scan={scan} scanContextKey={scanId} materials={materials} supportedIds={supportedIds} busy={busy} error={error} regionBusy={regionBusy} regionError={regionError} onRegion={analyzeRegion} onChoose={choose} onAnalyze={analyze} onDemo={runDemo} onCorrect={correctObject} onExclude={excludeObject} onSelect={setSelected} selected={selected} onManual={toggleManual} active={active} manual={manual} corrections={corrections} excluded={excluded}/>
    {libraryError&&<p className="connection-notice" role="status">{t('Không tải được thư viện kiến thức từ API. Hãy kiểm tra kết nối để tra cứu.','Could not load the knowledge library from the API. Check your connection to browse it.')}</p>}
    <TechnologySection health={healthError?null:health} scan={scan} supportedIds={supportedIds}/>
    <KnowledgeSections knowledge={knowledge} supportedIds={supportedIds}/><TeamSection/><ClosingSection/>
  </main><SiteFooter history={history} materials={materials} onClear={clearHistory}/><ChatAssistant messages={chat} busy={chatBusy} onAsk={ask}/></>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><LanguageProvider><App/></LanguageProvider></StrictMode>);
