from io import BytesIO
from datetime import datetime, timedelta, timezone

from backend.environment_news import EnvironmentNewsService, _image_url, _parse_feed, _topics


def test_rss_media_thumbnail_is_exposed_as_image_url():
    from xml.etree import ElementTree

    item = ElementTree.fromstring(
        '<item xmlns:media="http://search.yahoo.com/mrss/">'
        '<media:thumbnail url="https://cdn.example.org/story.jpg"/>'
        '</item>'
    )

    assert _image_url(item) == "https://cdn.example.org/story.jpg"


def test_rss_entry_keeps_article_image_and_source_link(monkeypatch):
    payload = b"""<?xml version="1.0"?>
    <rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
      <title>Thu gom r\xc3\xa1c th\xc6\xb0\xe1\xbb\x9dng xuy\xc3\xaan</title>
      <link>https://vnexpress.net/story</link>
      <description>Ch\xc6\xb0\xc6\xa1ng tr\xc3\xacnh t\xc3\xa1i ch\xe1\xba\xbf r\xc3\xa1c.</description>
      <pubDate>Sat, 14 Nov 2026 02:00:00 GMT</pubDate>
      <media:content url="https://cdn.example.org/story.jpg" medium="image"/>
    </item></channel></rss>"""

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr("backend.environment_news.urlopen", lambda *_args, **_kwargs: Response(payload))
    articles = _parse_feed({
        "id": "test",
        "name": "Test feed",
        "url": "https://feed.example.org/rss",
        "source_url": "https://vnexpress.net",
    })

    assert len(articles) == 1
    assert articles[0]["url"] == "https://vnexpress.net/story"
    assert articles[0]["image_url"] == "https://cdn.example.org/story.jpg"


def test_fresh_json_feed_cache_is_served_without_refresh(monkeypatch, tmp_path):
    service = EnvironmentNewsService(feeds=({
        "id": "test",
        "name": "Test feed",
        "url": "https://feed.example.org/rss",
        "source_url": "https://news.example.org",
    },))
    service._data_path = tmp_path / "environment_news.json"
    service._cache = [{"title": "Đổ trộm rác ở khu dân cư", "url": "https://news.example.org/story"}]
    service._latest_items = service._cache
    service._older_items = []
    service._updated_at = "2026-11-14T00:00:00Z"
    monkeypatch.setattr(service, "_file_cache_is_fresh", lambda: True)
    monkeypatch.setattr("backend.environment_news._parse_feed", lambda *_args: (_ for _ in ()).throw(AssertionError()))

    response = service.get_news()

    assert response["available"] is True
    assert response["items"] == service._cache


def test_news_filter_rejects_unrelated_animal_husbandry():
    assert _topics("Công an kiểm tra cơ sở chăn nuôi heo, xử lý mùi hôi") == []
    assert _topics("Đề xuất lắp camera phát hiện người đổ trộm rác") == ["rác thải"]


def test_news_cache_keeps_ten_latest_and_fifteen_older():
    service = EnvironmentNewsService(feeds=())
    now = datetime.now(timezone.utc)
    service._cache = [
        {
            "title": f"Rác thải bị đổ bừa bãi ở khu dân cư {index}",
            "url": f"https://tuoitre.vn/story-{index}",
            "publisher": "Báo Tuổi Trẻ",
            "publisher_url": "https://tuoitre.vn",
            "published_at": (now - timedelta(days=1 if index < 10 else 20)).isoformat(),
            "topics": ["rác thải"],
        }
        for index in range(25)
    ]

    service._split_cache()

    assert len(service._latest_items) == 10
    assert len(service._older_items) == 15
    assert len(service._cache) == 25
