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
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from http.cookiejar import CookieJar
from xml.etree import ElementTree


REFRESH_SECONDS = 24 * 60 * 60
LATEST_LIMIT = 10
OLDER_LIMIT = 15
MAX_ITEMS = LATEST_LIMIT + OLDER_LIMIT
MAX_IMAGE_ENRICH_PER_REFRESH = MAX_ITEMS
HISTORY_DAYS = 90
MAX_FEED_BYTES = 2_000_000
USER_AGENT = 'SOICTERRA-Environment-News/1.0 (RSS headlines and excerpts; opens original publisher pages)'
PAGE_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

TRUSTED_DOMAINS = {
    'vnexpress.net', 'tuoitre.vn', 'thanhnien.vn', 'dantri.com.vn',
    'vietnamnet.vn', 'vtv.vn', 'nhandan.vn', 'vov.vn', 'baotintuc.vn',
    'laodong.vn', 'tienphong.vn', 'plo.vn', 'cand.com.vn', 'vietnam.vn',
}
NEWS_QUERY = '("rác thải" OR "đổ trộm rác" OR "xả rác" OR "vứt rác" OR "đốt rác" OR "bãi rác") (site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn OR site:dantri.com.vn OR site:vietnamnet.vn OR site:vtv.vn OR site:nhandan.vn OR site:vov.vn) when:7d'
ARCHIVE_QUERY = NEWS_QUERY.rsplit('when:7d', 1)[0] + 'when:60d'
LANDFILL_QUERY = '("rác chất đống" OR "rác ngập" OR "bãi rác quá tải" OR "rác thải sinh hoạt") (site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn OR site:dantri.com.vn OR site:vietnamnet.vn OR site:vtv.vn OR site:nhandan.vn OR site:vov.vn) when:90d'
ILLEGAL_DUMPING_QUERY = '("lén đổ rác" OR "camera" "đổ rác" OR "đổ trộm" OR "xả rác nơi công cộng" OR "vứt rác bừa bãi") (site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn OR site:dantri.com.vn OR site:vietnamnet.vn OR site:vtv.vn OR site:nhandan.vn OR site:vov.vn) when:90d'
FEEDS = (
    {
        'id': 'google-news',
        'name': 'Google Tin tức',
        'url': 'https://news.google.com/rss/search?q=' + quote(NEWS_QUERY)
        + '&hl=vi&gl=VN&ceid=VN:vi',
        'source_url': 'https://news.google.com/',
    },
    {
        'id': 'google-news-archive',
        'name': 'Google Tin tức · Kho bài cũ',
        'url': 'https://news.google.com/rss/search?q=' + quote(LANDFILL_QUERY)
        + '&hl=vi&gl=VN&ceid=VN:vi',
        'source_url': 'https://news.google.com/',
        'history_days': HISTORY_DAYS,
    },
    {
        'id': 'google-news-enforcement',
        'name': 'Google Tin tức · Xả rác, đổ trộm',
        'url': 'https://news.google.com/rss/search?q=' + quote(ILLEGAL_DUMPING_QUERY)
        + '&hl=vi&gl=VN&ceid=VN:vi',
        'source_url': 'https://news.google.com/',
        'history_days': HISTORY_DAYS,
    },
    {
        'id': 'vnexpress-latest',
        'name': 'VnExpress',
        'url': 'https://vnexpress.net/rss/tin-moi-nhat.rss',
        'source_url': 'https://vnexpress.net/rss',
    },
    {
        'id': 'tuoitre-latest',
        'name': 'Báo Tuổi Trẻ',
        'url': 'https://tuoitre.vn/rss/tin-moi-nhat.rss',
        'source_url': 'https://tuoitre.vn/rss.htm',
    },
    {
        'id': 'tuoitre-readers',
        'name': 'Báo Tuổi Trẻ · Bạn đọc',
        'url': 'https://tuoitre.vn/rss/ban-doc.rss',
        'source_url': 'https://tuoitre.vn/rss.htm',
    },
    {
        'id': 'thanhnien-readers',
        'name': 'Báo Thanh Niên · Bạn đọc',
        'url': 'https://thanhnien.vn/rss/ban-doc.rss',
        'source_url': 'https://thanhnien.vn/rss.html',
        'history_days': HISTORY_DAYS,
    },
    {
        'id': 'dantri-lifestyle',
        'name': 'Báo Dân trí',
        'url': 'https://dantri.com.vn/rss/doi-song.rss',
        'source_url': 'https://dantri.com.vn/rss.htm',
    },
    {
        'id': 'thanhnien-current',
        'name': 'Báo Thanh Niên',
        'url': 'https://thanhnien.vn/rss/thoi-su.rss',
        'source_url': 'https://thanhnien.vn/rss.html',
    },
)

TOPIC_TERMS = {
    'rác thải': ('rac', 'chat thai', 'do trom', 'xa rac', 'dot rac', 'vu rac', 'bai rac'),
    'nhựa và tái chế': ('nhua', 'tai che', 'nilon', 'ni long', 'bao bi'),
    'ô nhiễm công cộng': ('o nhiem', 'diem den rac', 'khu dan cu'),
}
WASTE_TERMS = ('rac', 'chat thai')


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


def _contains_any(normalized: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf'(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])', normalized) for term in terms)


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
        request = Request(url, headers={'User-Agent': PAGE_USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'})
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


def _google_response_url(body: str) -> str | None:
    try:
        payload_text = body.split('\n\n', 1)[1] if '\n\n' in body else body.removeprefix(")]}'").lstrip()
        frames = json.loads(payload_text)
        frame = next(
            item for item in frames
            if isinstance(item, list) and len(item) > 2 and item[0] == 'wrb.fr' and item[1] == 'Fbv4je'
        )
        result = json.loads(frame[2])
        if isinstance(result, list) and len(result) > 1 and result[0] == 'garturlres':
            resolved = str(result[1])
            parsed = urlparse(resolved)
            if parsed.scheme == 'https' and parsed.netloc and _trusted_publisher(resolved):
                return resolved
    except (ValueError, TypeError, StopIteration, IndexError):
        pass
    return None


def _resolve_google_article(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname != 'news.google.com' or '/articles/' not in parsed.path:
        return None
    article_id = parsed.path.rsplit('/', 1)[-1]
    if not article_id:
        return None
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    headers = {
        'User-Agent': PAGE_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8',
        'Cookie': 'CONSENT=PENDING+987',
        'Upgrade-Insecure-Requests': '1',
    }
    try:
        page = opener.open(Request(f'https://news.google.com/rss/articles/{article_id}', headers=headers), timeout=8)
        html = page.read(800_000).decode('utf-8', errors='replace')
        signature = re.search(r"data-n-a-sg=[\"']([^\"']+)[\"']", html)
        timestamp = re.search(r"data-n-a-ts=[\"'](\d+)[\"']", html)
        if not signature or not timestamp:
            return None
        inner = json.dumps([
            'garturlreq',
            [['X', 'X', ['X', 'X'], None, None, 1, 1, 'VN:vi', None, 1, None, None, None, None, None, 0, 1],
             'X', 'X', 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id,
            int(timestamp.group(1)),
            signature.group(1),
        ], separators=(',', ':'))
        outer = json.dumps([[['Fbv4je', inner]]], separators=(',', ':'))
        body = ('f.req=' + quote(outer, safe='')).encode('utf-8')
        post_headers = {
            **headers,
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'Origin': 'https://news.google.com',
            'Referer': 'https://news.google.com/',
            'X-Same-Domain': '1',
            'Accept': '*/*',
        }
        with opener.open(Request(
            'https://news.google.com/_/DotsSplashUi/data/batchexecute',
            data=body,
            headers=post_headers,
        ), timeout=8) as response:
            return _google_response_url(response.read().decode('utf-8', errors='replace'))
    except Exception:
        return None


def _enrich_article_image(item: dict[str, Any]) -> None:
    """Resolve Google News links and read the publisher's social preview image."""
    article_url = str(item.get('url') or '')
    if (urlparse(article_url).hostname or '').casefold() == 'news.google.com':
        resolved = _resolve_google_article(article_url)
        if not resolved:
            return
        article_url = resolved
        item['url'] = resolved
    if not _trusted_publisher(article_url):
        return
    item['image_url'] = _article_image(article_url)


def _topics(text: str) -> list[str]:
    normalized = _normalized(text)
    if not _contains_any(normalized, WASTE_TERMS):
        return []
    return [label for label, terms in TOPIC_TERMS.items() if _contains_any(normalized, terms)]


def _trusted_publisher(url: str) -> bool:
    host = (urlparse(url).hostname or '').casefold().removeprefix('www.')
    return any(host == domain or host.endswith('.' + domain) for domain in TRUSTED_DOMAINS)


def _parse_feed(feed: dict[str, Any]) -> list[dict[str, Any]]:
    request = Request(feed['url'], headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/xml, text/xml'})
    with urlopen(request, timeout=8) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError('RSS response exceeded size limit')
    root = ElementTree.fromstring(data)
    entries = [node for node in root.iter() if node.tag.rsplit('}', 1)[-1].casefold() in {'item', 'entry'}]
    articles = []
    default_history = 7 if feed['id'] == 'google-news' else HISTORY_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(feed.get('history_days', default_history)))
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
        elif str(feed['id']).startswith('google-news'):
            continue
        source_node = next((node for node in entry if node.tag.rsplit('}', 1)[-1].casefold() == 'source'), None)
        publisher = _plain_text(source_node.text or '', 100) if source_node is not None else feed['name']
        publisher_url = (source_node.attrib.get('url') if source_node is not None else '') or feed['source_url']
        if not _trusted_publisher(publisher_url):
            continue
        source_suffix = f' - {publisher}'
        if title.casefold().endswith(source_suffix.casefold()):
            title = title[:-len(source_suffix)].rstrip()
        headline_topics = _topics(title)
        if not headline_topics:
            continue
        topics = _topics(f'{title} {summary}') or headline_topics
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
    def __init__(self, feeds: tuple[dict[str, Any], ...] = FEEDS) -> None:
        self._feeds = feeds
        self._cache: list[dict[str, Any]] = []
        self._latest_items: list[dict[str, Any]] = []
        self._older_items: list[dict[str, Any]] = []
        self._updated_at: str | None = None
        self._last_attempt = 0.0
        self._last_failures: list[str] = []
        self._lock = threading.Lock()
        self._data_path = Path(__file__).resolve().parent / 'data' / 'environment_news.json'
        self._load_file_cache()

    def _load_file_cache(self) -> None:
        try:
            payload = json.loads(self._data_path.read_text(encoding='utf-8'))
            latest = payload.get('latest_items')
            older = payload.get('older_items')
            items = (latest if isinstance(latest, list) else []) + (older if isinstance(older, list) else [])
            if not items:
                items = payload.get('items', [])
            if isinstance(items, list):
                self._cache = self._clean_items(items)
                self._split_cache()
                self._updated_at = payload.get('updated_at')
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def _published_datetime(item: dict[str, Any]) -> datetime | None:
        value = item.get('published_at')
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    def _clean_items(self, items: list[Any]) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
        unique: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict) or not item.get('url'):
                continue
            if not _trusted_publisher(str(item.get('publisher_url') or '')):
                continue
            if not _topics(f"{item.get('title', '')} {item.get('summary', '')}"):
                continue
            published = self._published_datetime(item)
            if published is None or published < cutoff:
                continue
            title_key = _normalized(str(item.get('title') or ''))
            if not title_key:
                continue
            existing = unique.get(title_key)
            if existing is None:
                unique[title_key] = item
            else:
                old_is_wrapper = (urlparse(str(existing.get('url') or '')).hostname or '').endswith('news.google.com')
                new_is_direct = not (urlparse(str(item.get('url') or '')).hostname or '').endswith('news.google.com')
                if (old_is_wrapper and new_is_direct) or (bool(item.get('image_url')) and not existing.get('image_url')):
                    unique[title_key] = item
        result = list(unique.values())
        result.sort(key=lambda row: row.get('published_at') or '', reverse=True)
        return result[:MAX_ITEMS * 3]

    def _split_cache(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        fresh = [
            item for item in self._cache
            if (published := self._published_datetime(item)) is not None and published >= cutoff
        ]
        self._latest_items = fresh[:LATEST_LIMIT]
        latest_urls = {item['url'] for item in self._latest_items}
        self._older_items = [item for item in self._cache if item['url'] not in latest_urls][:OLDER_LIMIT]
        self._cache = self._latest_items + self._older_items

    def _file_cache_is_fresh(self) -> bool:
        try:
            return bool(self._cache) and time.time() - self._data_path.stat().st_mtime < REFRESH_SECONDS
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
            merged = self._clean_items(self._cache + articles)
            missing_images = [item for item in merged if not item.get('image_url')][
                :MAX_IMAGE_ENRICH_PER_REFRESH
            ]
            if missing_images:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    image_jobs = {
                        executor.submit(_enrich_article_image, item): item for item in missing_images
                    }
                    for future in as_completed(image_jobs):
                        try:
                            future.result()
                        except Exception:
                            pass
            if merged:
                self._cache = merged
                self._split_cache()
            self._last_failures = failures
            self._last_attempt = time.monotonic()
            self._updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            if self._cache:
                try:
                    self._data_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self._data_path.with_suffix('.json.tmp')
                    temporary.write_text(json.dumps({
                        'schema_version': 1,
                        'updated_at': self._updated_at,
                        'latest_items': self._latest_items,
                        'older_items': self._older_items,
                        'items': self._cache,
                    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    temporary.replace(self._data_path)
                except OSError:
                    pass
        return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        return {
            'items': self._cache,
            'latest_items': self._latest_items,
            'older_items': self._older_items,
            'updated_at': self._updated_at,
            'refresh_after_seconds': REFRESH_SECONDS,
            'partial_failure': bool(self._last_failures),
            'available': bool(self._cache),
        }


environment_news = EnvironmentNewsService()
