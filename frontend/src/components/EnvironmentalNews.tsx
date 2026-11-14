import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Leaf, Recycle, RefreshCw, Waves, Wind } from 'lucide-react';
import { useLanguage } from '../lib/language';
import '../environmentNews.css';

type NewsItem = {
  title: string;
  summary: string;
  url: string;
  publisher: string;
  publisher_url: string;
  published_at: string | null;
  topics: string[];
  image_url?: string | null;
};
type NewsResponse = { items: NewsItem[]; updated_at: string | null; refresh_after_seconds: number; partial_failure: boolean; available: boolean };
const API = (import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || '';
const REFRESH_MS = 24 * 60 * 60 * 1000;

export function EnvironmentalNews() {
  const { language, t } = useLanguage();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [failed, setFailed] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  const hasItemsRef = useRef(false);

  async function load(force = false) {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    if (hasItemsRef.current) setRefreshing(true);
    else setLoading(true);
    try {
      const response = await fetch(`${API}/api/v1/news/environment${force ? '?refresh=true' : ''}`, { signal: controller.signal });
      if (!response.ok) throw new Error('news request failed');
      const data = await response.json() as NewsResponse;
      setItems(data.items ?? []);
      hasItemsRef.current = Boolean(data.items?.length);
      setUpdatedAt(data.updated_at ?? null);
      setFailed(!data.available);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setFailed(true);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
        requestRef.current = null;
      }
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => {
      window.clearInterval(timer);
      requestRef.current?.abort();
    };
  }, []);

  const formatDate = (value: string | null) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '' : date.toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' });
  };
  const TopicIcon = ({ topics }: { topics: string[] }) => {
    const topic = topics[0] ?? '';
    if (topic.includes('tái chế') || topic.includes('nhựa')) return <Recycle size={40} strokeWidth={1.4} aria-hidden="true"/>;
    if (topic.includes('ô nhiễm')) return <Wind size={40} strokeWidth={1.4} aria-hidden="true"/>;
    if (topic.includes('khí hậu')) return <Waves size={40} strokeWidth={1.4} aria-hidden="true"/>;
    return <Leaf size={40} strokeWidth={1.4} aria-hidden="true"/>;
  };

  return <section className="environment-news" aria-labelledby="environment-news-title">
    <div className="environment-news-head">
      <h3 id="environment-news-title">{t('TIN MỚI NHẤT HÔM NAY', "TODAY'S LATEST NEWS")}</h3>
      <div className="environment-news-tools">
        <span className="environment-news-autorefresh"><i aria-hidden="true"/> {t('TỰ CẬP NHẬT HẰNG NGÀY', 'DAILY AUTO-UPDATE')}</span>
        <button type="button" onClick={() => void load(true)} disabled={loading || refreshing} aria-label={t('Cập nhật tin ngay','Refresh news now')}>
          <RefreshCw size={15} className={refreshing ? 'spinning' : ''}/>{t('Làm mới','Refresh')}
        </button>
      </div>
    </div>
    <div className="environment-news-meta" aria-live="polite">
      {loading ? t('Đang lấy tin từ các nguồn…','Loading feeds…') : updatedAt ? `${t('Cập nhật gần nhất','Last refreshed')}: ${formatDate(updatedAt)}` : ''}
      {failed && <span>{t('Một số nguồn chưa phản hồi. Hãy thử làm mới sau.','Some feeds are unavailable. Try again later.')}</span>}
    </div>
    {items.length > 0 ? <div className="environment-news-grid">
      {items.slice(0, 12).map((item, index) => <a className="environment-news-card" href={item.url} target="_blank" rel="noreferrer" key={`${item.url}-${index}`} aria-label={`${item.title} (${item.publisher})`}>
        <div className="environment-news-image">
          {item.image_url ? <img src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true; event.currentTarget.nextElementSibling?.classList.add('is-visible'); }}/>: null}
          <div className={`environment-news-image-fallback${item.image_url ? '' : ' is-visible'}`} aria-hidden="true"><TopicIcon topics={item.topics}/><span>{item.topics[0] ?? t('MÔI TRƯỜNG','ENVIRONMENT')}</span></div>
          <span className="environment-news-badge">{t('TIN BÀI','NEWS')}</span>
        </div>
        <div className="environment-news-card-body">
          <div className="environment-news-card-meta"><span>{item.publisher}</span>{item.published_at && <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>}</div>
          <h4>{item.title}<ExternalLink size={13} aria-hidden="true"/></h4>
          {item.summary && <p>{item.summary}</p>}
          <div className="environment-news-topics">{item.topics.slice(0, 2).map(topic => <span key={topic}>{topic}</span>)}</div>
        </div>
      </a>)}
    </div> : !loading && <p className="environment-news-empty">
      {failed ? t('Chưa tải được tin. Kiểm tra kết nối máy chủ rồi thử lại.','News could not be loaded. Check the server and try again.') : t('Chưa tìm thấy bài mới phù hợp từ các nguồn RSS.','No recent matching articles were found in the RSS feeds.')}
    </p>}
    <p className="environment-news-footnote">{t('Chỉ hiển thị tiêu đề và đoạn trích RSS; nội dung đầy đủ thuộc về báo/đơn vị xuất bản. SOICTERRA không xác nhận độc lập từng bài.', 'Only RSS headlines and excerpts are shown; full articles remain with their publishers. SOICTERRA does not independently verify each article.')}</p>
  </section>;
}
