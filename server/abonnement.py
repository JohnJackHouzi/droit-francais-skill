import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

DATA = Path(os.environ.get("DROIT_DATA", Path(__file__).resolve().parent.parent / "data"))
BASE = Path(os.environ.get("DROIT_ABONNES_DB", DATA / "abonnes.sqlite"))
SITE = os.environ.get("DROIT_PUBLIC_URL", "https://droit.studjoow.com").rstrip("/")
PRIX = os.environ.get("DROIT_PRIX", "2,99")
CENTIMES = int(round(float(PRIX.replace(",", ".")) * 100))
ESSAI_PAR_JOUR = int(os.environ.get("DROIT_ESSAI_PAR_JOUR", "20"))
PLAFOND_ABONNE = int(os.environ.get("DROIT_PLAFOND_ABONNE", "500"))
SECRET = os.environ.get("DROIT_SECRET", "").encode()
STRIPE_CLE = os.environ.get("DROIT_STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK = os.environ.get("DROIT_STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRIX_ID = os.environ.get("DROIT_STRIPE_PRICE_ID", "")
STRIPE_PORTAIL = os.environ.get("DROIT_STRIPE_PORTAL_CONFIG", "")
STRIPE_API = os.environ.get("DROIT_STRIPE_API", "https://api.stripe.com")
RESEND_CLE = os.environ.get("DROIT_RESEND_API_KEY", "")
RESEND_API = os.environ.get("DROIT_RESEND_API", "https://api.resend.com")
EXPEDITEUR = os.environ.get("DROIT_EMAIL_FROM", "Droit français sourcé <droit@studjoow.com>")
APP = "droit"

ACTIFS = ("active", "trialing")
SUSPENDUS = ("past_due", "unpaid", "incomplete", "paused")

_verrou = threading.Lock()
_purge = {"jour": None}
_con = None


def maintenant():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def actif():
    return bool(SECRET and STRIPE_CLE and STRIPE_WEBHOOK)


def db():
    global _con
    if _con is None:
        BASE.parent.mkdir(parents=True, exist_ok=True)
        _con = sqlite3.connect(str(BASE), check_same_thread=False, isolation_level=None, timeout=10)
        _con.row_factory = sqlite3.Row
        _con.executescript(SCHEMA)
        try:
            os.chmod(BASE, 0o600)
        except OSError:
            pass
    return _con


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS cles (
  abonnement TEXT PRIMARY KEY,
  client TEXT NOT NULL,
  email TEXT,
  statut TEXT NOT NULL,
  statut_stripe TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  hash TEXT NOT NULL UNIQUE,
  affichee INTEGER NOT NULL DEFAULT 0,
  email_envoye INTEGER NOT NULL DEFAULT 0,
  fin_periode TEXT,
  resiliation_prevue INTEGER NOT NULL DEFAULT 0,
  demande_execution TEXT,
  cree_le TEXT NOT NULL,
  maj_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS essais (
  ip TEXT NOT NULL,
  jour TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (ip, jour)
);
CREATE TABLE IF NOT EXISTS usages (
  abonnement TEXT NOT NULL,
  jour TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (abonnement, jour)
);
CREATE TABLE IF NOT EXISTS evenements (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  recu_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


def _sel():
    c = db()
    row = c.execute("SELECT v FROM config WHERE k='sel'").fetchone()
    if row:
        return row["v"].encode()
    sel = secrets.token_hex(32)
    c.execute("INSERT OR IGNORE INTO config (k, v) VALUES ('sel', ?)", (sel,))
    return c.execute("SELECT v FROM config WHERE k='sel'").fetchone()["v"].encode()


# Clés : dérivées du secret serveur, jamais stockées en clair (seul leur SHA-256 est en base).

def cle_de(abonnement, version):
    mac = hmac.new(SECRET, ("cle:%s:%d" % (abonnement, version)).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")[:32]


def empreinte(cle):
    return hashlib.sha256(cle.encode()).hexdigest()


def adresse(cle):
    return "%s/mcp/%s" % (SITE, cle)


def extraire_cle(texte):
    texte = (texte or "").strip().rstrip("/")
    if "/mcp/" in texte:
        texte = texte.rsplit("/mcp/", 1)[1]
    return texte if 20 <= len(texte) <= 64 and all(ch.isalnum() or ch in "-_" for ch in texte) else ""


def verifier_cle(cle):
    if not cle or not SECRET:
        return None
    h = empreinte(cle)
    row = db().execute("SELECT * FROM cles WHERE hash = ?", (h,)).fetchone()
    if row and hmac.compare_digest(row["hash"], h):
        return row
    return None


# Essai : compteur par IP hachée et par jour, purgé au-delà de 2 jours.

def _jour():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ip_hachee(ip):
    return hmac.new(_sel(), ip.encode(), hashlib.sha256).hexdigest()[:24]


def consommer_essai(ip, n=1):
    jour = _jour()
    h = ip_hachee(ip)
    with _verrou:
        c = db()
        if _purge["jour"] != jour:
            purger_essais()
            _purge["jour"] = jour
        row = c.execute("SELECT n FROM essais WHERE ip=? AND jour=?", (h, jour)).fetchone()
        deja = row["n"] if row else 0
        if deja + n > ESSAI_PAR_JOUR:
            return False, deja
        c.execute("INSERT INTO essais (ip, jour, n) VALUES (?, ?, ?) ON CONFLICT(ip, jour) DO UPDATE SET n = n + ?",
                  (h, jour, n, n))
        return True, deja + n


def consommer_abonne(abonnement, n=1):
    """Plafond quotidien par abonné : repère une adresse personnelle partagée."""
    jour = _jour()
    with _verrou:
        c = db()
        row = c.execute("SELECT n FROM usages WHERE abonnement=? AND jour=?", (abonnement, jour)).fetchone()
        deja = row["n"] if row else 0
        if deja + n > PLAFOND_ABONNE:
            return False, deja
        c.execute("INSERT INTO usages (abonnement, jour, n) VALUES (?, ?, ?) ON CONFLICT(abonnement, jour) DO UPDATE SET n = n + ?",
                  (abonnement, jour, n, n))
        return True, deja + n


def purger_essais():
    limite = datetime.fromtimestamp(time.time() - 2 * 86400, timezone.utc).strftime("%Y-%m-%d")
    db().execute("DELETE FROM essais WHERE jour < ?", (limite,))
    mois = datetime.fromtimestamp(time.time() - 31 * 86400, timezone.utc).strftime("%Y-%m-%d")
    db().execute("DELETE FROM usages WHERE jour < ?", (mois,))
    un_an = datetime.fromtimestamp(time.time() - 365 * 86400, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db().execute("DELETE FROM cles WHERE statut='revoque' AND maj_le < ?", (un_an,))
    db().execute("DELETE FROM evenements WHERE recu_le < ?", (un_an,))


# Stripe (API REST, sans SDK).

def _form(d, prefixe=""):
    out = []
    for k, v in d.items():
        cle = "%s[%s]" % (prefixe, k) if prefixe else str(k)
        if isinstance(v, dict):
            out += _form(v, cle)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                out += _form(x, "%s[%d]" % (cle, i)) if isinstance(x, dict) else [("%s[%d]" % (cle, i), str(x))]
        elif v is not None:
            out.append((cle, "true" if v is True else "false" if v is False else str(v)))
    return out


class ErreurStripe(Exception):
    pass


async def stripe(methode, chemin, donnees=None):
    try:
        async with httpx.AsyncClient(base_url=STRIPE_API, timeout=20, auth=(STRIPE_CLE, "")) as client:
            if methode == "GET":
                r = await client.get(chemin, params=_form(donnees or {}))
            else:
                r = await client.post(chemin, content=urlencode(_form(donnees or {})),
                                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        corps = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ErreurStripe("Stripe injoignable : %s" % type(exc).__name__)
    if r.status_code >= 400:
        raise ErreurStripe(corps.get("error", {}).get("message", "erreur Stripe %d" % r.status_code))
    return corps


async def creer_session(demande_execution):
    ligne = ({"price": STRIPE_PRIX_ID, "quantity": 1} if STRIPE_PRIX_ID else {
        "price_data": {"currency": "eur", "unit_amount": CENTIMES, "recurring": {"interval": "month"},
                       "product_data": {"name": "Droit by Studjoow : abonnement mensuel"}},
        "quantity": 1})
    meta = {"app": APP, "demande_execution": demande_execution}
    return await stripe("POST", "/v1/checkout/sessions", {
        "mode": "subscription",
        "line_items": [ligne],
        "success_url": SITE + "/merci?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": SITE + "/#tarifs",
        "locale": "fr",
        "metadata": meta,
        "subscription_data": {"metadata": meta},
        "custom_text": {"submit": {"message": "Accès immédiat après paiement. Sans engagement, résiliable à tout moment."}},
    })


async def configuration_portail():
    """Portail dédié « Droit by Studjoow » : le portail par défaut du compte peut appartenir à une autre marque."""
    if STRIPE_PORTAIL:
        return STRIPE_PORTAIL
    mode = "live" if STRIPE_CLE.startswith(("sk_live", "rk_live")) else "test"
    row = db().execute("SELECT v FROM config WHERE k=?", ("portail_" + mode,)).fetchone()
    if row:
        return row["v"]
    conf = await stripe("POST", "/v1/billing_portal/configurations", {
        "business_profile": {"headline": "Droit by Studjoow : gérez votre abonnement",
                             "privacy_policy_url": SITE + "/confidentialite", "terms_of_service_url": SITE + "/cgv"},
        "features": {"subscription_cancel": {"enabled": True, "mode": "at_period_end"},
                     "payment_method_update": {"enabled": True}, "invoice_history": {"enabled": True},
                     "customer_update": {"enabled": True, "allowed_updates": ["email"]}},
        "default_return_url": SITE + "/compte",
        "metadata": {"app": APP},
    })
    db().execute("INSERT OR REPLACE INTO config (k, v) VALUES (?, ?)", ("portail_" + mode, conf["id"]))
    return conf["id"]


async def creer_portail(client):
    return await stripe("POST", "/v1/billing_portal/sessions", {
        "customer": client, "return_url": SITE + "/compte", "locale": "fr", "configuration": await configuration_portail()})


def statut_de(statut_stripe):
    if statut_stripe in ACTIFS:
        return "actif"
    if statut_stripe in SUSPENDUS:
        return "suspendu"
    return "revoque"


def _date(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None


def _fin_periode(abo):
    fin = abo.get("current_period_end")
    if not fin:
        items = (abo.get("items") or {}).get("data") or []
        fin = items[0].get("current_period_end") if items else None
    return _date(fin)


def _resiliation(abo):
    return 1 if abo.get("cancel_at_period_end") or abo.get("cancel_at") else 0


def enregistrer_abonnement(abo, email=None):
    """Crée ou met à jour la ligne d'un abonnement Stripe ; idempotent."""
    if (abo.get("metadata") or {}).get("app") != APP:
        return None
    sid, client = abo["id"], abo["customer"]
    st = abo.get("status", "")
    c = db()
    with _verrou:
        c.execute(
            "INSERT OR IGNORE INTO cles (abonnement, client, email, statut, statut_stripe, version, hash, fin_periode,"
            " resiliation_prevue, demande_execution, cree_le, maj_le) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
            (sid, client, email, statut_de(st), st, empreinte(cle_de(sid, 1)), _fin_periode(abo),
             _resiliation(abo), (abo.get("metadata") or {}).get("demande_execution"),
             maintenant(), maintenant()))
        c.execute(
            "UPDATE cles SET statut=?, statut_stripe=?, fin_periode=COALESCE(?, fin_periode), resiliation_prevue=?,"
            " email=COALESCE(email, ?), maj_le=? WHERE abonnement=?",
            (statut_de(st), st, _fin_periode(abo), _resiliation(abo), email, maintenant(), sid))
    return c.execute("SELECT * FROM cles WHERE abonnement=?", (sid,)).fetchone()


def regenerer(abonnement):
    c = db()
    with _verrou:
        row = c.execute("SELECT version FROM cles WHERE abonnement=?", (abonnement,)).fetchone()
        v = row["version"] + 1
        c.execute("UPDATE cles SET version=?, hash=?, maj_le=? WHERE abonnement=?",
                  (v, empreinte(cle_de(abonnement, v)), maintenant(), abonnement))
    return cle_de(abonnement, v)


def marquer_affichee(abonnement):
    cur = db().execute("UPDATE cles SET affichee=1 WHERE abonnement=? AND affichee=0", (abonnement,))
    return cur.rowcount == 1


# Webhook Stripe : signature vérifiée, événements traités une seule fois.

def signature_valide(corps, entete, tolerance=300):
    if not STRIPE_WEBHOOK or not entete:
        return False
    parts = {}
    for morceau in entete.split(","):
        k, _, v = morceau.partition("=")
        parts.setdefault(k.strip(), []).append(v.strip())
    try:
        t = int(parts.get("t", ["0"])[0])
    except ValueError:
        return False
    if abs(time.time() - t) > tolerance:
        return False
    attendu = hmac.new(STRIPE_WEBHOOK.encode(), b"%d." % t + corps, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(attendu, s) for s in parts.get("v1", []))


async def traiter_evenement(ev):
    """Renvoie un court compte rendu ; lève une exception pour que Stripe rejoue."""
    c = db()
    if c.execute("SELECT 1 FROM evenements WHERE id=?", (ev["id"],)).fetchone():
        return "déjà traité"
    t, obj = ev["type"], ev["data"]["object"]
    abo_id, email = None, None
    if t == "checkout.session.completed":
        if (obj.get("metadata") or {}).get("app") != APP or obj.get("mode") != "subscription":
            abo_id = None
        else:
            abo_id = obj.get("subscription")
            email = (obj.get("customer_details") or {}).get("email")
    elif t in ("customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.created"):
        abo_id = obj["id"] if (obj.get("metadata") or {}).get("app") == APP else None
    elif t == "invoice.payment_failed":
        abo_id = obj.get("subscription") or ((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    compte = "ignoré"
    if abo_id:
        abo = await stripe("GET", "/v1/subscriptions/%s" % abo_id)
        if not email and (abo.get("metadata") or {}).get("app") == APP:
            email = (await stripe("GET", "/v1/customers/%s" % abo["customer"])).get("email")
        row = enregistrer_abonnement(abo, email)
        if row:
            compte = "%s -> %s" % (abo_id, row["statut"])
            if t == "checkout.session.completed":
                await envoyer_cle_si_besoin(row["abonnement"])
    c.execute("INSERT OR IGNORE INTO evenements (id, type, recu_le) VALUES (?, ?, ?)", (ev["id"], t, maintenant()))
    return compte


# E-mails (Resend).

async def envoyer_email(a, sujet, html_corps, texte):
    if not RESEND_CLE:
        return False
    async with httpx.AsyncClient(base_url=RESEND_API, timeout=20) as client:
        r = await client.post("/emails", headers={"Authorization": "Bearer " + RESEND_CLE},
                              json={"from": EXPEDITEUR, "to": [a], "subject": sujet, "html": html_corps, "text": texte,
                                    "reply_to": "hello@studjoow.com"})
    return r.status_code < 300


def _gabarit(titre, paragraphes):
    import html as h
    corps = "".join('<p style="margin:0 0 14px">%s</p>' % p for p in paragraphes)
    return ('<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1b0b16;line-height:1.55">'
            '<p style="color:#b1338a;font-weight:bold;margin:0 0 6px">Droit français sourcé</p>'
            '<h1 style="font-size:22px;margin:0 0 18px">%s</h1>%s'
            '<p style="color:#7e8493;font-size:12px;margin-top:28px">Un service Studjoow · <a href="%s" style="color:#7e8493">%s</a>'
            ' · Information juridique, pas conseil.</p></div>') % (h.escape(titre), corps, SITE, SITE.split("//")[1])


async def envoyer_cle_si_besoin(abonnement):
    c = db()
    cur = c.execute("UPDATE cles SET email_envoye=1 WHERE abonnement=? AND email_envoye=0 AND email IS NOT NULL",
                    (abonnement,))
    if cur.rowcount != 1:
        return False
    row = c.execute("SELECT * FROM cles WHERE abonnement=?", (abonnement,)).fetchone()
    url = adresse(cle_de(abonnement, row["version"]))
    ok = await envoyer_email(row["email"], "Votre adresse personnelle Droit français sourcé", _gabarit(
        "Votre abonnement est actif", [
            "Merci pour votre abonnement à %s € par mois, sans engagement." % PRIX,
            "Votre adresse personnelle, à coller comme connecteur dans Claude ou ChatGPT :",
            '<code style="background:#f2f3fb;padding:8px 10px;border-radius:6px;display:inline-block;word-break:break-all">%s</code>' % url,
            "Gardez-la pour vous : elle donne accès à votre abonnement. En cas de doute, régénérez-la depuis "
            '<a href="%s/compte">votre compte</a>, où vous pouvez aussi gérer ou résilier l\'abonnement.' % SITE,
            "Vous avez demandé l'accès immédiat au service. Vous gardez un droit de rétractation de 14 jours "
            "(conditions dans nos <a href=\"%s/cgv\">CGV</a>)." % SITE,
        ]), "Votre adresse personnelle : %s\nGérer ou résilier : %s/compte\nCGV : %s/cgv\n" % (url, SITE, SITE))
    if not ok:
        c.execute("UPDATE cles SET email_envoye=0 WHERE abonnement=?", (abonnement,))
    return ok


# Lien d'accès au compte par e-mail (adresse perdue), valable 1 h.

def jeton_acces(abonnement, duree=3600):
    exp = int(time.time()) + duree
    charge = "%s.%d" % (abonnement, exp)
    sig = hmac.new(SECRET, ("acces:" + charge).encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(("%s.%s" % (charge, sig)).encode()).decode().rstrip("=")


def lire_jeton(jeton):
    try:
        brut = base64.urlsafe_b64decode(jeton + "=" * (-len(jeton) % 4)).decode()
        abonnement, exp, sig = brut.rsplit(".", 2)
    except Exception:
        return None
    attendu = hmac.new(SECRET, ("acces:%s.%s" % (abonnement, exp)).encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(attendu, sig) or int(exp) < time.time():
        return None
    return abonnement


async def envoyer_lien_acces(email):
    rows = db().execute("SELECT abonnement FROM cles WHERE lower(email)=lower(?) AND statut!='revoque'", (email,)).fetchall()
    for row in rows:
        lien = "%s/compte/acces?j=%s" % (SITE, jeton_acces(row["abonnement"]))
        await envoyer_email(email, "Accès à votre abonnement Droit français sourcé", _gabarit(
            "Accès à votre compte", [
                "Vous avez demandé à retrouver votre adresse personnelle. Ce lien est valable une heure :",
                '<a href="%s" style="color:#b1338a">Ouvrir mon compte</a>' % lien,
                "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
            ]), "Ouvrir mon compte (valable 1 h) : %s\n" % lien)
    return len(rows)


def json_rpc_erreur(ids, message):
    """Réponse à un appel d'outil refusé : visible par l'assistant, qui peut la relayer."""
    rep = [{"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": message}], "isError": True}}
           for i in ids]
    return json.dumps(rep[0] if len(rep) == 1 else rep, ensure_ascii=False).encode()
