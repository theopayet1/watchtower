"""Chargement de la configuration : variables d'environnement (.env) + sources.yaml.

Tout le reste du code importe ses clés et sa config d'ici : un seul point d'entrée.
Les chemins sont résolus par rapport à CE fichier (pas au répertoire courant),
pour que ça marche aussi en exécution distante où le cwd peut changer.
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# En local : charge .env. En cloud : les variables sont déjà injectées dans l'env,
# et load_dotenv ne fait rien si le fichier n'existe pas.
load_dotenv(ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name, default)
    return val.strip() if isinstance(val, str) else val


# --- Environnement d'exécution ---
# "dev" (défaut) -> replis silencieux actifs (pratique pour tester en local).
# "prod"         -> échec BRUYANT si une config critique manque (routine cloud).
APP_ENV = (_env("APP_ENV", "dev") or "dev").lower()
IS_PROD = APP_ENV == "prod"


# --- Anthropic (étape 6) ---
# En cloud (Claude Code web), le nom ANTHROPIC_API_KEY est RÉSERVÉ par la plateforme
# et n'est pas transmis à nos scripts. On lit donc d'abord un nom personnalisé,
# avec repli sur ANTHROPIC_API_KEY pour le dev local.
ANTHROPIC_API_KEY = _env("VEILLE_ANTHROPIC_API_KEY") or _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-opus-4-8")

# --- Supabase (étape 5) ---
SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_KEY = _env("SUPABASE_KEY")

# --- Email ---
# Backend d'envoi : auto | resend | brevo | smtp | file
# En CLOUD (routine distante), privilégier resend/brevo (API HTTPS 443) : le SMTP
# (ports 25/587) y est souvent bloqué par la sandbox anti-spam.
EMAIL_BACKEND = _env("EMAIL_BACKEND", "auto")
RESEND_API_KEY = _env("RESEND_API_KEY")
BREVO_API_KEY = _env("BREVO_API_KEY")
SMTP_HOST = _env("SMTP_HOST", "smtp-mail.outlook.com")
SMTP_PORT = int(_env("SMTP_PORT", "587") or 587)
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
EMAIL_FROM = _env("EMAIL_FROM")
EMAIL_TO = _env("EMAIL_TO")

# --- Réglages globaux des sources (utilisés quand les sources viennent de la BDD) ---
MAX_PER_SOURCE = int(_env("MAX_PER_SOURCE", "15") or 15)
FRESHNESS_HOURS = int(_env("FRESHNESS_HOURS", "30") or 30)


def load_sources(path: str | Path | None = None) -> dict:
    """Lit sources.yaml et renvoie la config (catégories, limites, fraîcheur)."""
    path = Path(path) if path else ROOT / "sources.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "categories" not in data:
        raise ValueError(f"{path} : clé 'categories' manquante")
    return data
