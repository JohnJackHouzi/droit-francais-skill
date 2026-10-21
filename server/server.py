import asyncio
import os
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
CONCURRENT = asyncio.Semaphore(int(os.environ.get("DROIT_CONCURRENCY", "6")))

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
9. Pour une question touchant au droit de l'UE (données personnelles, IA, plateformes, consommation, droit d'auteur), croiser le texte européen, sa transposition ou son application en droit français et la jurisprudence (CJUE et juridictions françaises).
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
async def etat_base() -> str:
    """Comptes, date des dumps et du dernier incrémental DILA appliqué pour chaque base : à citer pour indiquer l'actualité des données."""
    return await run("etat.py")


sys.path.insert(0, str(SCRIPTS))
import etat as etat_bases  # noqa: E402

PROXIES = int(os.environ.get("DROIT_TRUSTED_PROXIES", "1"))
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


class Garde:
    def __init__(self, app):
        self.app = app
        self.hits = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] not in ("/health", "/ping"):
            now, q = time.monotonic(), self.hits[client_ip(scope)]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= RATE:
                return await texte(send, 429, "Trop de requêtes, réessayer dans quelques secondes.", b"30")
            q.append(now)
            if len(self.hits) > 50000:
                for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                    del self.hits[k]
            if not bases_pretes():
                return await texte(send, 503, "Bases en cours d'installation ou de reconstruction, réessayer plus tard.", b"600")
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

    app = mcp.streamable_http_app()
    app.router.routes.insert(0, Route("/health", health))
    app.router.routes.insert(0, Route("/ping", lambda r: PlainTextResponse("ok")))
    return Garde(app)


app = build_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
                proxy_headers=False)
