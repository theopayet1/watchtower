"""Livraison du digest par email.

⚠️ PIÈGE CLOUD : en routine distante, l'egress SMTP (ports 25/587) est très
souvent bloqué par la sandbox (anti-spam), MÊME en réseau "Full" qui n'autorise
que le HTTP(S) 443. Conséquence : un envoi SMTP peut marcher en local et échouer
en cloud avec des identifiants pourtant corrects.
=> En cloud, on passe par une API HTTP (Resend ou Brevo) qui sort en HTTPS 443.

Choix du backend (config.EMAIL_BACKEND, défaut "auto") :
  1. resend  si RESEND_API_KEY défini   (HTTP 443 — local ET cloud) ✅ recommandé cloud
  2. brevo   si BREVO_API_KEY défini     (HTTP 443 — local ET cloud) ✅ recommandé cloud
  3. smtp    si identifiants SMTP définis (fiable en local, risqué en cloud)
  4. file    dernier recours : écrit last_digest.md (pour tester sans rien configurer)
"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path

import requests

import config

ROOT = Path(__file__).resolve().parent
RESEND_URL = "https://api.resend.com/emails"
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _write_local(subject: str, body: str) -> Path:
    path = ROOT / "last_digest.md"
    path.write_text(f"# {subject}\n\n{body}", encoding="utf-8")
    return path


def _send_resend(subject: str, body: str) -> None:
    r = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
        json={
            "from": config.EMAIL_FROM,
            "to": [config.EMAIL_TO],
            "subject": subject,
            "text": body,
        },
        timeout=30,
    )
    r.raise_for_status()


def _send_brevo(subject: str, body: str) -> None:
    r = requests.post(
        BREVO_URL,
        headers={"api-key": config.BREVO_API_KEY, "accept": "application/json"},
        json={
            "sender": {"email": config.EMAIL_FROM},
            "to": [{"email": config.EMAIL_TO}],
            "subject": subject,
            "textContent": body,
        },
        timeout=30,
    )
    r.raise_for_status()


def _send_smtp(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM or config.SMTP_USER
    msg["To"] = config.EMAIL_TO
    msg["Date"] = formatdate(localtime=True)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(msg["From"], [config.EMAIL_TO], msg.as_string())


def resolve_backend() -> str:
    """Détermine le backend d'envoi effectif (sans rien envoyer)."""
    choice = (config.EMAIL_BACKEND or "auto").lower()
    if choice != "auto":
        return choice
    if config.RESEND_API_KEY:
        return "resend"
    if config.BREVO_API_KEY:
        return "brevo"
    if config.SMTP_USER and config.SMTP_PASSWORD:
        return "smtp"
    return "file"


def send(subject: str, body: str) -> None:
    if not config.EMAIL_TO:
        if config.IS_PROD:
            raise RuntimeError("EMAIL_TO manquant (APP_ENV=prod) : aucun destinataire")
        path = _write_local(subject, body)
        print(f"  [email] EMAIL_TO absent -> digest écrit dans {path}")
        return

    backend = resolve_backend()
    senders = {"resend": _send_resend, "brevo": _send_brevo, "smtp": _send_smtp}

    if backend not in senders:        # "file" ou valeur inconnue
        if config.IS_PROD:
            raise RuntimeError(
                f"aucun backend d'envoi réel (EMAIL_BACKEND={config.EMAIL_BACKEND!r}) "
                "en APP_ENV=prod : le digest ne partirait pas"
            )
        path = _write_local(subject, body)
        print(f"  [email] aucun backend d'envoi configuré -> digest écrit dans {path}")
        return

    try:
        senders[backend](subject, body)
        print(f"  [email] envoyé via {backend} à {config.EMAIL_TO}")
    except Exception as e:
        if config.IS_PROD:
            raise                       # en prod : échec bruyant (routine ROUGE)
        path = _write_local(subject, body)
        print(f"  [email] échec {backend} ({e}) -> digest écrit dans {path}")
