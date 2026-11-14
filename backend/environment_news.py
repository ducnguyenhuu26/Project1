"""Provider-neutral environment news feed with a daily RSS fallback."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import re
import threading
import time
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


REFRESH_SECONDS = 24 * 60 * 60
MAX_ITEMS = 36
MAX_FEED_BYTES = 2_000_000
USER_AGENT = 'SOICTERRA-Environment-News/1.0 (RSS headlines and excerpts; opens original publisher pages)'

NEWS_QUERY = '(môi trường OR rác thải OR chất thải OR tái chế OR ô nhiễm OR khí hậu OR phát thải) when:7d'
FEEDS = (
    {
        'id': 'google-news',
        'name': 'Google Tin tức',
        'url': 'https://news.google.com/rss/search?q=' + quote(NEWS_QUERY)
        + '&hl=vi&gl=VN&ceid=VN:vi',
        'source_url': 'https://news.google.com/',
    },
    {
        'id': 'vnexpress',
        'name': 'VnExpress · Khoa học',
        'url': 'https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss',
        'source_url': 'https://vnexpress.net/rss',
    },
    {
        'id': 'tuoitre',
        'name': 'Tuổi Trẻ · Khoa học',
        'url': 'https://tuoitre.vn/khoa-hoc.rss',
        'source_url': 'https://tuoitre.vn/rss.htm',
    },
    {
        'id': 'vepf',
        'name': 'Quỹ Bảo vệ Môi trường Việt Nam',
        'url': 'https://www.vepf.vn/vi/rss/tin-moi-truong-vepfpw4e5j.rss',
        'source_url': 'https://www.vepf.vn/vi/rss.html',
    },
)

TOPIC_TERMS = {
    'rác thải': ('rac thai', 'chat thai', 'phan loai rac', 'bai rac', 'xu ly rac'),
    'nhựa và tái chế': ('nhua', 'tai che', 'tai su dung', 'kinh te tuan hoan'),
    'ô nhiễm': ('o nhiem', 'nuoc thai', 'khi thai', 'xa thai', 'vi nhua'),
    'khí hậu': ('khi hau', 'bien doi khi hau', 'phat thai', 'carbon', 'nang luong sach', 'nang luong tai tao'),
    'thiên nhiên': ('sinh thai', 'bao ton', 'da dang sinh hoc', 'rung', 'moi truong'),
}


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


class _SocialImage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.url = ''

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != 'meta' or self.url:
            return
        values = {key.casefold(): value or '' for key, value in attrs}
        key = values.get('property', values.get('name', '')).casefold()
        if key in {'og:image', 'og:image:url', 'twitter:image'}:
            self.url = values.get('content', '').strip()


def _plain_text(value: str, max_chars: int = 420) -> str:
    parser = _TextOnly()
    try:
        parser.feed(unescape(value))
        text = ' '.join(parser.parts)
    except Exception:
        text = re.sub(r'<[^>]+>', ' ', unescape(value))
    text = ' '.join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0].rstrip(' .,:;') + '…'
    return text


def _normalized(value: str) -> str:
    import unicodedata

    value = unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
    return ''.join(char for char in value if not unicodedata.combining(char))


def _published(value: str) -> str | None:
    value = value.strip().replace('\u202f', ' ')
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        for fmt in ('%m/%d/%Y %I:%M:%S %p', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z'):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _child_text(element: ElementTree.Element, *names: str) -> str:
    wanted = set(names)
    for child in element:
        if child.tag.rsplit('}', 1)[-1].casefold() in wanted:
            if child.text and child.text.strip():
                return child.text.strip()
    return ''


def _article_link(element: ElementTree.Element) -> str:
    for child in element:
        if child.tag.rsplit('}', 1)[-1].casefold() != 'link':
            continue
        href = child.attrib.get('href', '').strip()
        rel = child.attrib.get('rel', 'alternate').casefold()
        if href and rel in {'alternate', ''}:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ''


def _image_url(entry: ElementTree.Element) -> str | None:
    for node in entry.iter():
        tag = node.tag.rsplit('}', 1)[-1].casefold()
        candidate = ''
        if tag in {'content', 'thumbnail', 'enclosure'}:
            candidate = node.attrib.get('url', '')
            if tag == 'enclosure' and not node.attrib.get('type', '').startswith('image/'):
                continue
        elif tag in {'description', 'summary', 'encoded', 'content'} and node.text:
            match = re.search(r"""<img\b[^>]*?src=["']([^"']+)""", unescape(node.text), re.I)
            candidate = match.group(1) if match else ''
        parsed = urlparse(candidate)
        if parsed.scheme == 'https' and parsed.netloc:
            return candidate
    return None


def _article_image(url: str) -> str | None:
    try:
        request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'})
        with urlopen(request, timeout=5) as response:
            html = response.read(500_000).decode('utf-8', errors='replace')
        parser = _SocialImage()
        parser.feed(html)
        candidate = parser.url
        if candidate.startswith('//'):
            candidate = 'https:' + candidate
        parsed = urlparse(candidate)
        return candidate if parsed.scheme == 'https' and parsed.netloc else None
    except Exception:
        return None


def _topics(text: str) -> list[str]:
    normalized = _normalized(text)
    return [label for label, terms in TOPIC_TERMS.items() if any(term in normalized for term in terms)]


def _parse_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    request = Request(feed['url'], headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/xml, text/xml'})
    with urlopen(request, timeout=8) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError('RSS response exceeded size limit')
    root = ElementTree.fromstring(data)
    entries = [node for node in root.iter() if node.tag.rsplit('}', 1)[-1].casefold() in {'item', 'entry'}]
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for entry in entries:
        title = _plain_text(_child_text(entry, 'title'), max_chars=220)
        link = _article_link(entry)
        if not title or not link:
            continue
        parsed_link = urlparse(link)
        if parsed_link.scheme != 'https' or not parsed_link.netloc:
            continue
        summary = _plain_text(_child_text(entry, 'description', 'summary', 'encoded', 'content'))
        image_url = _image_url(entry)
        published = _published(_child_text(entry, 'pubdate', 'published', 'updated', 'date'))
        if published:
            published_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
            if published_dt < cutoff:
                continue
        elif feed['id'] == 'google-news':
            continue
        source_node = next((node for node in entry if node.tag.rsplit('}', 1)[-1].casefold() == 'source'), None)
        publisher = _plain_text(source_node.text or '', 100) if source_node is not None else feed['name']
        publisher_url = (source_node.attrib.get('url') if source_node is not None else '') or feed['source_url']
        source_suffix = f' - {publisher}'
        if title.casefold().endswith(source_suffix.casefold()):
            title = title[:-len(source_suffix)].rstrip()
        searchable = f'{title} {summary}'
        topics = _topics(searchable)
        if not topics:
            continue
        articles.append({
            'title': title,
            'summary': summary,
            'url': link,
            'publisher': publisher,
            'publisher_url': publisher_url,
            'published_at': published,
            'topics': topics,
            'image_url': image_url,
        })
    return articles


class EnvironmentNewsService:
    def __init__(self, feeds: tuple[dict[str, str], ...] = FEEDS) -> None:
        self._feeds = feeds
        self._cache: list[dict[str, Any]] = []
        self._updated_at: str | None = None
        self._last_attempt = 0.0
        self._last_failures: list[str] = []
        self._lock = threading.Lock()
        self._data_path = Path(__file__).resolve().parent / 'data' / 'environment_news.json'
        self._load_file_cache()

    def _load_file_cache(self) -> None:
        try:
            payload = json.loads(self._data_path.read_text(encoding='utf-8'))
            items = payload.get('items', [])
            if isinstance(items, list):
                self._cache = [item for item in items if isinstance(item, dict) and item.get('url')][:MAX_ITEMS]
                self._updated_at = payload.get('updated_at')
        except (OSError, ValueError, TypeError):
            pass

    def _file_cache_is_fresh(self) -> bool:
        try:
            return time.time() - self._data_path.stat().st_mtime < REFRESH_SECONDS
        except OSError:
            return False

    def get_news(self, force_refresh: bool = False) -> dict[str, Any]:
        if not force_refresh and self._file_cache_is_fresh():
            return self._snapshot()
        now = time.monotonic()
        if not force_refresh and now - self._last_attempt < REFRESH_SECONDS:
            return self._snapshot()
        with self._lock:
            now = time.monotonic()
            if not force_refresh and now - self._last_attempt < REFRESH_SECONDS:
                return self._snapshot()
            articles: list[dict[str, Any]] = []
            failures: list[str] = []
            with ThreadPoolExecutor(max_workers=len(self._feeds)) as executor:
                future_to_feed = {executor.submit(_parse_feed, feed): feed for feed in self._feeds}
                for future in as_completed(future_to_feed):
                    feed = future_to_feed[future]
                    try:
                        articles.extend(future.result())
                    except Exception:
                        failures.append(feed['id'])
            unique: dict[str, dict[str, Any]] = {}
            for article in articles:
                unique.setdefault(article['url'], article)
            merged = list(unique.values())
            merged.sort(key=lambda item: item['published_at'] or '', reverse=True)
            visible = merged[:12]
            missing_images = [item for item in visible if not item.get('image_url')]
            if missing_images:
                with ThreadPoolExecutor(max_workers=6) as executor:
                    image_jobs = {executor.submit(_article_image, item['url']): item for item in missing_images}
                    for future in as_completed(image_jobs):
                        try:
                            image_jobs[future]['image_url'] = future.result()
                        except Exception:
                            pass
            if merged:
                self._cache = merged[:MAX_ITEMS]
            self._last_failures = failures
            self._last_attempt = time.monotonic()
            self._updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            if self._cache:
                try:
                    self._data_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self._data_path.with_suffix('.json.tmp')
                    temporary.write_text(json.dumps({'schema_version': 1, 'updated_at': self._updated_at, 'items': self._cache}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    temporary.replace(self._data_path)
                except OSError:
                    pass
        return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        return {
            'items': self._cache,
            'updated_at': self._updated_at,
            'refresh_after_seconds': REFRESH_SECONDS,
            'partial_failure': bool(self._last_failures),
            'available': bool(self._cache),
        }


environment_news = EnvironmentNewsService()
