"""Synthèse d'une catégorie via l'API Claude.

Repli sans clé : si ANTHROPIC_API_KEY est absente (ou l'appel échoue), on renvoie
une liste markdown brute — comme ça le pipeline reste testable de bout en bout.
"""
import config

PROMPT = """Tu es un assistant de veille. Voici les nouveautés du jour pour la
catégorie « {label} ». Rédige une synthèse en français, claire et concise :
- regroupe les sujets proches, ne fais pas une simple liste à puces ligne par ligne
- 3 à 6 points maximum, le plus important d'abord
- pour chaque point, garde le ou les liens source au format markdown [texte](url)
- ton factuel, zéro remplissage
{feedback_block}
Voici les items (titre — source — lien — éventuel résumé) :

{items_block}
"""


def _format_items(items: list[dict]) -> str:
    lines = []
    for it in items:
        score = f" [{it['score']} pts]" if it.get("score") else ""
        summary = f"\n    {it['summary'][:300]}" if it.get("summary") else ""
        lines.append(f"- {it['title']}{score} — {it['source']} — {it['url']}{summary}")
    return "\n".join(lines)


def _fallback(items: list[dict]) -> str:
    return "\n".join(f"- [{it['title']}]({it['url']}) — {it['source']}" for it in items)


def synthesize(label: str, items: list[dict], feedback: str = "") -> str:
    items_block = _format_items(items)

    if not config.ANTHROPIC_API_KEY:
        if config.IS_PROD:
            raise RuntimeError("ANTHROPIC_API_KEY manquante (APP_ENV=prod) : pas de synthèse")
        print("  [synthèse] ANTHROPIC_API_KEY absente -> liste brute")
        return _fallback(items)

    feedback_block = (
        f"\nConsigne supplémentaire de l'utilisateur (à appliquer) : {feedback}\n"
        if feedback else ""
    )
    prompt = PROMPT.format(label=label, feedback_block=feedback_block, items_block=items_block)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        if config.IS_PROD:
            raise                       # en prod : échec bruyant, pas de repli silencieux
        print(f"  [synthèse] erreur API ({e}) -> repli liste brute")
        return _fallback(items)
