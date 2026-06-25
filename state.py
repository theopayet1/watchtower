"""État persistant : dédoublonnage, historique des digests, feedback.

DEUX BACKENDS, MÊME INTERFACE (filter_new / mark_seen / save_digest /
pending_feedback / mark_feedback_applied) :

  - LOCAL (défaut) : fichiers dans state/ et digests/. Parfait pour le dev.
  - SUPABASE : activé dès que SUPABASE_URL + SUPABASE_KEY sont définis. PostgreSQL
    hébergé. INDISPENSABLE en routine cloud : l'environnement est détruit à chaque
    run, donc un fichier local ne survivrait pas d'un jour sur l'autre.

Le schéma des 3 tables Supabase est dans schema.sql (à coller dans l'éditeur SQL).
Le reste du code (pipeline.py) ne sait pas quel backend est actif : il appelle les
mêmes fonctions.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import config

USE_SUPABASE = bool(config.SUPABASE_URL and config.SUPABASE_KEY)

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
DIGESTS_DIR = ROOT / "digests"
SEEN_FILE = STATE_DIR / "seen.json"
FEEDBACK_FILE = STATE_DIR / "feedback.md"

_sb = None
if USE_SUPABASE:
    from supabase import create_client
    _sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
else:
    STATE_DIR.mkdir(exist_ok=True)
    DIGESTS_DIR.mkdir(exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- API

def filter_new(items: list[dict]) -> list[dict]:
    """Garde les items jamais vus, et dédoublonne aussi DANS le lot courant
    (un même article peut remonter via deux sources)."""
    if USE_SUPABASE:
        seen_ids = set()
        ids = [it["id"] for it in items]
        for chunk in (ids[i:i + 100] for i in range(0, len(ids), 100)):  # paquets de 100
            rows = _sb.table("seen_items").select("id").in_("id", chunk).execute()
            seen_ids.update(r["id"] for r in rows.data)
    else:
        seen_ids = set(_load_seen().keys())

    out, batch = [], set()
    for it in items:
        iid = it["id"]
        if iid in seen_ids or iid in batch:
            continue
        batch.add(iid)
        out.append(it)
    return out


def mark_seen(items: list[dict]) -> None:
    """Marque les items comme traités EN STOCKANT titre/url/source, pour pouvoir
    les retrouver plus tard (recherche dans la base). À n'appeler qu'APRÈS
    livraison réussie. La colonne `note` n'est pas touchée ici : tu la remplis
    toi-même dans Supabase pour annoter/taguer un item."""
    if not items:
        return
    if USE_SUPABASE:
        rows = [{
            "id": it["id"],
            "seen_at": _now(),
            "title": it.get("title"),
            "url": it.get("url"),
            "source": it.get("source"),
            "published": str(it["published"]) if it.get("published") not in (None, "") else None,
        } for it in items]
        _sb.table("seen_items").upsert(rows).execute()
    else:
        seen = _load_seen()
        for it in items:
            seen[it["id"]] = {
                "seen_at": _now(),
                "title": it.get("title"),
                "url": it.get("url"),
                "source": it.get("source"),
            }
        _save_seen(seen)


def save_digest(text: str):
    """Archive le digest envoyé (table digests en Supabase, fichier .md en local)."""
    if USE_SUPABASE:
        _sb.table("digests").insert({"content": text}).execute()
        return None
    name = datetime.now().strftime("%Y-%m-%d_%H%M") + ".md"
    path = DIGESTS_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def pending_feedback() -> str:
    """Retourne le feedback non encore appliqué (ou chaîne vide)."""
    if USE_SUPABASE:
        rows = (_sb.table("feedback").select("note")
                .eq("applied", False).order("created_at").execute())
        return "\n".join(r["note"] for r in rows.data).strip()
    if FEEDBACK_FILE.exists():
        return FEEDBACK_FILE.read_text(encoding="utf-8").strip()
    return ""


def mark_feedback_applied() -> None:
    """Marque le feedback comme pris en compte (pour ne pas le réappliquer)."""
    if USE_SUPABASE:
        (_sb.table("feedback").update({"applied": True, "applied_at": _now()})
         .eq("applied", False).execute())
        return
    if not FEEDBACK_FILE.exists():
        return
    archive = STATE_DIR / "feedback_applied.md"
    with archive.open("a", encoding="utf-8") as f:
        f.write(f"\n--- appliqué {_now()} ---\n")
        f.write(FEEDBACK_FILE.read_text(encoding="utf-8"))
    FEEDBACK_FILE.write_text("", encoding="utf-8")


# ----------------------------------------------------------------- backend local

def _load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    return {}


def _save_seen(seen: dict) -> None:
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
