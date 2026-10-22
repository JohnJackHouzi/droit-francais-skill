"""Connexion OAuth 2.1 des abonnés (spécification MCP) : l'assistant (Claude, ChatGPT...) s'enregistre
tout seul (RFC 7591), envoie l'abonné sur notre page de connexion (code à 6 chiffres reçu par e-mail),
puis échange le code contre des jetons (PKCE S256 obligatoire). Les jetons ne sont stockés qu'en empreinte."""

import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode, urlparse

import abonnement

SITE = abonnement.SITE
RESSOURCE = SITE + "/abonne/mcp"
DUREE_ACCES = 24 * 3600
DUREE_RAFRAICHISSEMENT = 90 * 24 * 3600
DUREE_DEMANDE = 15 * 60
DUREE_CODE_MAIL = 10 * 60
ESSAIS_MAX = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (
  client_id TEXT PRIMARY KEY, secret_hash TEXT, nom TEXT, redirect_uris TEXT NOT NULL,
  methode TEXT NOT NULL, cree_le TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_demandes (
  id TEXT PRIMARY KEY, client_id TEXT NOT NULL, redirect_uri TEXT NOT NULL, state TEXT, defi TEXT NOT NULL,
  ressource TEXT, email TEXT, code_mail TEXT, essais INTEGER NOT NULL DEFAULT 0, expire REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_codes (
  hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, redirect_uri TEXT NOT NULL, defi TEXT NOT NULL,
  abonnement TEXT NOT NULL, ressource TEXT, expire REAL NOT NULL, utilise INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS oauth_jetons (
  hash TEXT PRIMARY KEY, type TEXT NOT NULL, client_id TEXT NOT NULL, abonnement TEXT NOT NULL,
  expire REAL NOT NULL, cree_le TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS oauth_jetons_abo ON oauth_jetons (abonnement);
"""

_pret = {"v": False}


def db():
    c = abonnement.db()
    if not _pret["v"]:
        c.executescript(SCHEMA)
        _pret["v"] = True
    return c


def h(valeur):
    return hashlib.sha256(valeur.encode()).hexdigest()


def purger():
    c, t = db(), time.time()
    c.execute("DELETE FROM oauth_demandes WHERE expire < ?", (t,))
    c.execute("DELETE FROM oauth_codes WHERE expire < ?", (t - 3600,))
    c.execute("DELETE FROM oauth_jetons WHERE expire < ?", (t,))


# Métadonnées (RFC 9728 et RFC 8414).

def meta_ressource():
    return {"resource": RESSOURCE, "authorization_servers": [SITE], "bearer_methods_supported": ["header"],
            "resource_name": "Droit by Studjoow", "resource_documentation": SITE + "/"}


def meta_serveur():
    return {
        "issuer": SITE,
        "authorization_endpoint": SITE + "/oauth/authorize",
        "token_endpoint": SITE + "/oauth/token",
        "registration_endpoint": SITE + "/oauth/register",
        "revocation_endpoint": SITE + "/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
        "scopes_supported": ["droit"],
        "service_documentation": SITE + "/",
    }


def entete_401():
    return 'Bearer resource_metadata="%s/.well-known/oauth-protected-resource/abonne/mcp"' % SITE


# Enregistrement dynamique des clients (RFC 7591).

def _uri_valide(u):
    p = urlparse(u)
    if p.scheme == "https" and p.netloc:
        return True
    return p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1", "::1")


def enregistrer_client(donnees):
    uris = donnees.get("redirect_uris")
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) and _uri_valide(u) for u in uris):
        raise ValueError("redirect_uris invalides (https obligatoire, http seulement en local)")
    methode = donnees.get("token_endpoint_auth_method") or "client_secret_basic"
    if methode not in ("none", "client_secret_post", "client_secret_basic"):
        raise ValueError("token_endpoint_auth_method non pris en charge")
    client_id = "drt_" + secrets.token_urlsafe(18)
    secret = None if methode == "none" else secrets.token_urlsafe(32)
    nom = str(donnees.get("client_name") or "Assistant")[:80]
    db().execute("INSERT INTO oauth_clients (client_id, secret_hash, nom, redirect_uris, methode, cree_le) VALUES (?, ?, ?, ?, ?, ?)",
                 (client_id, h(secret) if secret else None, nom, json.dumps(uris), methode, abonnement.maintenant()))
    rep = {"client_id": client_id, "client_id_issued_at": int(time.time()), "client_name": nom, "redirect_uris": uris,
           "token_endpoint_auth_method": methode, "grant_types": ["authorization_code", "refresh_token"],
           "response_types": ["code"]}
    if secret:
        rep.update(client_secret=secret, client_secret_expires_at=0)
    return rep


def client(client_id):
    return db().execute("SELECT * FROM oauth_clients WHERE client_id=?", (client_id or "",)).fetchone()


# Autorisation : demande en attente, code par e-mail, code d'autorisation.

class ErreurOAuth(Exception):
    def __init__(self, code, description="", statut=400):
        super().__init__(description or code)
        self.code, self.description, self.statut = code, description, statut


def ouvrir_demande(p):
    cl = client(p.get("client_id"))
    if not cl:
        raise ErreurOAuth("invalid_client", "Assistant inconnu : supprimez puis rajoutez le connecteur.")
    uri = p.get("redirect_uri") or ""
    if uri not in json.loads(cl["redirect_uris"]):
        raise ErreurOAuth("invalid_request", "Adresse de retour non enregistrée pour cet assistant.")
    if p.get("response_type") != "code" or p.get("code_challenge_method") != "S256" or not p.get("code_challenge"):
        raise ErreurOAuth("invalid_request", "Demande incomplète (PKCE S256 obligatoire).")
    purger()
    demande = secrets.token_urlsafe(24)
    db().execute("INSERT INTO oauth_demandes (id, client_id, redirect_uri, state, defi, ressource, expire) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (demande, cl["client_id"], uri, p.get("state"), p["code_challenge"], p.get("resource"), time.time() + DUREE_DEMANDE))
    return demande, cl["nom"]


def demande(did):
    d = db().execute("SELECT * FROM oauth_demandes WHERE id=?", (did or "",)).fetchone()
    return d if d and d["expire"] > time.time() else None


def abonnement_par_email(email):
    rows = abonnement.db().execute(
        "SELECT * FROM cles WHERE lower(email)=lower(?) AND statut='actif' ORDER BY cree_le DESC", (email,)).fetchall()
    rows = sorted(rows, key=lambda r: 0 if abonnement.offre_de(r)["pro"] else 1)
    return rows[0] if rows else None


async def envoyer_code_mail(did, email):
    """Envoie un code à 6 chiffres si un abonnement actif correspond ; même réponse sinon."""
    d = demande(did)
    if not d:
        return False
    db().execute("UPDATE oauth_demandes SET email=?, code_mail=NULL, essais=0 WHERE id=?", (email, did))
    if not abonnement_par_email(email):
        return True
    code = "%06d" % secrets.randbelow(1000000)
    db().execute("UPDATE oauth_demandes SET code_mail=?, expire=? WHERE id=?",
                 (h(did + ":" + code), time.time() + DUREE_CODE_MAIL, did))
    await abonnement.envoyer_email(email, "Votre code de connexion : %s" % code, abonnement._gabarit(
        "Votre code de connexion.", [
            abonnement._p("Saisissez ce code sur la page de connexion ouverte par votre assistant :"),
            '<p style="margin:6px 0 20px;font-family:Menlo,Consolas,monospace;font-size:34px;letter-spacing:.3em;'
            'font-weight:bold;color:#1b0b16">%s</p>' % code,
            abonnement._p("Il est valable 10 minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
                          "personne ne peut se connecter sans ce code.", "font-size:13.5px;color:#7e8493;margin:0"),
        ], "Code valable 10 minutes."), "Votre code de connexion Droit by Studjoow : %s (valable 10 minutes)\n" % code)
    return True


def verifier_code_mail(did, code):
    d = demande(did)
    if not d or not d["code_mail"] or not d["email"]:
        return None
    if d["essais"] >= ESSAIS_MAX:
        return None
    db().execute("UPDATE oauth_demandes SET essais = essais + 1 WHERE id=?", (did,))
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if not hmac.compare_digest(d["code_mail"], h(did + ":" + code)):
        return None
    return abonnement_par_email(d["email"])


def accorder(did, row):
    """Termine la demande : renvoie l'adresse de retour de l'assistant avec le code d'autorisation."""
    d = demande(did)
    if not d or not row or row["statut"] != "actif":
        return None
    code = secrets.token_urlsafe(32)
    c = db()
    c.execute("INSERT INTO oauth_codes (hash, client_id, redirect_uri, defi, abonnement, ressource, expire) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (h(code), d["client_id"], d["redirect_uri"], d["defi"], row["abonnement"], d["ressource"], time.time() + 300))
    c.execute("DELETE FROM oauth_demandes WHERE id=?", (did,))
    params = {"code": code, "iss": SITE}
    if d["state"]:
        params["state"] = d["state"]
    return d["redirect_uri"] + ("&" if "?" in d["redirect_uri"] else "?") + urlencode(params)


def refuser(did):
    d = demande(did)
    if not d:
        return None
    db().execute("DELETE FROM oauth_demandes WHERE id=?", (did,))
    params = {"error": "access_denied", "iss": SITE}
    if d["state"]:
        params["state"] = d["state"]
    return d["redirect_uri"] + ("&" if "?" in d["redirect_uri"] else "?") + urlencode(params)


# Jetons.

def _authentifier_client(form, auth_basic):
    client_id, secret = form.get("client_id"), form.get("client_secret")
    if auth_basic:
        client_id, secret = auth_basic
    cl = client(client_id)
    if not cl:
        raise ErreurOAuth("invalid_client", "client inconnu", 401)
    if cl["methode"] != "none":
        if not secret or not cl["secret_hash"] or not hmac.compare_digest(cl["secret_hash"], h(secret)):
            raise ErreurOAuth("invalid_client", "secret invalide", 401)
    return cl


def _emettre(client_id, abo):
    acces, rafraichir = "dra_" + secrets.token_urlsafe(32), "drr_" + secrets.token_urlsafe(32)
    t, c = time.time(), db()
    c.execute("INSERT INTO oauth_jetons (hash, type, client_id, abonnement, expire, cree_le) VALUES (?, 'acces', ?, ?, ?, ?)",
              (h(acces), client_id, abo, t + DUREE_ACCES, abonnement.maintenant()))
    c.execute("INSERT INTO oauth_jetons (hash, type, client_id, abonnement, expire, cree_le) VALUES (?, 'rafraichir', ?, ?, ?, ?)",
              (h(rafraichir), client_id, abo, t + DUREE_RAFRAICHISSEMENT, abonnement.maintenant()))
    return {"access_token": acces, "token_type": "Bearer", "expires_in": DUREE_ACCES, "refresh_token": rafraichir,
            "scope": "droit"}


def echanger(form, auth_basic=None):
    cl = _authentifier_client(form, auth_basic)
    type_ = form.get("grant_type")
    c = db()
    if type_ == "authorization_code":
        code = form.get("code") or ""
        row = c.execute("SELECT * FROM oauth_codes WHERE hash=?", (h(code),)).fetchone()
        if not row or row["client_id"] != cl["client_id"] or row["expire"] < time.time():
            raise ErreurOAuth("invalid_grant", "code invalide ou expiré")
        if row["utilise"]:
            c.execute("DELETE FROM oauth_jetons WHERE abonnement=? AND client_id=?", (row["abonnement"], cl["client_id"]))
            raise ErreurOAuth("invalid_grant", "code déjà utilisé")
        if form.get("redirect_uri") and form.get("redirect_uri") != row["redirect_uri"]:
            raise ErreurOAuth("invalid_grant", "redirect_uri différente")
        verif = form.get("code_verifier") or ""
        import base64
        attendu = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).decode().rstrip("=")
        if not verif or not hmac.compare_digest(attendu, row["defi"]):
            c.execute("UPDATE oauth_codes SET utilise=1 WHERE hash=?", (row["hash"],))
            raise ErreurOAuth("invalid_grant", "PKCE invalide")
        c.execute("UPDATE oauth_codes SET utilise=1 WHERE hash=?", (row["hash"],))
        return _emettre(cl["client_id"], row["abonnement"])
    if type_ == "refresh_token":
        jeton = form.get("refresh_token") or ""
        row = c.execute("SELECT * FROM oauth_jetons WHERE hash=? AND type='rafraichir'", (h(jeton),)).fetchone()
        if not row or row["client_id"] != cl["client_id"] or row["expire"] < time.time():
            raise ErreurOAuth("invalid_grant", "jeton de rafraîchissement invalide")
        c.execute("DELETE FROM oauth_jetons WHERE hash=?", (row["hash"],))
        abo = abonnement.db().execute("SELECT statut FROM cles WHERE abonnement=?", (row["abonnement"],)).fetchone()
        if not abo or abo["statut"] == "revoque":
            raise ErreurOAuth("invalid_grant", "abonnement terminé")
        return _emettre(cl["client_id"], row["abonnement"])
    raise ErreurOAuth("unsupported_grant_type", "type non pris en charge")


def revoquer_jeton(jeton):
    db().execute("DELETE FROM oauth_jetons WHERE hash=?", (h(jeton or ""),))


def deconnecter_tout(abo):
    return db().execute("DELETE FROM oauth_jetons WHERE abonnement=?", (abo,)).rowcount


def abonne_par_jeton(entete):
    if not entete.startswith("Bearer "):
        return None
    hj = h(entete[7:].strip())
    row = db().execute("SELECT * FROM oauth_jetons WHERE hash=? AND type='acces'", (hj,)).fetchone()
    if not row or row["expire"] < time.time() or not hmac.compare_digest(row["hash"], hj):
        return None
    return abonnement.db().execute("SELECT * FROM cles WHERE abonnement=?", (row["abonnement"],)).fetchone()


def assistants_connectes(abo):
    return db().execute(
        "SELECT c.nom, count(*) AS n, max(j.cree_le) AS dernier FROM oauth_jetons j JOIN oauth_clients c ON c.client_id = j.client_id "
        "WHERE j.abonnement=? AND j.type='rafraichir' GROUP BY c.nom ORDER BY dernier DESC", (abo,)).fetchall()
