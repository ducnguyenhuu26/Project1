import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, BookOpenCheck, Search, ShieldAlert } from 'lucide-react';
import '../recommendations.css';
import { useLanguage } from '../lib/language';
import { API_BASE } from '../lib/apiBase';
import type { ItemSession } from '../types';

type Item = { id: string; name_vi: string; category_id: string; aliases_vi: string[] };
type Choice = { id: string; label: string };
type Question = { id: string; label: string; options: Choice[] };
type Detail = { id: string; name_vi: string; category_id: string; questions: Question[]; notice: string; headline?: string; review_status?: string };
type CatalogResponse = { items: Item[]; count: number; total_count: number };
type Props = { categoryId?: string; detectedCategoryId?: string; source?: 'manual' | 'detected' | 'corrected'; session: ItemSession; onSessionChange: (next: ItemSession) => void };
const API = API_BASE;

export function RecommendationWizard({ categoryId = '', detectedCategoryId = '', source = 'manual', session, onSessionChange }: Props) {
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [categoryOnly, setCategoryOnly] = useState(false);
  const [catalog, setCatalog] = useState<Item[]>([]);
  const [catalogTotal, setCatalogTotal] = useState(0);
  const selected = session.confirmedObjectId;
  const answers = session.answers;
  const result = session.recommendation;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [evaluationError, setEvaluationError] = useState('');
  const evaluationRequest = useRef(0);
  const evaluationController = useRef<AbortController | null>(null);
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const allAnswered = useMemo(() => detail?.questions.every(q => Boolean(answers[q.id])) ?? false, [detail, answers]);

  function invalidateEvaluation() {
    evaluationRequest.current += 1;
    evaluationController.current?.abort();
    evaluationController.current = null;
    setBusy(false);
  }

  function chooseObject(id: string) {
    invalidateEvaluation();
    onSessionChange({confirmedObjectId:id,answers:{},recommendation:null});
    setDetail(null);
    setDetailError('');
    setEvaluationError('');
  }

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    params.set('limit', '200');
    if (query.trim()) params.set('q', query.trim());
    if (categoryOnly && categoryId) params.set('category_id', categoryId);
    setLoadingCatalog(true);
    setCatalogError('');
    fetch(`${API}/api/v1/recommendations/catalog?${params}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(t('Không tải được danh mục vật thể. Hãy kiểm tra kết nối máy chủ.', 'Could not load the object catalog. Check the server connection.')); return response.json() as Promise<CatalogResponse>; })
      .then(data => { setCatalog([...data.items].sort((a,b)=>Number(b.category_id===categoryId)-Number(a.category_id===categoryId))); setCatalogTotal(data.total_count ?? data.count); })
      .catch(e => { if (!controller.signal.aborted) setCatalogError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.')); })
      .finally(() => { if (!controller.signal.aborted) setLoadingCatalog(false); });
    return () => controller.abort();
  }, [query, categoryOnly, categoryId, t]);

  useEffect(() => {
    setDetail(null);
    setDetailError('');
    if (!selected) { setLoadingDetail(false); return; }
    const controller = new AbortController();
    setLoadingDetail(true);
    fetch(`${API}/api/v1/recommendations/objects/${encodeURIComponent(selected)}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(t('Không tải được câu hỏi cho vật thể này.', 'Could not load questions for this item.')); return response.json() as Promise<Detail>; })
      .then(data => { setDetail(data); })
      .catch(e => { if (!controller.signal.aborted) setDetailError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.')); })
      .finally(() => { if (!controller.signal.aborted) setLoadingDetail(false); });
    return () => controller.abort();
  }, [selected, t]);

  useEffect(() => {
    return () => {
      evaluationRequest.current += 1;
      evaluationController.current?.abort();
      evaluationController.current = null;
    };
  }, []);

  function answerQuestion(questionId: string, optionId: string) {
    invalidateEvaluation();
    onSessionChange({...session,answers:{...answers,[questionId]:optionId},recommendation:null});
    setEvaluationError('');
  }

  async function evaluate() {
    if (!selected || !allAnswered || busy) return;
    const requestId = ++evaluationRequest.current;
    const controller = new AbortController();
    evaluationController.current?.abort();
    evaluationController.current = controller;
    const requestSnapshot = { selected, answers: { ...answers }, source, detectedCategoryId };
    setBusy(true);
    setEvaluationError('');
    onSessionChange({...session,recommendation:null});
    try {
      const response = await fetch(`${API}/api/v1/recommendations/evaluate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ object_id: requestSnapshot.selected, answers: requestSnapshot.answers,
          source: requestSnapshot.source, detected_category_id: requestSnapshot.detectedCategoryId || undefined }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : t('Không thể tạo gợi ý xử lý.', 'Could not create a handling suggestion.'));
      if (requestId === evaluationRequest.current && sessionRef.current.confirmedObjectId===requestSnapshot.selected && JSON.stringify(sessionRef.current.answers)===JSON.stringify(requestSnapshot.answers)) onSessionChange({...sessionRef.current,recommendation:data});
    } catch (e) {
      if (!controller.signal.aborted && requestId === evaluationRequest.current)
        setEvaluationError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.'));
    } finally {
      if (requestId === evaluationRequest.current) {
        setBusy(false);
        evaluationController.current = null;
      }
    }
  }

  const selectedOptionIsInCatalog = catalog.some(item => item.id === selected);
  return <section className="recommend-wizard" aria-labelledby="recommend-title">
    <div className="recommend-heading">
      <span className="recommend-eyebrow"><BookOpenCheck size={15}/> {t('TRA CỨU THEO TỪNG ĐỒ VẬT', 'ITEM-BY-ITEM GUIDANCE')}</span>
      <h3 id="recommend-title">{t('Chọn đúng món đồ để nhận hướng dẫn phù hợp', 'Choose the item for more relevant guidance')}</h3>
      <p>{t('AI chỉ gợi ý nhóm vật liệu. Hãy chọn đúng đồ vật và mô tả tình trạng để xem cách xử lý.', 'AI only suggests a material group. Select the exact item and describe its condition to see handling guidance.')}</p>
    </div>
    <div className="recommend-form-grid">
      <label className="recommend-field"><span>{t(`Tìm trong ${catalogTotal || '…'} loại đồ vật`, `Search ${catalogTotal || '…'} everyday items`)}</span>
        <span className="recommend-search"><Search size={17}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t('Ví dụ: vỏ chuối, áo cũ, pin…', 'For example: banana peel, old shirt, battery…')} /></span>
      </label>
      <label className="recommend-field"><span>{t('Đồ vật cần hướng dẫn', 'Item to get guidance for')}</span>
        <select value={selected} onChange={e => chooseObject(e.target.value)}>
          <option value="">{t('— Chọn một đồ vật —', '— Select an item —')}</option>
          {selected && detail && !selectedOptionIsInCatalog && <option value={selected}>{detail.name_vi} · {t('đang chọn', 'selected')}</option>}
          {catalog.map(item => <option value={item.id} key={item.id}>{item.name_vi}</option>)}
        </select>
      </label>
    </div>
    {categoryId && <label className="recommend-toggle"><input type="checkbox" checked={categoryOnly} onChange={e => setCategoryOnly(e.target.checked)} />
      {t(`Chỉ lọc theo nhóm vật liệu ${categoryId}`, `Filter to the ${categoryId} material group`)}</label>}
    {categoryOnly&&<button type="button" className="textbtn" onClick={()=>setCategoryOnly(false)}>Không tìm thấy / tra cứu toàn bộ</button>}
    {loadingCatalog && <p className="recommend-status" role="status">{t('Đang tải danh mục…', 'Loading catalog…')}</p>}
    {!loadingCatalog && !catalog.length && !catalogError && <p className="recommend-status">{t('Không tìm thấy đồ vật phù hợp. Thử từ khóa khác.', 'No matching items. Try another search.')}</p>}
    {catalogError && <p role="alert" className="recommend-error"><ShieldAlert size={16}/>{catalogError}</p>}
    {loadingDetail && <p className="recommend-status" role="status">{t('Đang tải câu hỏi…', 'Loading questions…')}</p>}
    {detailError && <p role="alert" className="recommend-error"><ShieldAlert size={16}/>{detailError}</p>}
    {detail && <div className="recommend-questions">
      <div className="recommend-item-name">{t('ĐANG XEM XÉT', 'CURRENT ITEM')}<strong>{detail.name_vi}</strong></div>
      {source === 'corrected' && detectedCategoryId && <p className="recommend-provenance" role="status">{t(`YOLO ban đầu gợi ý nhóm ${detectedCategoryId}; bạn đã hiệu chỉnh. Hướng dẫn bên dưới dựa trên đồ vật bạn chọn.`, `YOLO originally suggested the ${detectedCategoryId} group; you corrected it. Guidance below follows the item you selected.`)}</p>}
      {source === 'detected' && detectedCategoryId && <p className="recommend-provenance" role="status">{t(`Nhóm ${detectedCategoryId} là gợi ý từ YOLO, không phải xác nhận vật thể. Hướng dẫn bên dưới dựa trên đồ vật bạn chọn.`, `The ${detectedCategoryId} group is a YOLO hint, not an object confirmation. Guidance below follows the item you selected.`)}</p>}
      {source === 'manual' && <p className="recommend-provenance">{t('Tra cứu thủ công theo vật thể bạn đã chọn.', 'Manual lookup for the item you selected.')}</p>}
      {categoryId&&detail.category_id!==categoryId&&<p className="recommend-provenance" role="status">Đồ vật đã chọn thuộc nhóm {detail.category_id}, khác nhóm gợi ý {categoryId}. Hướng dẫn dựa trên đồ vật bạn xác nhận.</p>}
      {detail.questions.map((q, i) => <fieldset key={q.id}><legend><span>{String(i + 1).padStart(2, '0')}</span>{q.label}</legend>
        <div className="recommend-options">{q.options.map(opt => <label key={opt.id} className={`recommend-choice${answers[q.id] === opt.id ? ' selected' : ''}`}>
          <input type="radio" name={`rec-${selected}-${q.id}`} value={opt.id} checked={answers[q.id] === opt.id}
            onChange={() => answerQuestion(q.id, opt.id)} />{opt.label}
        </label>)}</div>
      </fieldset>)}
      <button type="button" className="recommend-submit" disabled={!allAnswered || busy || loadingDetail} onClick={evaluate}>
        {busy ? t('Đang xem xét…', 'Reviewing…') : <>{t('Xem hướng xử lý', 'View handling guidance')} <ArrowRight size={16}/></>}
      </button>
    </div>}
    {evaluationError && <p role="alert" className="recommend-error"><ShieldAlert size={16}/>{evaluationError}</p>}
    {result?.status === 'complete' && <article className="recommend-result" aria-live="polite">
      <span>{t('HƯỚNG XỬ LÝ ĐỀ XUẤT', 'SUGGESTED HANDLING')}</span>
      <h4>{result.headline || result.stream_label}</h4>
      {result.assessment && <p>{result.assessment}</p>}
      <p><strong>{result.stream_label}</strong></p>
      {result.recommendation&&<p>{result.recommendation}</p>}
      {result.context_response&&result.context_response!==result.recommendation&&<p>{result.context_response}</p>}
      <div className="recommend-result-grid">
        <div><strong>{t('CẦN TRÁNH', 'AVOID')}</strong><ul>{result.avoid?.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        <div><strong>{t('LƯU Ý AN TOÀN', 'SAFETY NOTES')}</strong><ul>{result.cautions?.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
      </div>
      {!!result.practical_steps?.length && <div className="recommend-reasons"><strong>{t('Các bước thực hiện', 'Practical steps')}</strong>
        <ol>{result.practical_steps.map((x, i) => <li key={i}>{x}</li>)}</ol>
        {result.why && <p>{result.why}</p>}{result.next_step && <p><strong>{t('Tiếp theo:', 'Next:')}</strong> {result.next_step}</p>}
        {!!result.sources?.length && <><p>{t('Nguồn nguyên tắc chung; chưa xác minh tuyến thu gom tại địa phương:', 'General-principle references; local collection is not verified:')}</p>
          <ul>{result.sources.map(source => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.id} · {source.title}</a> ({source.scope})</li>)}</ul></>}
      </div>}
      {!!result.reasons?.length && <details className="recommend-reasons"><summary>{t('Vì sao hệ thống đưa ra gợi ý này?', 'Why this suggestion?')}</summary><ul>{result.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul></details>}
      <p className="recommend-disclaimer">{result.notice} {result.review_status === 'pending_human_review' && t('Nội dung đang chờ rà soát chuyên môn; đây là hướng dẫn tham khảo.', 'Content is pending expert review and is provided as general guidance.')}</p>
    </article>}
  </section>;
}
