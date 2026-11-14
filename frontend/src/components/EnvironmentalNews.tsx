import { useEffect, useRef, useState } from 'react';
import { Camera, ChevronLeft, ChevronRight, ExternalLink, Flame, Recycle, RefreshCw, Trash2, Waves, Wind } from 'lucide-react';
import { useLanguage } from '../lib/language';
import { API_BASE } from '../lib/apiBase';
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
type NewsResponse = {
  items: NewsItem[];
  latest_items?: NewsItem[];
  older_items?: NewsItem[];
  updated_at: string | null;
  refresh_after_seconds: number;
  partial_failure: boolean;
  available: boolean;
};
const API = API_BASE;
const REFRESH_MS = 24 * 60 * 60 * 1000;

function TopicIcon({ topics, title }: { topics: string[]; title: string }) {
  const topic = topics[0] ?? '';
  if (title.includes('camera')) return <Camera size={40} strokeWidth={1.4} aria-hidden="true"/>;
  if (title.includes('đốt')) return <Flame size={40} strokeWidth={1.4} aria-hidden="true"/>;
  if (title.includes('biển') || title.includes('kênh')) return <Waves size={40} strokeWidth={1.4} aria-hidden="true"/>;
  if (topic.includes('nhựa') || topic.includes('tái chế')) return <Recycle size={40} strokeWidth={1.4} aria-hidden="true"/>;
  if (topic.includes('ô nhiễm')) return <Wind size={40} strokeWidth={1.4} aria-hidden="true"/>;
  return <Trash2 size={40} strokeWidth={1.4} aria-hidden="true"/>;
}

export function EnvironmentalNews() {
  const { language, t } = useLanguage();
  const [latestItems, setLatestItems] = useState<NewsItem[]>([]);
  const [olderItems, setOlderItems] = useState<NewsItem[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [failed, setFailed] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  const latestSlider = useRef<HTMLDivElement>(null);
  const olderSlider = useRef<HTMLDivElement>(null);
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
      const latest = data.latest_items ?? data.items.slice(0, 10);
      const older = data.older_items ?? data.items.slice(10, 25);
      setLatestItems(latest);
      setOlderItems(older);
      hasItemsRef.current = Boolean(latest.length || older.length);
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
  const moveSlider = (slider: { current: HTMLDivElement | null }, direction: number) => {
    slider.current?.scrollBy({ left: slider.current.clientWidth * 0.8 * direction, behavior: 'smooth' });
  };
  const renderCarousel = (title: string, rows: NewsItem[], id: string, slider: { current: HTMLDivElement | null }) =>
    <section className="environment-news-row" aria-labelledby={`${id}-title`}>
      <div className="environment-news-row-head">
        <h4 id={`${id}-title`}>{title}<span>{rows.length}</span></h4>
        <div className="environment-news-slider-controls">
          <button type="button" onClick={() => moveSlider(slider, -1)} aria-label={t('Trượt sang trái','Scroll left')}><ChevronLeft size={16}/></button>
          <button type="button" onClick={() => moveSlider(slider, 1)} aria-label={t('Trượt sang phải','Scroll right')}><ChevronRight size={16}/></button>
        </div>
      </div>
      {rows.length ? <div className="environment-news-track" ref={slider} tabIndex={0} role="region" aria-label={title}>
        {rows.map((item, index) => <a className="environment-news-card" href={item.url} target="_blank" rel="noreferrer" key={`${item.url}-${index}`} aria-label={`${item.title} (${item.publisher})`}>
          <div className="environment-news-image">
            {item.image_url ? <img src={item.image_url} alt="" loading="lazy" referrerPolicy="strict-origin-when-cross-origin" onError={event => { event.currentTarget.hidden = true; event.currentTarget.nextElementSibling?.classList.add('is-visible'); }}/>: null}
            <div className={`environment-news-image-fallback${item.image_url ? '' : ' is-visible'}`} aria-hidden="true"><TopicIcon topics={item.topics} title={item.title.toLocaleLowerCase(language === 'vi' ? 'vi' : 'en')}/><span>{item.topics[0] ?? t('RÁC THẢI','WASTE')}</span></div>
            <span className="environment-news-badge">{t('TIN BÀI','NEWS')}</span>
          </div>
          <div className="environment-news-card-body">
            <div className="environment-news-card-meta"><span>{item.publisher}</span>{item.published_at && <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>}</div>
            <h5>{item.title}<ExternalLink size={13} aria-hidden="true"/></h5>
            {item.summary && <p>{item.summary}</p>}
            <div className="environment-news-topics">{item.topics.slice(0, 2).map(topic => <span key={topic}>{topic}</span>)}</div>
          </div>
        </a>)}
      </div> : <p className="environment-news-empty">{t('Chưa có bài viết trong nhóm này.','There are no articles in this row yet.')}</p>}
    </section>;

  const hasItems = latestItems.length > 0 || olderItems.length > 0;
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
    {hasItems ? <>
      {renderCarousel(t('TIN MỚI NHẤT','LATEST NEWS'), latestItems, 'latest-news', latestSlider)}
      {renderCarousel(t('CÁC BÀI VIẾT CŨ HƠN','EARLIER ARTICLES'), olderItems, 'older-news', olderSlider)}
    </> : !loading && <p className="environment-news-empty">
      {failed ? t('Chưa tải được tin. Kiểm tra kết nối máy chủ rồi thử lại.','News could not be loaded. Check the server and try again.') : t('Chưa tìm thấy bài mới về rác thải từ các báo đã chọn.','No recent waste related articles were found from the selected publishers.')}
    </p>}
    <p className="environment-news-footnote">{t('Chỉ hiển thị tiêu đề và đoạn trích RSS; nội dung đầy đủ thuộc về báo/đơn vị xuất bản.', 'Only RSS headlines and excerpts are shown; full articles remain with their publishers.')}</p>
  </section>;
}
