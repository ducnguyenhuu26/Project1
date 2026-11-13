import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BookOpenCheck, Search, ShieldAlert } from 'lucide-react';
import '../recommendations.css';
import { useLanguage } from '../lib/language';

type Item = { id: string; name_vi: string; category_id: string; aliases_vi: string[] };
type Choice = { id: string; label: string };
type Question = { id: string; label: string; options: Choice[] };
type Detail = { id: string; name_vi: string; questions: Question[]; notice: string };
type Result = { status: string; stream_label?: string; recommendation?: string; avoid?: string[]; cautions?: string[]; reasons?: string[]; notice?: string };
type Props = { categoryId?: string; detectedCategoryId?: string; source?: 'manual' | 'detected' | 'corrected' };
const API = (import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || '';

export function RecommendationWizard({ categoryId = '', detectedCategoryId = '', source = 'manual' }: Props) {
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [categoryOnly, setCategoryOnly] = useState(false);
  const [catalog, setCatalog] = useState<Item[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [error, setError] = useState('');
  const allAnswered = useMemo(() => detail?.questions.every(q => Boolean(answers[q.id])) ?? false, [detail, answers]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (categoryOnly && categoryId) params.set('category_id', categoryId);
    setLoadingCatalog(true);
    fetch(`${API}/api/v1/recommendations/catalog?${params}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(t('Không tải được danh mục vật thể. Hãy kiểm tra kết nối máy chủ.', 'Could not load the object catalog. Check the server connection.')); return response.json(); })
      .then(data => { setCatalog(data.items); setError(''); })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.')); })
      .finally(() => { if (!controller.signal.aborted) setLoadingCatalog(false); });
    return () => controller.abort();
  }, [query, categoryOnly, categoryId, t]);

  useEffect(() => {
    setAnswers({}); setResult(null); setDetail(null);
    if (!selected) return;
    const controller = new AbortController();
    fetch(`${API}/api/v1/recommendations/objects/${encodeURIComponent(selected)}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(t('Không tải được câu hỏi cho vật thể này.', 'Could not load questions for this object.')); return response.json(); })
      .then(setDetail)
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.')); });
    return () => controller.abort();
  }, [selected, t]);

  async function evaluate() {
    if (!selected || !allAnswered || busy) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}/api/v1/recommendations/evaluate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ object_id: selected, answers, source, detected_category_id: detectedCategoryId || undefined }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : t('Không thể tạo gợi ý xử lý.', 'Could not create a handling suggestion.'));
      setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : t('Lỗi kết nối máy chủ.', 'Server connection error.')); }
    finally { setBusy(false); }
  }

  return <section className="recommend-wizard" aria-labelledby="recommend-title">
    <div className="recommend-heading">
      <span className="recommend-eyebrow"><BookOpenCheck size={15}/> {t('TRA CỨU THEO TỪNG ĐỒ VẬT', 'ITEM-BY-ITEM GUIDANCE')}</span>
      <h3 id="recommend-title">{t('Chọn đúng món đồ để nhận hướng dẫn phù hợp', 'Choose the item for more relevant guidance')}</h3>
      <p>{t('AI chỉ gợi ý nhóm vật liệu. Hãy chọn đúng đồ vật và mô tả tình trạng để xem cách xử lý.', 'AI only suggests a material group. Select the exact item and describe its condition to see handling guidance.')}</p>
    </div>
    <div className="recommend-form-grid">
      <label className="recommend-field"><span>{t('Tìm trong 43 loại đồ vật', 'Search 43 everyday items')}</span>
        <span className="recommend-search"><Search size={17}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t('Ví dụ: vỏ chuối, áo cũ, pin…', 'For example: banana peel, old shirt, battery…')} /></span>
      </label>
      <label className="recommend-field"><span>{t('Đồ vật cần hướng dẫn', 'Item to get guidance for')}</span>
        <select value={selected} onChange={e => setSelected(e.target.value)}>
          <option value="">{t('— Chọn một đồ vật —', '— Select an item —')}</option>
          {catalog.map(item => <option value={item.id} key={item.id}>{item.name_vi}</option>)}
        </select>
      </label>
    </div>
    {categoryId && <label className="recommend-toggle"><input type="checkbox" checked={categoryOnly} onChange={e => setCategoryOnly(e.target.checked)} />
      {t(`Chỉ lọc theo nhóm vật liệu ${categoryId}`, `Filter to the ${categoryId} material group`)}</label>}
    {loadingCatalog && <p className="recommend-status" role="status">{t('Đang tải danh mục…', 'Loading catalog…')}</p>}
    {!loadingCatalog && !catalog.length && !error && <p className="recommend-status">{t('Không tìm thấy đồ vật phù hợp. Thử từ khóa khác.', 'No matching items. Try another search.')}</p>}
    {detail && <div className="recommend-questions">
      <div className="recommend-item-name">{t('ĐANG XEM XÉT', 'CURRENT ITEM')}<strong>{detail.name_vi}</strong></div>
      {detail.questions.map((q, i) => <fieldset key={q.id}><legend><span>{String(i + 1).padStart(2, '0')}</span>{q.label}</legend>
        <div className="recommend-options">{q.options.map(opt => <label key={opt.id} className={`recommend-choice${answers[q.id] === opt.id ? ' selected' : ''}`}>
          <input type="radio" name={`rec-${selected}-${q.id}`} value={opt.id} checked={answers[q.id] === opt.id}
            onChange={() => { setAnswers(a => ({ ...a, [q.id]: opt.id })); setResult(null); }} />{opt.label}
        </label>)}</div>
      </fieldset>)}
      <button type="button" className="recommend-submit" disabled={!allAnswered || busy} onClick={evaluate}>
        {busy ? t('Đang xem xét…', 'Reviewing…') : <>{t('Xem hướng xử lý', 'View handling guidance')} <ArrowRight size={16}/></>}
      </button>
    </div>}
    {error && <p role="alert" className="recommend-error"><ShieldAlert size={16}/>{error}</p>}
    {result?.status === 'complete' && <article className="recommend-result" aria-live="polite">
      <span>{t('HƯỚNG XỬ LÝ ĐỀ XUẤT', 'SUGGESTED HANDLING')}</span>
      <h4>{result.stream_label}</h4><p>{result.recommendation}</p>
      <div className="recommend-result-grid">
        <div><strong>{t('CẦN TRÁNH', 'AVOID')}</strong><ul>{result.avoid?.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        <div><strong>{t('LƯU Ý AN TOÀN', 'SAFETY NOTES')}</strong><ul>{result.cautions?.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
      </div>
      {!!result.reasons?.length && <details className="recommend-reasons"><summary>{t('Vì sao hệ thống đưa ra gợi ý này?', 'Why this suggestion?')}</summary><ul>{result.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul></details>}
      <p className="recommend-disclaimer">{result.notice}</p>
    </article>}
  </section>;
}
