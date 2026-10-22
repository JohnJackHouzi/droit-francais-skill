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
PRIX = os.environ.get("DROIT_PRIX", "4,99")
CENTIMES = int(round(float(PRIX.replace(",", ".")) * 100))
ESSAI_PAR_JOUR = int(os.environ.get("DROIT_ESSAI_PAR_JOUR", "20"))
PLAFOND_ABONNE = int(os.environ.get("DROIT_PLAFOND_ABONNE", "500"))
PLAFOND_PRO = int(os.environ.get("DROIT_PLAFOND_PRO", "3000"))
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


def _centimes(prix):
    return int(round(float(prix.replace(",", ".")) * 100))


OFFRES = {
    "particulier": {"nom": "Particulier", "prix": PRIX, "intervalle": "month", "plafond": PLAFOND_ABONNE,
                    "price_id": os.environ.get("DROIT_STRIPE_PRICE_ID", ""), "pro": False},
    "pro": {"nom": "Pro", "prix": os.environ.get("DROIT_PRIX_PRO", "19"), "intervalle": "month", "plafond": PLAFOND_PRO,
            "price_id": os.environ.get("DROIT_STRIPE_PRICE_PRO", ""), "pro": True},
    "pro-an": {"nom": "Pro annuel", "prix": os.environ.get("DROIT_PRIX_PRO_AN", "190"), "intervalle": "year",
               "plafond": PLAFOND_PRO, "price_id": os.environ.get("DROIT_STRIPE_PRICE_PRO_AN", ""), "pro": True},
}


def offre_de(row):
    try:
        cle = row["offre"]
    except (IndexError, KeyError):
        cle = "particulier"
    return OFFRES.get(cle or "particulier", OFFRES["particulier"])

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
            _con.execute("ALTER TABLE cles ADD COLUMN offre TEXT NOT NULL DEFAULT 'particulier'")
        except sqlite3.OperationalError:
            pass
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


def consommer_abonne(abonnement, n=1, plafond=None):
    """Plafond quotidien par abonné : repère une adresse personnelle partagée."""
    jour = _jour()
    with _verrou:
        c = db()
        row = c.execute("SELECT n FROM usages WHERE abonnement=? AND jour=?", (abonnement, jour)).fetchone()
        deja = row["n"] if row else 0
        if deja + n > (plafond or PLAFOND_ABONNE):
            return False, deja
        c.execute("INSERT INTO usages (abonnement, jour, n) VALUES (?, ?, ?) ON CONFLICT(abonnement, jour) DO UPDATE SET n = n + ?",
                  (abonnement, jour, n, n))
        return True, deja + n


def consommer_ia(abonnement, quota):
    """Analyses de conformité en ligne : compteur mensuel (clé ia:AAAA-MM dans la table usages)."""
    mois = "ia:" + _jour()[:7]
    with _verrou:
        c = db()
        row = c.execute("SELECT n FROM usages WHERE abonnement=? AND jour=?", (abonnement, mois)).fetchone()
        deja = row["n"] if row else 0
        if deja >= quota:
            return False, deja
        c.execute("INSERT INTO usages (abonnement, jour, n) VALUES (?, ?, 1) ON CONFLICT(abonnement, jour) DO UPDATE SET n = n + 1",
                  (abonnement, mois))
        return True, deja + 1


def purger_essais():
    limite = datetime.fromtimestamp(time.time() - 2 * 86400, timezone.utc).strftime("%Y-%m-%d")
    db().execute("DELETE FROM essais WHERE jour < ?", (limite,))
    mois = datetime.fromtimestamp(time.time() - 31 * 86400, timezone.utc).strftime("%Y-%m-%d")
    db().execute("DELETE FROM usages WHERE jour < ? OR (jour LIKE 'ia:%' AND jour < ?)", (mois, "ia:" + mois[:7]))
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


async def creer_session(demande_execution, offre="particulier"):
    o = OFFRES[offre]
    libelle = "Droit by Studjoow : %s" % ("abonnement mensuel" if offre == "particulier" else
                                           "offre Pro " + ("mensuelle" if o["intervalle"] == "month" else "annuelle"))
    ligne = ({"price": o["price_id"], "quantity": 1} if o["price_id"] else {
        "price_data": {"currency": "eur", "unit_amount": _centimes(o["prix"]), "recurring": {"interval": o["intervalle"]},
                       "product_data": {"name": libelle}},
        "quantity": 1})
    meta = {"app": APP, "demande_execution": demande_execution, "offre": offre}
    extra = {"tax_id_collection": {"enabled": True}, "billing_address_collection": "required"} if o["pro"] else {}
    return await stripe("POST", "/v1/checkout/sessions", {**extra,
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
    offre = (abo.get("metadata") or {}).get("offre")
    offre = offre if offre in OFFRES else "particulier"
    c = db()
    with _verrou:
        c.execute(
            "INSERT OR IGNORE INTO cles (abonnement, client, email, statut, statut_stripe, version, hash, fin_periode,"
            " resiliation_prevue, demande_execution, cree_le, maj_le, offre) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
            (sid, client, email, statut_de(st), st, empreinte(cle_de(sid, 1)), _fin_periode(abo),
             _resiliation(abo), (abo.get("metadata") or {}).get("demande_execution"),
             maintenant(), maintenant(), offre))
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


LOGO_MAIL = os.environ.get("DROIT_EMAIL_LOGO", "picto")
POLICE = "Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"


def _bandeau():
    if LOGO_MAIL == "studjoow":
        logo = ('<img src="%s/static/email/logo-studjoow.png" width="64" height="64" alt="Studjoow" '
                'style="display:block;border:0;border-radius:14px">' % SITE)
    else:
        logo = ('<img src="%s/static/email/picto.png" width="48" height="48" alt="Studjoow" '
                'style="display:block;border:0;border-radius:12px">' % SITE)
    return ('<tr><td style="background:#040e30;background-image:linear-gradient(135deg,#2a1240 0%%,#040e30 60%%);'
            'padding:26px 32px;border-radius:18px 18px 0 0">'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td style="padding-right:14px;vertical-align:middle">%s</td>'
            '<td style="vertical-align:middle;font-family:%s;color:#ffffff;font-size:20px;line-height:1.1">Droit '
            '<span style="color:#e0539f;font-style:italic">by Studjoow</span><br>'
            '<span style="font-family:%s;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8a90a3">'
            'Le droit officiel, sourcé</span></td></tr></table></td></tr>') % (logo, SERIF, POLICE)


def _bouton(texte, url):
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 4px"><tr>'
            '<td style="background:#b1338a;border-radius:10px"><a href="%s" style="display:inline-block;padding:13px 22px;'
            'font-family:%s;font-size:15px;font-weight:bold;color:#ffffff;text-decoration:none">%s</a></td></tr></table>'
            % (url, POLICE, texte))


def _gabarit(titre, blocs, apercu=""):
    """Mail aux couleurs du site : bandeau sombre, carte blanche, tables pour Gmail et Outlook."""
    import html as h
    corps = "".join(blocs)
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta name="color-scheme" content="light only"><title>%(titre)s</title></head>'
            '<body style="margin:0;padding:0;background:#f2f3fb">'
            '<div style="display:none;max-height:0;overflow:hidden;opacity:0">%(apercu)s</div>'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="background:#f2f3fb">'
            '<tr><td align="center" style="padding:28px 12px">'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="max-width:580px">'
            '%(bandeau)s'
            '<tr><td style="background:#ffffff;padding:34px 32px 30px;border-radius:0 0 18px 18px;font-family:%(police)s;'
            'color:#1b0b16;font-size:15.5px;line-height:1.6">'
            '<h1 style="margin:0 0 18px;font-family:%(serif)s;font-weight:normal;font-size:30px;line-height:1.15;color:#1b0b16">%(titre)s</h1>'
            '%(corps)s</td></tr>'
            '<tr><td style="padding:22px 32px 6px;font-family:%(police)s;font-size:12.5px;line-height:1.6;color:#7e8493;text-align:center">'
            'Droit by Studjoow · <a href="%(site)s" style="color:#7e8493">%(domaine)s</a> · '
            '<a href="%(site)s/compte" style="color:#7e8493">Mon compte</a> · <a href="%(site)s/cgv" style="color:#7e8493">CGV</a><br>'
            'Information juridique, pas un conseil : pour un cas concret, consultez un avocat.</td></tr>'
            '</table></td></tr></table></body></html>') % {
        "titre": h.escape(titre), "apercu": h.escape(apercu), "bandeau": _bandeau(), "corps": corps,
        "police": POLICE, "serif": SERIF, "site": SITE, "domaine": SITE.split("//")[1]}


def _p(texte, style=""):
    return '<p style="margin:0 0 16px;%s">%s</p>' % (style, texte)


def _adresse_bloc(url):
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 8px">'
            '<tr><td style="background:#f2f3fb;border-left:4px solid #b1338a;border-radius:0 12px 12px 0;padding:16px 18px">'
            '<div style="font-family:%s;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:#7e8493;margin-bottom:6px">'
            'Votre adresse personnelle</div>'
            '<div style="font-family:Menlo,Consolas,monospace;font-size:14px;line-height:1.5;color:#1b0b16;word-break:break-all">'
            '<a href="%s" style="color:#1b0b16;text-decoration:none">%s</a></div></td></tr></table>'
            '<p style="margin:0 0 22px;font-size:13.5px;color:#7e8493">Gardez-la pour vous : elle donne accès à votre abonnement.</p>'
            % (POLICE, url, url))


def _etapes():
    lignes = [("Claude", "Paramètres, puis Connecteurs, puis <b>Ajouter un connecteur personnalisé</b>. Collez l'adresse, sans authentification."),
              ("ChatGPT", "Paramètres, puis Applications et connecteurs, <b>Créer</b> un connecteur avec cette adresse."),
              ("Essayez", "Demandez : « Que dit l'article 1240 du Code civil ? »")]
    rangs = "".join(
        '<tr><td style="vertical-align:top;padding:0 12px 12px 0;width:28px"><div style="width:26px;height:26px;border-radius:13px;'
        'background:#eddaec;color:#b1338a;font-family:%s;font-weight:bold;font-size:13px;line-height:26px;text-align:center">%d</div></td>'
        '<td style="vertical-align:top;padding:2px 0 12px;font-size:14.5px;line-height:1.5"><b>%s</b> : %s</td></tr>'
        % (POLICE, n + 1, t, d) for n, (t, d) in enumerate(lignes))
    return ('<h2 style="margin:0 0 12px;font-family:%s;font-weight:normal;font-size:21px">L\'installer en 30 secondes</h2>'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 14px">%s</table>' % (SERIF, rangs))


def _recap(row):
    o = offre_de(row)
    fin = (row["fin_periode"] or "")[:10]
    fin = "%s/%s/%s" % (fin[8:10], fin[5:7], fin[:4]) if fin else ""
    lignes = [("Offre", "%s, %s € par %s" % (o["nom"], o["prix"], "mois" if o["intervalle"] == "month" else "an")),
              ("Inclus", "%s requêtes par jour, toutes les sources" % "{:,}".format(o["plafond"]).replace(",", " "))]
    if fin:
        lignes.append(("Prochain prélèvement", fin))
    rangs = "".join('<tr><td style="padding:6px 16px 6px 0;color:#7e8493;font-size:13.5px;white-space:nowrap">%s</td>'
                    '<td style="padding:6px 0;font-size:14px">%s</td></tr>' % l for l in lignes)
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
            'style="border-top:1px solid #d8dbe4;border-bottom:1px solid #d8dbe4;margin:8px 0 22px">%s</table>' % rangs)


async def envoyer_cle_si_besoin(abonnement):
    c = db()
    cur = c.execute("UPDATE cles SET email_envoye=1 WHERE abonnement=? AND email_envoye=0 AND email IS NOT NULL",
                    (abonnement,))
    if cur.rowcount != 1:
        return False
    row = c.execute("SELECT * FROM cles WHERE abonnement=?", (abonnement,)).fetchone()
    url = adresse(cle_de(abonnement, row["version"]))
    ok = await envoyer_email(row["email"], "Votre accès Droit by Studjoow est prêt", _gabarit(
        "Votre accès est prêt.", [
            _p("Merci pour votre confiance. Votre abonnement est actif : collez l'adresse ci-dessous dans Claude ou "
               "ChatGPT, et votre assistant s'appuiera sur les textes officiels, vérifiés avant d'être cités."),
            _adresse_bloc(url),
            _etapes(),
            _recap(row),
            _bouton("Gérer mon abonnement", SITE + "/compte"),
            _p("Depuis votre compte : facture, carte bancaire, résiliation en un clic, ou nouvelle adresse si vous pensez "
               "qu'elle a circulé.", "margin-top:14px;font-size:13.5px;color:#7e8493"),
            _p("Vous avez demandé l'accès immédiat. Vous pouvez changer d'avis dans les 14 jours : vous êtes remboursé, "
               "moins les jours déjà utilisés (<a href=\"%s/cgv\" style=\"color:#b1338a\">CGV</a>)." % SITE,
               "font-size:13px;color:#7e8493;margin:0"),
        ], "Votre adresse personnelle et l'installation en 30 secondes."),
        "Votre accès Droit by Studjoow est prêt.\n\nVotre adresse personnelle : %s\n\nClaude : Paramètres > Connecteurs > "
        "Ajouter un connecteur personnalisé, collez l'adresse.\nChatGPT : Paramètres > Applications et connecteurs > Créer.\n\n"
        "Gérer ou résilier : %s/compte\nCGV : %s/cgv\n" % (url, SITE, SITE))
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
        await envoyer_email(email, "Accès à votre abonnement Droit by Studjoow", _gabarit(
            "Accès à votre compte.", [
                _p("Vous avez demandé à retrouver votre adresse personnelle. Ce lien est valable une heure :"),
                _bouton("Ouvrir mon compte", lien),
                _p("Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : rien ne change.",
                   "margin-top:16px;font-size:13.5px;color:#7e8493"),
            ], "Votre lien d'accès, valable une heure."), "Ouvrir mon compte (valable 1 h) : %s\n" % lien)
    return len(rows)


def json_rpc_erreur(ids, message):
    """Réponse à un appel d'outil refusé : visible par l'assistant, qui peut la relayer."""
    rep = [{"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": message}], "isError": True}}
           for i in ids]
    return json.dumps(rep[0] if len(rep) == 1 else rep, ensure_ascii=False).encode()


# Back-office (lu par l'admin Studjoow avec un jeton secret).

ADMIN_JETON = os.environ.get("DROIT_ADMIN_TOKEN", "")


def admin_autorise(entete):
    if not ADMIN_JETON or not entete.startswith("Bearer "):
        return False
    return hmac.compare_digest(entete[7:].strip().encode(), ADMIN_JETON.encode())


def _mensuel(offre):
    o = OFFRES.get(offre or "particulier", OFFRES["particulier"])
    centimes = _centimes(o["prix"])
    return centimes if o["intervalle"] == "month" else round(centimes / 12)


def resume_admin():
    c = db()
    jour, mois = _jour(), _jour()[:7]
    rows = c.execute("SELECT * FROM cles ORDER BY cree_le DESC").fetchall()
    usages = {(r["abonnement"], r["jour"]): r["n"] for r in c.execute(
        "SELECT abonnement, jour, n FROM usages WHERE jour IN (?, ?)", (jour, "ia:" + mois))}
    abonnes = []
    for r in rows:
        offre = r["offre"] if "offre" in r.keys() else "particulier"
        abonnes.append({
            "abonnement": r["abonnement"], "client": r["client"], "email": r["email"], "offre": offre,
            "statut": r["statut"], "statut_stripe": r["statut_stripe"], "cree_le": r["cree_le"], "maj_le": r["maj_le"],
            "fin_periode": r["fin_periode"], "resiliation_prevue": bool(r["resiliation_prevue"]),
            "requetes_jour": usages.get((r["abonnement"], jour), 0),
            "analyses_mois": usages.get((r["abonnement"], "ia:" + mois), 0),
            "plafond": OFFRES.get(offre, OFFRES["particulier"])["plafond"],
        })
    actifs = [a for a in abonnes if a["statut"] == "actif"]
    par_offre = {k: sum(1 for a in actifs if a["offre"] == k) for k in OFFRES}
    essais = c.execute("SELECT jour, count(*) AS visiteurs, sum(n >= ?) AS au_plafond, sum(n) AS requetes "
                       "FROM essais GROUP BY jour ORDER BY jour DESC", (ESSAI_PAR_JOUR,)).fetchall()
    evenements = c.execute("SELECT type, recu_le FROM evenements ORDER BY recu_le DESC LIMIT 15").fetchall()
    return {
        "genere_le": maintenant(),
        "mode_stripe": "live" if STRIPE_CLE.startswith(("sk_live", "rk_live")) else "test",
        "chiffres": {
            "actifs": len(actifs), "par_offre": par_offre,
            "suspendus": sum(1 for a in abonnes if a["statut"] == "suspendu"),
            "termines": sum(1 for a in abonnes if a["statut"] == "revoque"),
            "resiliations_prevues": sum(1 for a in actifs if a["resiliation_prevue"]),
            "revenu_mensuel_centimes": sum(_mensuel(a["offre"]) for a in actifs),
            "nouveaux_ce_mois": sum(1 for a in abonnes if (a["cree_le"] or "").startswith(mois)),
            "termines_ce_mois": sum(1 for a in abonnes if a["statut"] == "revoque" and (a["maj_le"] or "").startswith(mois)),
        },
        "essais": [{"jour": e["jour"], "visiteurs": e["visiteurs"], "au_plafond": e["au_plafond"] or 0,
                    "requetes": e["requetes"] or 0} for e in essais],
        "evenements": [{"type": e["type"], "recu_le": e["recu_le"]} for e in evenements],
        "abonnes": abonnes,
        "offres": {k: {"nom": o["nom"], "prix": o["prix"], "intervalle": o["intervalle"], "plafond": o["plafond"]}
                   for k, o in OFFRES.items()},
    }


async def regenerer_et_envoyer(abonnement):
    row = db().execute("SELECT * FROM cles WHERE abonnement=?", (abonnement,)).fetchone()
    if not row:
        return None
    cle = regenerer(abonnement)
    envoye = False
    if row["email"]:
        url = adresse(cle)
        envoye = await envoyer_email(row["email"], "Votre nouvelle adresse Droit by Studjoow", _gabarit(
            "Votre nouvelle adresse.", [
                _p("Par sécurité, votre adresse personnelle a été renouvelée : l'ancienne ne fonctionne plus. "
                   "Remplacez-la dans vos connecteurs Claude ou ChatGPT."),
                _adresse_bloc(url),
                _p("Une question : répondez simplement à ce message.", "font-size:13.5px;color:#7e8493;margin:0"),
            ], "Remplacez l'ancienne adresse dans vos connecteurs."), "Votre nouvelle adresse personnelle : %s\n" % url)
    return {"regeneree": True, "email_envoye": envoye}
