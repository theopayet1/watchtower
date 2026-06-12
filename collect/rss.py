"""Collecteur de flux RSS/Atom via feedparser (aucune clé requise).

On parcourt chaque flux, on filtre par fraîcheur (date de publication) et on
normalise vers le format d'item commun.
"""
import calendar
import html
import re
import time

import feedparser

_TAGS = re.compile(r"<[^>]+>")


def _clean(raw: str) -> str:
    """Retire les balises HTML ET décode les entités (&#160;, &#8217;…)."""
    text = _TAGS.sub("", raw or "")
    return html.unescape(text).strip()


def collect(category_key: str, feeds: list[str], max_items: int, freshness_hours: int) -> list[dict]:
    cutoff = time.time() - freshness_hours * 3600
    items = []
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"  [rss] erreur {feed_url}: {e}")
            continue

        feed_title = parsed.feed.get("title", "RSS")
        count = 0
        for entry in parsed.entries:
            # feedparser fournit une struct_time en UTC -> timegm (et non mktime).
            t = entry.get("published_parsed") or entry.get("updated_parsed")
            if t and calendar.timegm(t) < cutoff:
                continue

            uid = entry.get("id") or entry.get("link")
            if not uid:
                continue

            items.append({
                "id": f"rss:{uid}",
                "source": feed_title,
                "title": entry.get("title", "(sans titre)"),
                "url": entry.get("link", ""),
                "score": None,
                "published": entry.get("published", entry.get("updated", "")),
                "summary": _clean(entry.get("summary", ""))[:500],
            })
            count += 1
            if count >= max_items:
                break
    return items
