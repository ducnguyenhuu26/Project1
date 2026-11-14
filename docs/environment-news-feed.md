# Environment news feed

The web app reads GET /api/v1/news/environment. The response contains
items, updated_at, refresh_after_seconds, partial_failure, and available.
Article records are provider-neutral, so a scheduled GitHub Actions crawler
can combine RSS, publisher APIs, or other permitted sources without changing
the API or UI.

The crawler can replace backend/data/environment_news.json atomically:

    {
      "schema_version": 1,
      "updated_at": "2026-11-14T02:44:25Z",
      "items": [
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
      ]
    }

Use the original article URL in url; image_url is optional and should point
to a public HTTPS image. The backend reads a fresh JSON snapshot and refreshes
RSS sources once per day when the snapshot is stale or missing. The manual
refresh button requests an immediate refresh.
