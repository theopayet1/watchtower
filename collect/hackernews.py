"""Collecteur Hacker News via l'API Algolia (aucune clé requise, très fiable).

Doc : https://hn.algolia.com/api  — on cherche les "story" récentes par mot-clé.
"""
import time

import requests

API = "https://hn.algolia.com/api/v1/search_by_date"


def collect(category_key: str, query: str, max_items: int, freshness_hours: int) -> list[dict]:
    since = int(time.time()) - freshness_hours * 3600
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since}",
        "hitsPerPage": max_items,
    }
    try:
        r = requests.get(API, params=params, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except requests.RequestException as e:
        print(f"  [hackernews] erreur: {e}")
        return []

    items = []
    for h in hits:
        oid = h.get("objectID")
        url = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        items.append({
            "id": f"hn:{oid}",
            "source": "Hacker News",
            "title": h.get("title") or "(sans titre)",
            "url": url,
            "score": h.get("points"),
            "published": h.get("created_at", ""),
            "summary": "",
        })
    return items
