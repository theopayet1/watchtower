"""Orchestration de la veille :
collecte par catégorie -> dédoublonnage -> synthèse (Claude) -> email.

Lancement : python pipeline.py
C'est ce point d'entrée que la routine distante exécutera à chaque déclenchement.
"""
import sys
from datetime import date

# Sur Windows, la console plante sur les emojis/accents en cp1252 : on force l'UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
import state
import synthesize
import deliver_email
from collect import rss, hackernews


def collect_category(key: str, cfg: dict, max_per_source: int, freshness_hours: int) -> list[dict]:
    items = []
    if cfg.get("rss"):
        items += rss.collect(key, cfg["rss"], max_per_source, freshness_hours)
    if cfg.get("hn_query"):
        items += hackernews.collect(key, cfg["hn_query"], max_per_source, freshness_hours)
    return items


def preflight() -> None:
    """Vérification de pré-vol.

    Un run cloud « vert » = « pas d'erreur d'infra », PAS « la tâche a réussi ».
    En APP_ENV=prod on échoue donc BRUYAMMENT (sortie non-zéro -> routine ROUGE)
    si une config critique manque, au lieu de dégrader en silence. En dev, on se
    contente de signaler quels replis sont actifs.
    """
    problems, warnings = [], []

    if not config.ANTHROPIC_API_KEY:
        problems.append("ANTHROPIC_API_KEY manquante -> pas de vraie synthèse")

    backend = deliver_email.resolve_backend()
    if backend == "file":
        problems.append("aucun backend email réel (resend/brevo/smtp) -> pas d'envoi")
    elif backend == "smtp":
        warnings.append("backend SMTP : souvent bloqué en sandbox cloud (ports 25/587)")
    if not config.EMAIL_TO:
        problems.append("EMAIL_TO manquant -> aucun destinataire")

    for w in warnings:
        print(f"⚠️  AVERTISSEMENT : {w}")

    if not problems:
        return

    if config.IS_PROD:
        raise SystemExit(
            "❌ ÉCHEC PRÉ-VOL (APP_ENV=prod) — la routine DOIT échouer plutôt que "
            "tourner au vert pour rien :\n  - " + "\n  - ".join(problems)
        )

    print(f"ℹ️  Mode dev (APP_ENV={config.APP_ENV}) — replis actifs pour :")
    for p in problems:
        print(f"   - {p}")


def main() -> None:
    preflight()
    sources = config.load_sources()
    max_per_source = sources.get("max_per_source", 15)
    freshness_hours = sources.get("freshness_hours", 30)
    print(f"État : {'Supabase' if state.USE_SUPABASE else 'local JSON'}")
    feedback = state.pending_feedback()
    if feedback:
        print(f"Feedback en attente à appliquer : {feedback!r}")

    digest_parts = []
    all_new = []

    for key, cfg in sources["categories"].items():
        label = cfg.get("label", key)
        print(f"\n=== {label} ===")
        raw = collect_category(key, cfg, max_per_source, freshness_hours)
        print(f"  collecté : {len(raw)} items bruts")
        fresh = state.filter_new(raw)          # retire ce qui a déjà été vu
        if not fresh:
            print("  rien de nouveau")
            continue
        print(f"  {len(fresh)} nouveaux -> synthèse")
        summary = synthesize.synthesize(label, fresh, feedback)
        if summary:
            digest_parts.append(f"## {label}\n\n{summary}")
            all_new += fresh

    today = date.today().isoformat()
    if digest_parts:
        body = f"# News digest — {today}\n\n" + "\n\n".join(digest_parts)
    else:
        body = f"# News digest — {today}\n\n_No new items today._"

    # On envoie TOUJOURS, même sans nouveauté (confirme que la veille a tourné).
    deliver_email.send(f"🗞️ News digest — {today}", body)

    # On n'archive et ne marque "vu" que s'il y avait vraiment du contenu.
    if digest_parts:
        state.save_digest(body)
        state.mark_seen(all_new)                # marqué APRÈS livraison réussie
        if feedback:
            state.mark_feedback_applied()
    print(f"\nDigest livré ({len(all_new)} items) et état mis à jour.")


if __name__ == "__main__":
    main()
