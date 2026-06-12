"""Aperçu de la collecte — montre CE QUE les collecteurs récupèrent, joliment
formaté, SANS dédoublonnage, synthèse ni email.

C'est de la LECTURE SEULE : ça ne touche pas à state/, donc tu peux le relancer
autant de fois que tu veux pour voir le rendu brut des items.

Lancement :
    python preview.py            -> toutes les catégories
    python preview.py ia         -> une seule catégorie (sa clé dans sources.yaml)
"""
import sys
from datetime import date

# Force l'UTF-8 pour que les emojis/accents s'affichent sans planter (Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
from collect import rss, hackernews

LINE = "═" * 72


def collect_category(key: str, cfg: dict, max_per_source: int, freshness_hours: int) -> list[dict]:
    items = []
    if cfg.get("rss"):
        items += rss.collect(key, cfg["rss"], max_per_source, freshness_hours)
    if cfg.get("hn_query"):
        items += hackernews.collect(key, cfg["hn_query"], max_per_source, freshness_hours)
    return items


def print_item(n: int, it: dict) -> None:
    score = f"   ⭐ {it['score']} pts" if it.get("score") else ""
    print(f"  {n:>2}. {it['title']}")
    print(f"      ├─ source : {it['source']}{score}")
    if it.get("published"):
        print(f"      ├─ date   : {it['published']}")
    print(f"      ├─ lien   : {it['url']}")
    print(f"      └─ id     : {it['id']}")
    if it.get("summary"):
        print(f"         « {it['summary'][:160]} »")
    print()


def main() -> None:
    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    sources = config.load_sources()
    max_per_source = sources.get("max_per_source", 15)
    freshness_hours = sources.get("freshness_hours", 30)

    print(LINE)
    print(f"  APERÇU DE LA COLLECTE — {date.today().isoformat()}")
    print(f"  max {max_per_source}/source · fraîcheur {freshness_hours}h · lecture seule")
    print(LINE)

    grand_total = 0
    for key, cfg in sources["categories"].items():
        if wanted and key != wanted:
            continue
        label = cfg.get("label", key)
        items = collect_category(key, cfg, max_per_source, freshness_hours)

        # décompte par source
        by_source: dict[str, int] = {}
        for it in items:
            by_source[it["source"]] = by_source.get(it["source"], 0) + 1
        breakdown = " · ".join(f"{s}: {n}" for s, n in by_source.items()) or "aucune source"

        print(f"\n┌{'─' * 70}")
        print(f"│ {label}   [{key}]")
        print(f"│ {len(items)} items  →  {breakdown}")
        print(f"└{'─' * 70}\n")

        for n, it in enumerate(items, 1):
            print_item(n, it)
        grand_total += len(items)

    print(LINE)
    print(f"  TOTAL : {grand_total} items collectés")
    print(LINE)


if __name__ == "__main__":
    main()
