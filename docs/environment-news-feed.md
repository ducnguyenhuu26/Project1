# Environment news feed

The web app reads GET /api/v1/news/environment. The response contains
latest_items (up to 10 stories published in the last seven days), older_items
(up to 15 saved stories from the preceding 90 days), the combined items list,
updated_at, refresh_after_seconds, partial_failure, and available.
Article records are provider-neutral, so a scheduled GitHub Actions crawler
can combine RSS, publisher APIs, or other permitted sources without changing
the API or UI.

The crawler can replace backend/data/environment_news.json atomically:

    {
      "schema_version": 1,
      "updated_at": "2026-11-14T02:44:25Z",
      "latest_items": [],
      "older_items": [
        {
          "title": "Article title",
          "summary": "Short source excerpt",
          "url": "https://publisher.example/article",
          "publisher": "Publisher",
          "publisher_url": "https://publisher.example",
          "published_at": "2026-11-14T02:00:00Z",
          "topics": ["rác thải"],
          "image_url": "https://publisher.example/image.jpg"
        }
      ],
      "items": []
    }

Use the original article URL in url; image_url is optional and should point
to a public HTTPS image. Stories are kept only when their headline explicitly
mentions garbage or solid waste, and current feeds are restricted to
established Vietnamese publishers. The API refreshes RSS sources daily and
keeps a rolling history for the second carousel. The manual refresh button
requests an immediate refresh.
