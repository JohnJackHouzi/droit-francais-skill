import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
TIMEOUT = float(os.environ.get("DROIT_TIMEOUT", "40"))
MAX_CHARS = int(os.environ.get("DROIT_MAX_CHARS", "40000"))
RATE = int(os.environ.get("DROIT_RATE_PER_MIN", "60"))
CONCURRENT = asyncio.Semaphore(int(os.environ.get("DROIT_CONCURRENCY", "2")))

INSTRUCTIONS = """Droit français officiel (Légifrance open data, DILA) : codes, lois, décrets, JORF, conventions collectives, jurisprudence (Conseil d'État, Cour de cassation, cours d'appel, Conseil constitutionnel, CNIL). Droit de l'Union européenne en français (EUR-Lex, Office des publications) : règlements, directives, traités, Charte, arrêts de la CJUE.

PROTOCOLE OBLIGATOIRE
1. Ne jamais répondre sur le droit français de mémoire : chercher d'abord avec ces outils.
2. Pour une question de fond, croiser la loi applicable ET la jurisprudence. Lire le texte intégral (lire_article, lire_decision), pas seulement les extraits.
3. Utiliser le paramètre date pour la date des faits : un article change dans le temps. Signaler quand la version en vigueur aujourd'hui diffère.
4. Avant de citer une référence, la contrôler avec verifier_references. Une référence INTROUVABLE ou une citation ABSENTE ne doit pas être citée. Les citations entre guillemets sont copiées du texte lu, jamais reconstituées.
5. Chaque affirmation de droit est suivie de sa source : (Code du travail, art. L1237-1), (Cass. soc., 12 juillet 2023, n° 21-21.185), (RGPD, art. 17) ou (CJUE, 13 mai 2014, Google Spain, C-131/12).
6. Terminer par un bloc « Sources » : une ligne par référence avec identifiant Légifrance ou CELEX et lien, repris des résultats. Pour l'UE, le lien est https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:<id> et la version consolidée utilisée est indiquée.
7. Si la base ne contient pas la réponse, le dire. Séparer ce que dit le texte (cité) de l'interprétation (signalée comme telle).
8. Information juridique, pas conseil : renvoyer vers Légifrance pour la version faisant foi et vers un avocat pour un cas concret.
9. Pour savoir si un projet est conforme, appeler d'abord analyser_conformite, puis lire chaque texte listé.
10. Pour une question touchant au droit de l'UE (données personnelles, IA, plateformes, consommation, droit d'auteur), croiser le texte européen, sa transposition ou son application en droit français et la jurisprudence (CJUE et juridictions françaises).
Limites : base figée à la dernière mise à jour DILA (voir etat_base) ; droit de l'UE limité au périmètre chargé (voir etat_base) et versions consolidées sans valeur officielle ; cours d'appel jusqu'à fin 2023 ; certaines délibérations CNIL sans texte ; jurisprudence non exhaustive (seules les décisions diffusées par la DILA)."""

_hosts = [h for h in os.environ.get("DROIT_ALLOWED_HOSTS", "").split(",") if h]
security = (
    TransportSecuritySettings(allowed_hosts=_hosts, allowed_origins=["*"])
    if _hosts
    else TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

mcp = FastMCP(
    "droit-francais",
    instructions=INSTRUCTIONS,
    host=os.environ.get("HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8000")),
    stateless_http=True,
    json_response=True,
    transport_security=security,
)


async def run(script, *args):
    async with CONCURRENT:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", str(SCRIPTS / script), *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return "Délai dépassé : reformuler avec une requête plus précise (code, dates, juridiction)."
    text = out.decode("utf-8", "replace")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[... tronqué : affiner la recherche ou lire l'élément par son identifiant ...]"
    return text


def opts(**kw):
    out = []
    for k, v in kw.items():
        if v not in (None, "", False):
            out.append(f"--{k.replace('_', '-')}")
            if v is not True:
                out.append(str(v))
    return out


@mcp.tool()
async def lire_article(code: str, numero: str, date: str = "") -> str:
    """Texte d'un article de code ou de loi, tel qu'en vigueur à une date. code : « Code civil », « Code du travail »... ; numero : « 1240 », « L1221-1 » ; date : AAAA-MM-JJ (défaut aujourd'hui)."""
    return await run("search_legi.py", "article", code, numero, *opts(date=date))


@mcp.tool()
async def rechercher_loi(requete: str, code: str = "", base: str = "legi", date: str = "", limite: int = 10) -> str:
    """Recherche plein texte dans les articles. base : legi (codes, lois, décrets consolidés, défaut), kali (conventions collectives), jorf (Journal officiel tel que publié) ou tout. Syntaxe : "phrase exacte", AND, OR, NOT, prefixe*. code : restreindre à un code, un texte ou « IDCC 1486 ». date : AAAA-MM-JJ, version en vigueur à cette date (défaut aujourd'hui)."""
    base = base if base in ("legi", "kali", "jorf", "tout") else "legi"
    return await run("search_legi.py", "recherche", *opts(q=requete, code=code, base=base, date=date,
                                                          limit=min(max(limite, 1), 30)))


@mcp.tool()
async def lire_texte(identifiant_ou_nom: str) -> str:
    """Fiche et plan d'un texte : identifiant LEGITEXT/JORFTEXT, NOR, numéro IDCC d'une convention collective, ou nom (« Code de la consommation »)."""
    return await run("search_legi.py", "texte", identifiant_ou_nom)


@mcp.tool()
async def lister_codes() -> str:
    """Liste des codes disponibles."""
    return await run("search_legi.py", "codes")


@mcp.tool()
async def rechercher_jurisprudence(
    requete: str = "", base: str = "", juridiction: str = "", formation: str = "",
    numero: str = "", ecli: str = "", du: str = "", au: str = "",
    publiees_seulement: bool = False, tri: str = "pertinence", limite: int = 10,
) -> str:
    """Recherche de décisions. base : jade (juridictions administratives), cass (Cour de cassation), capp (cours d'appel), inca (Cassation inédits), constit (Conseil constitutionnel), cnil. numero : pourvoi ou requête (21-21.185). du/au : AAAA-MM-JJ. tri : pertinence ou date."""
    return await run(
        "search_juri.py",
        *opts(q=requete, base=base, juridiction=juridiction, formation=formation, numero=numero,
              ecli=ecli, du=du, au=au, publie=publiees_seulement,
              tri=tri if tri in ("pertinence", "date") else "pertinence",
              limit=min(max(limite, 1), 30)),
    )


@mcp.tool()
async def lire_decision(identifiant: str, max_caracteres: int = 20000) -> str:
    """Texte intégral d'une décision à partir de son identifiant (JURITEXT..., CONSTEXT..., CNILTEXT...)."""
    return await run("search_juri.py", "decision", identifiant, *opts(max_chars=min(max_caracteres, 40000)))


@mcp.tool()
async def verifier_references(references: list[str], date: str = "", citations: list[str] | None = None) -> str:
    """Contrôle que chaque référence existe avant de la citer. references : « Code civil 1240 », « LEGIARTI000032041571 », « 21-21.185 », « ECLI:FR:... », « RGPD art. 17 », « règlement (UE) 2024/1689, article 50 », « C-131/12 ». citations : extraits censés figurer mot pour mot dans la référence de même rang. Toute ligne INTROUVABLE ou citation ABSENTE interdit la citation."""
    args = list(references)
    for c in citations or []:
        args += ["--quote", c]
    return await run("verify.py", *args, *opts(date=date))


@mcp.tool()
async def lire_texte_ue(reference: str, article: str = "", max_caracteres: int = 20000) -> str:
    """Droit de l'UE : fiche, plan ou article d'un acte, ou texte d'un arrêt. reference : CELEX (32016R0679), alias (RGPD, DSA, DMA, RIA, TFUE, Charte), « règlement (UE) 2016/679 », « directive 93/13/CEE », numéro d'affaire (C-131/12) ou ECLI. article : « 17 », « premier », « Annexe III »."""
    return await run("search_eu.py", "texte", reference, *opts(article=article, max_chars=min(max(max_caracteres, 500), 40000)))


@mcp.tool()
async def rechercher_droit_ue(requete: str, acte: str = "", limite: int = 10) -> str:
    """Recherche plein texte dans les règlements, directives, traités et la Charte (en français). acte : restreindre à un acte (RGPD, 32022R2065...). Syntaxe : "phrase exacte", AND, OR, NOT, prefixe*."""
    return await run("search_eu.py", "recherche", *opts(q=requete, type="actes", celex=acte, limit=min(max(limite, 1), 30)))


@mcp.tool()
async def rechercher_jurisprudence_ue(requete: str, du: str = "", au: str = "", tri: str = "pertinence", limite: int = 10) -> str:
    """Recherche plein texte dans les arrêts de la Cour de justice de l'UE et du Tribunal (en français). du/au : AAAA-MM-JJ. tri : pertinence ou date. Lire ensuite l'arrêt avec lire_texte_ue (numéro d'affaire ou CELEX)."""
    return await run("search_eu.py", "recherche", *opts(q=requete, type="jurisprudence", du=du, au=au,
                                                        tri=tri if tri in ("pertinence", "date") else "pertinence",
                                                        limit=min(max(limite, 1), 30)))


@mcp.tool()
async def analyser_conformite(description: str, domaines: str = "") -> str:
    """Pré-analyse de conformité d'un projet en France et dans l'UE (RGPD, cookies, vente en ligne, abonnements, IA, DSA, droit d'auteur, mentions légales...). description : le projet en quelques phrases (activité, public, données collectées, paiement, prestataires, usage de l'IA). domaines : clés à forcer, séparées par des virgules. Renvoie les obligations probables, la question à vérifier pour chacune et l'outil pour lire le texte. Lire ensuite chaque texte avant de conclure : information juridique, pas certification."""
    return conformite.analyser(description[:8000], domaines)


@mcp.tool()
async def etat_base() -> str:
    """Comptes, date des dumps et du dernier incrémental DILA appliqué pour chaque base : à citer pour indiquer l'actualité des données."""
    return await run("etat.py")


sys.path.insert(0, str(SCRIPTS))
import etat as etat_bases  # noqa: E402
import abonnement  # noqa: E402
import conformite  # noqa: E402
import analyse_ia  # noqa: E402

PROXIES = int(os.environ.get("DROIT_TRUSTED_PROXIES", "1"))
PUBLIC_PATHS = ("/health", "/ping", "/", "/robots.txt", "/sitemap.xml", "/llms.txt", "/favicon.svg", "/og.png")
MAX_CORPS = 1_000_000
_pret = {"t": 0.0, "v": False}


def bases_pretes():
    if time.monotonic() - _pret["t"] > 30:
        _pret["v"] = etat_bases.etat(comptes=False)["pret"]
        _pret["t"] = time.monotonic()
    return _pret["v"]


def client_ip(scope):
    xff = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode()
    hops = [h.strip() for h in xff.split(",") if h.strip()]
    if PROXIES and len(hops) >= PROXIES:
        return hops[-PROXIES]
    return (scope.get("client") or ("?",))[0]


async def texte(send, status, body, retry=None):
    headers = [(b"content-type", b"text/plain; charset=utf-8")]
    if retry:
        headers.append((b"retry-after", retry))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body.encode()})


async def json_brut(send, body):
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})


async def lire_corps(receive):
    morceaux, total = [], 0
    while True:
        msg = await receive()
        if msg["type"] != "http.request":
            return None
        morceaux.append(msg.get("body", b""))
        total += len(morceaux[-1])
        if total > MAX_CORPS:
            return None
        if not msg.get("more_body"):
            return b"".join(morceaux)


def rejouer(corps, receive):
    envoye = {"v": False}

    async def recv():
        if not envoye["v"]:
            envoye["v"] = True
            return {"type": "http.request", "body": corps, "more_body": False}
        return await receive()
    return recv


def appels_outils(corps):
    try:
        msgs = json.loads(corps)
    except ValueError:
        return []
    msgs = msgs if isinstance(msgs, list) else [msgs]
    return [m.get("id") for m in msgs if isinstance(m, dict) and m.get("method") == "tools/call"]


def message_essai():
    return ("Quota de l'essai gratuit atteint : %d requêtes par jour sur l'adresse publique. "
            "Pour continuer, abonnement à %s € par mois (%d requêtes par jour), sans engagement : %s/abonnement . "
            "L'essai repart demain (minuit UTC). Indiquer ce lien à l'utilisateur."
            % (abonnement.ESSAI_PAR_JOUR, abonnement.PRIX, abonnement.PLAFOND_ABONNE, abonnement.SITE))


def message_plafond(plafond):
    return ("Plafond quotidien de l'abonnement atteint : %d requêtes par jour et par adresse personnelle (voir les "
            "CGV). Il repart demain (minuit UTC). Si l'adresse a pu être partagée, la régénérer sur %s/compte ."
            % (plafond, abonnement.SITE))


MESSAGES_STATUT = {
    "suspendu": "Abonnement suspendu : le dernier paiement a échoué. Mettre à jour le moyen de paiement sur %s/compte .",
    "revoque": "Abonnement terminé : cette adresse personnelle n'est plus active. Se réabonner sur %s/abonnement .",
}


class Garde:
    def __init__(self, app):
        self.app = app
        self.hits = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS or scope["path"].startswith("/static/"):
            return await self.app(scope, receive, send)
        abonne = None
        if scope["path"].startswith("/mcp/") and scope["path"].strip("/") != "mcp":
            abonne = abonnement.verifier_cle(scope["path"][5:].strip("/"))
            scope["path"], scope["raw_path"] = "/mcp", b"/mcp"
            if abonne is None:
                return await texte(send, 404, "Adresse personnelle inconnue. Vérifier l'adresse copiée ou la régénérer sur %s/compte ." % abonnement.SITE)
        ip = client_ip(scope)
        now, q = time.monotonic(), self.hits["k:" + abonne["abonnement"] if abonne else ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE:
            return await texte(send, 429, "Trop de requêtes, réessayer dans quelques secondes.", b"30")
        q.append(now)
        if len(self.hits) > 50000:
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                del self.hits[k]
        if scope["path"] == "/mcp" or scope["path"].startswith("/mcp/"):
            if not bases_pretes():
                return await texte(send, 503, "Bases en cours d'installation ou de reconstruction, réessayer plus tard.", b"600")
            limiter = abonne is not None or abonnement.actif()
            if limiter and scope["method"] == "POST":
                corps = await lire_corps(receive)
                if corps is None:
                    return await texte(send, 413, "Requête trop volumineuse.")
                ids = appels_outils(corps)
                if ids and abonne is not None and abonne["statut"] != "actif":
                    return await json_brut(send, abonnement.json_rpc_erreur(ids, MESSAGES_STATUT[abonne["statut"]] % abonnement.SITE))
                if ids and abonne is not None:
                    ok, _ = await asyncio.get_running_loop().run_in_executor(
                        None, abonnement.consommer_abonne, abonne["abonnement"], len(ids), abonnement.offre_de(abonne)["plafond"])
                    if not ok:
                        return await json_brut(send, abonnement.json_rpc_erreur(ids, message_plafond(abonnement.offre_de(abonne)["plafond"])))
                elif ids:
                    ok, _ = await asyncio.get_running_loop().run_in_executor(None, abonnement.consommer_essai, ip, len(ids))
                    if not ok:
                        return await json_brut(send, abonnement.json_rpc_erreur(ids, message_essai()))
                receive = rejouer(corps, receive)
        await self.app(scope, receive, send)


def build_app():
    import json
    from starlette.responses import PlainTextResponse, Response
    from starlette.routing import Route

    def health(request):
        e = etat_bases.etat(comptes=False)
        _pret.update(t=time.monotonic(), v=e["pret"])
        return Response(json.dumps(e, ensure_ascii=False), status_code=200 if e["pret"] else 503,
                        media_type="application/json")

    import page
    from starlette.responses import HTMLResponse

    if abonnement.actif():
        page.LIEN_ABONNEMENT = "/abonnement"

    cache = {"Cache-Control": "public, max-age=600"}

    async def accueil(request):
        body = await asyncio.get_running_loop().run_in_executor(None, page.render, etat_bases.etat)
        return HTMLResponse(body, headers=cache)

    async def llms(request):
        body = await asyncio.get_running_loop().run_in_executor(None, page.llms, etat_bases.etat)
        return PlainTextResponse(body, headers=cache)

    app = mcp.streamable_http_app()
    app.router.routes.insert(0, Route("/health", health))
    app.router.routes.insert(0, Route("/ping", lambda r: PlainTextResponse("ok")))
    app.router.routes.insert(0, Route("/", accueil))
    app.router.routes.insert(0, Route("/llms.txt", llms))
    app.router.routes.insert(0, Route("/robots.txt", lambda r: PlainTextResponse(page.robots(), headers=cache)))
    app.router.routes.insert(0, Route("/sitemap.xml", lambda r: Response(page.sitemap(), media_type="application/xml", headers=cache)))
    og = Path(__file__).resolve().parent / "og.png"
    if not og.exists():
        og = Path(__file__).resolve().parent.parent / "docs" / "apercu-social.png"
    og_bytes = og.read_bytes() if og.exists() else b""
    app.router.routes.insert(0, Route("/og.png", lambda r: Response(og_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})))
    import mimetypes
    from starlette.routing import Mount

    mimetypes.add_type("font/woff2", ".woff2")
    from starlette.staticfiles import StaticFiles

    class StaticCache(StaticFiles):
        async def get_response(self, path, scope):
            resp = await super().get_response(path, scope)
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp

    app.router.routes.insert(0, Mount("/static", app=StaticCache(directory=str(Path(__file__).resolve().parent / "static")), name="static"))
    app.router.routes.insert(0, Route("/favicon.svg", lambda r: Response(page.ICONE, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})))
    for chemin, fn in (("/cgv", page.cgv), ("/mentions-legales", page.mentions), ("/confidentialite", page.confidentialite)):
        app.router.routes.insert(0, Route(chemin, lambda r, fn=fn: HTMLResponse(fn(), headers=cache)))
    for route in routes_abonnement(page):
        app.router.routes.insert(0, route)
    return Garde(app)


def routes_abonnement(page):
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
    from starlette.routing import Route

    prive = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"}
    liens_envoyes = defaultdict(deque)

    def vue(contenu, status=200):
        return HTMLResponse(contenu, status_code=status, headers=prive)

    def ferme():
        return vue(page.page_ferme(), 503)

    async def formulaire(request):
        if not abonnement.actif():
            return ferme()
        offre = request.query_params.get("offre", "particulier")
        offre = offre if offre in abonnement.OFFRES else "particulier"
        if request.method == "GET":
            return vue(page.page_abonnement(offre=offre))
        f = await request.form()
        offre = f.get("offre") if f.get("offre") in abonnement.OFFRES else offre
        if f.get("cgv") != "1" or f.get("execution") != "1":
            return vue(page.page_abonnement("Cochez les deux cases pour continuer.", offre), 400)
        try:
            session = await abonnement.creer_session(abonnement.maintenant(), offre)
        except abonnement.ErreurStripe as exc:
            logging.getLogger("droit").error("Checkout : %s", exc)
            return vue(page.page_abonnement("Le paiement est momentanément indisponible, réessayez dans un instant.", offre), 502)
        return RedirectResponse(session["url"], status_code=303)

    async def merci(request):
        if not abonnement.actif():
            return ferme()
        sid = request.query_params.get("session_id", "")
        if not re.fullmatch(r"cs_(test|live)_[A-Za-z0-9]+", sid):
            return vue(page.page_merci(None, "Lien de confirmation invalide."), 400)
        try:
            s = await abonnement.stripe("GET", "/v1/checkout/sessions/" + sid, {"expand": ["subscription"]})
        except abonnement.ErreurStripe:
            return vue(page.page_merci(None, "Session de paiement introuvable."), 404)
        if (s.get("metadata") or {}).get("app") != abonnement.APP or s.get("status") != "complete" or not s.get("subscription"):
            return vue(page.page_merci(None, "Le paiement n'est pas finalisé."), 402)
        row = abonnement.enregistrer_abonnement(s["subscription"], (s.get("customer_details") or {}).get("email"))
        envoye = await abonnement.envoyer_cle_si_besoin(row["abonnement"])
        if abonnement.marquer_affichee(row["abonnement"]):
            return vue(page.page_merci(abonnement.adresse(abonnement.cle_de(row["abonnement"], row["version"])), None, row["email"], envoye or row["email_envoye"]))
        return vue(page.page_merci(None, "Votre adresse personnelle a déjà été affichée sur cette page. Retrouvez-la dans l'e-mail de confirmation, ou régénérez-la depuis votre compte."))

    def ligne_depuis(f):
        return abonnement.verifier_cle(abonnement.extraire_cle(f.get("adresse", "")))

    async def compte(request):
        if not abonnement.actif():
            return ferme()
        if request.method == "GET":
            return vue(page.page_compte())
        row = ligne_depuis(await request.form())
        if not row:
            return vue(page.page_compte(erreur="Adresse personnelle inconnue."), 404)
        return vue(page.page_gestion(row, abonnement.adresse(abonnement.cle_de(row["abonnement"], row["version"]))))

    async def acces(request):
        if not abonnement.actif():
            return ferme()
        aid = abonnement.lire_jeton(request.query_params.get("j", ""))
        row = aid and abonnement.db().execute("SELECT * FROM cles WHERE abonnement=?", (aid,)).fetchone()
        if not row:
            return vue(page.page_compte(erreur="Lien expiré ou invalide : demandez-en un nouveau."), 400)
        return vue(page.page_gestion(row, abonnement.adresse(abonnement.cle_de(row["abonnement"], row["version"]))))

    async def portail(request):
        if not abonnement.actif():
            return ferme()
        row = ligne_depuis(await request.form())
        if not row:
            return vue(page.page_compte(erreur="Adresse personnelle inconnue."), 404)
        try:
            p = await abonnement.creer_portail(row["client"])
        except abonnement.ErreurStripe as exc:
            logging.getLogger("droit").error("Portail : %s", exc)
            return vue(page.page_compte(erreur="Portail de gestion momentanément indisponible."), 502)
        return RedirectResponse(p["url"], status_code=303)

    async def regenerer(request):
        if not abonnement.actif():
            return ferme()
        row = ligne_depuis(await request.form())
        if not row:
            return vue(page.page_compte(erreur="Adresse personnelle inconnue."), 404)
        cle = abonnement.regenerer(row["abonnement"])
        row = abonnement.db().execute("SELECT * FROM cles WHERE abonnement=?", (row["abonnement"],)).fetchone()
        return vue(page.page_gestion(row, abonnement.adresse(cle), nouvelle=True))

    async def lien(request):
        if not abonnement.actif():
            return ferme()
        email = ((await request.form()).get("email") or "").strip()[:200]
        now, q = time.monotonic(), liens_envoyes[client_ip(request.scope)]
        while q and now - q[0] > 3600:
            q.popleft()
        if "@" in email and len(q) < 5:
            q.append(now)
            await abonnement.envoyer_lien_acces(email)
        return vue(page.page_compte(info="Si un abonnement correspond à cette adresse e-mail, un lien d'accès valable une heure vient d'y être envoyé."))

    async def webhook(request):
        corps = await request.body()
        if not abonnement.signature_valide(corps, request.headers.get("stripe-signature", "")):
            return JSONResponse({"erreur": "signature invalide"}, status_code=400)
        ev = json.loads(corps)
        try:
            compte_rendu = await abonnement.traiter_evenement(ev)
        except Exception as exc:
            logging.getLogger("droit").exception("Webhook %s", ev.get("type"))
            return JSONResponse({"erreur": str(exc)[:200]}, status_code=500)
        return JSONResponse({"ok": True, "resultat": compte_rendu})

    executer = {"analyser_conformite": analyser_conformite, "lire_article": lire_article, "lire_texte_ue": lire_texte_ue,
                "rechercher_loi": rechercher_loi, "verifier_references": verifier_references}

    async def conformite_page(request):
        if not (abonnement.actif() and analyse_ia.actif()):
            return vue(page.page_conformite(ferme=True), 503)
        if request.method == "GET":
            return vue(page.page_conformite())
        f = await request.form()
        description = (f.get("description") or "").strip()
        if f.get("avertissement") != "1" or len(description) < 80:
            return vue(page.page_conformite("Décrivez le projet en quelques phrases (80 caractères au moins) et cochez la case.", description), 400)
        row = ligne_depuis(f)
        if not row or row["statut"] != "actif":
            return vue(page.page_conformite("Adresse personnelle inconnue ou abonnement inactif.", description), 403)
        offre = "pro" if abonnement.offre_de(row)["pro"] else "particulier"
        ok, n = await asyncio.get_running_loop().run_in_executor(
            None, abonnement.consommer_ia, row["abonnement"], analyse_ia.QUOTAS[offre])
        if not ok:
            return vue(page.page_conformite("Quota mensuel atteint : %d analyses par mois avec votre offre." % analyse_ia.QUOTAS[offre], description), 429)
        job = analyse_ia.lancer(description[:6000], executer)
        return RedirectResponse("/conformite/rapport/" + job, status_code=303)

    async def conformite_rapport(request):
        if not analyse_ia.etat(request.path_params["job"]):
            return vue(page.page_conformite("Rapport introuvable ou expiré (conservé une heure)."), 404)
        return vue(page.page_rapport(request.path_params["job"]))

    async def conformite_etat(request):
        job = analyse_ia.etat(request.path_params["job"])
        if not job:
            return JSONResponse({"etat": "inconnu"}, status_code=404, headers=prive)
        rep = {"etat": job["etat"], "etape": job.get("etape", "")}
        if job["etat"] == "fini":
            rep["html"] = page.md_html(job["rapport"])
        elif job["etat"] == "erreur":
            rep["erreur"] = job.get("erreur", "")
        return JSONResponse(rep, headers=prive)

    def refus():
        return JSONResponse({"erreur": "non autorisé"}, status_code=401, headers=prive)

    async def admin_resume(request):
        if not abonnement.admin_autorise(request.headers.get("authorization", "")):
            return refus()
        data = await asyncio.get_running_loop().run_in_executor(None, abonnement.resume_admin)
        return JSONResponse(data, headers=prive)

    async def admin_regenerer(request):
        if not abonnement.admin_autorise(request.headers.get("authorization", "")):
            return refus()
        try:
            aid = (await request.json()).get("abonnement", "")
        except ValueError:
            aid = ""
        rep = await abonnement.regenerer_et_envoyer(aid) if aid else None
        if not rep:
            return JSONResponse({"erreur": "abonnement inconnu"}, status_code=404, headers=prive)
        return JSONResponse(rep, headers=prive)

    return [
        Route("/admin/api/resume", admin_resume),
        Route("/admin/api/regenerer", admin_regenerer, methods=["POST"]),
        Route("/abonnement", formulaire, methods=["GET", "POST"]),
        Route("/merci", merci),
        Route("/compte", compte, methods=["GET", "POST"]),
        Route("/compte/acces", acces),
        Route("/compte/portail", portail, methods=["POST"]),
        Route("/compte/regenerer", regenerer, methods=["POST"]),
        Route("/compte/lien", lien, methods=["POST"]),
        Route("/stripe/webhook", webhook, methods=["POST"]),
        Route("/conformite", conformite_page, methods=["GET", "POST"]),
        Route("/conformite/rapport/{job}", conformite_rapport),
        Route("/conformite/etat/{job}", conformite_etat),
    ]


class Masque(logging.Filter):
    """Retire des journaux d'accès les clés (/mcp/<clé>) et les paramètres d'URL."""

    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str):
            chemin = record.args[2].split("?", 1)
            p = re.sub(r"^/mcp/.+", "/mcp/***", chemin[0])
            record.args = record.args[:2] + (p + ("?***" if len(chemin) > 1 else ""),) + record.args[3:]
        return True


app = build_app()

if __name__ == "__main__":
    import uvicorn
    from copy import deepcopy

    from uvicorn.config import LOGGING_CONFIG

    journaux = deepcopy(LOGGING_CONFIG)
    journaux["filters"] = {"masque": {"()": Masque}}
    journaux["handlers"]["access"]["filters"] = ["masque"]
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
                proxy_headers=False, log_config=journaux)
