import html
import json
import os
import time

SITE = os.environ.get("DROIT_PUBLIC_URL", "https://droit.studjoow.com").rstrip("/")
REPO = "https://github.com/JohnJackHouzi/droit-francais-skill"
TITRE = "Droit français sourcé : serveur MCP gratuit pour Claude et ChatGPT"
DESCRIPTION = ("Ajoutez le droit français et européen officiel à Claude ou ChatGPT en 30 secondes : codes, lois, "
               "Journal officiel, conventions collectives, jurisprudence et EUR-Lex, chaque réponse sourcée "
               "avec son lien Légifrance ou EUR-Lex. Gratuit, sans inscription.")

FAQ = [
    ("Qu'est-ce que ce serveur ?",
     "Un serveur MCP (Model Context Protocol) public et gratuit qui donne à Claude, ChatGPT ou tout assistant "
     "compatible un accès en lecture aux données ouvertes officielles du droit français (DILA, Légifrance) et du "
     "droit de l'Union européenne (EUR-Lex). L'assistant cherche dans les textes avant de répondre et cite chaque "
     "source avec son identifiant et son lien."),
    ("Comment l'ajouter dans Claude ?",
     "Dans Claude, ouvrez Paramètres, puis Connecteurs, cliquez sur Ajouter un connecteur personnalisé, donnez-lui "
     "un nom et collez l'adresse %s/mcp. Aucune authentification n'est demandée." % SITE),
    ("Comment l'ajouter dans ChatGPT ?",
     "Dans ChatGPT, ouvrez Paramètres, puis Applications et connecteurs. Selon votre offre, activez le mode "
     "développeur dans les paramètres avancés, puis créez un connecteur avec l'adresse %s/mcp, sans "
     "authentification." % SITE),
    ("Quelles sources sont couvertes ?",
     "Les codes et lois consolidés avec toutes leurs versions datées (LEGI), le Journal officiel (JORF), les "
     "conventions collectives (KALI), la jurisprudence administrative (JADE), judiciaire (CASS, INCA, CAPP), "
     "constitutionnelle (CONSTIT) et de la CNIL, ainsi que les règlements, directives, traités et arrêts de la Cour "
     "de justice de l'Union européenne en français."),
    ("Les réponses sont-elles fiables ?",
     "Chaque référence peut être contrôlée par l'outil verifier_references avant d'être citée : une référence "
     "introuvable ou une citation absente du texte est signalée. Cela réduit fortement les inventions, sans "
     "remplacer la lecture du texte officiel sur Légifrance ou EUR-Lex. C'est de l'information juridique, pas un "
     "conseil : pour un cas concret, consultez un avocat."),
    ("Est-ce gratuit ?",
     "Oui, sans inscription ni publicité. Le service est fourni sans garantie de disponibilité, avec une limite de "
     "60 requêtes par minute et par adresse IP. Le code est libre (licence MIT) et chacun peut héberger son propre "
     "serveur."),
]

OUTILS = [
    ("lire_article", "Texte d'un article de code ou de loi à une date donnée"),
    ("rechercher_loi", "Recherche plein texte dans les codes, lois, Journal officiel et conventions collectives"),
    ("lire_texte", "Fiche et plan d'un texte, d'un code ou d'une convention collective (IDCC)"),
    ("lister_codes", "Liste des codes en vigueur"),
    ("rechercher_jurisprudence", "Décisions du Conseil d'État, de la Cour de cassation, des cours d'appel, du Conseil constitutionnel et de la CNIL"),
    ("lire_decision", "Texte intégral d'une décision"),
    ("verifier_references", "Contrôle qu'une référence existe et qu'une citation y figure mot pour mot"),
    ("lire_texte_ue", "Règlement, directive, traité ou arrêt de la CJUE, article par article"),
    ("rechercher_droit_ue", "Recherche plein texte dans le droit de l'Union européenne"),
    ("rechercher_jurisprudence_ue", "Recherche dans les arrêts de la Cour de justice et du Tribunal"),
    ("etat_base", "Date de mise à jour et volume de chaque base"),
]

ICONE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
         'fill="#1d3557"/><path d="M32 12v40M18 52h28M14 24h36M20 24l-8 16h16zM44 24l-8 16h16z" stroke="#f1c453" '
         'stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

_cache = {"t": 0.0, "v": None}


def _date(stamp):
    if not stamp or len(stamp) < 8:
        return None
    return "%s/%s/%s" % (stamp[6:8], stamp[4:6], stamp[:4])


def resume(etat_fn):
    if _cache["v"] is not None and time.monotonic() - _cache["t"] < 3600:
        return _cache["v"]
    try:
        e = etat_fn(comptes=True)
    except Exception:
        e = {"pret": False, "bases": {}}
    b = e.get("bases", {})
    legi, juri, eu = b.get("legi.sqlite", {}), b.get("juri.sqlite", {}), b.get("eu.sqlite", {})
    stamps = [v for k, v in (legi.get("meta") or {}).items() if k.startswith("last_increment_")]
    stamps += [v for k, v in (juri.get("meta") or {}).items() if k.startswith("incremental_")]
    r = {
        "pret": e.get("pret", False),
        "maj": _date(max(stamps)) if stamps else None,
        "articles": sum((legi.get("comptes") or {}).values()),
        "decisions": sum((juri.get("comptes") or {}).values()),
        "ue": sum((eu.get("comptes") or {}).values()),
    }
    _cache.update(t=time.monotonic(), v=r)
    return r


def nombre(n):
    return "{:,}".format(n).replace(",", " ")


def json_ld():
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": "Droit français sourcé",
         "inLanguage": "fr-FR", "description": DESCRIPTION},
        {"@type": "SoftwareApplication", "@id": SITE + "/#app", "name": "Serveur MCP Droit français",
         "applicationCategory": "DeveloperApplication", "operatingSystem": "Tous (service web)",
         "url": SITE + "/", "installUrl": SITE + "/mcp", "softwareHelp": REPO, "codeRepository": REPO,
         "license": "https://opensource.org/licenses/MIT", "inLanguage": "fr-FR", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
         "description": DESCRIPTION,
         "featureList": [o[1] for o in OUTILS]},
        {"@type": "Dataset", "name": "Droit français et européen (données ouvertes DILA et EUR-Lex)",
         "description": "Bases LEGI, JORF, KALI, JADE, CASS, CAPP, INCA, CONSTIT, CNIL et EUR-Lex interrogeables en plein texte.",
         "license": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
         "isBasedOn": ["https://echanges.dila.gouv.fr/OPENDATA/", "https://eur-lex.europa.eu/"],
         "inLanguage": "fr-FR", "creator": {"@type": "Organization", "name": "DILA", "url": "https://www.dila.premier-ministre.gouv.fr/"}},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
        {"@type": "HowTo", "name": "Ajouter le droit français à Claude", "totalTime": "PT1M", "step": [
            {"@type": "HowToStep", "position": 1, "text": "Ouvrir Paramètres puis Connecteurs dans Claude."},
            {"@type": "HowToStep", "position": 2, "text": "Cliquer sur Ajouter un connecteur personnalisé."},
            {"@type": "HowToStep", "position": 3, "text": "Coller l'adresse %s/mcp et valider, sans authentification." % SITE},
        ]},
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


CSS = """
:root{--bg:#fbfaf7;--fg:#1b1f24;--muted:#5b6470;--card:#fff;--line:#e4e1da;--accent:#1d3557;--gold:#b8860b;--ok:#2e7d32;--warn:#b26a00}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--fg:#e9ecef;--muted:#a3acb7;--card:#181c21;--line:#2a3038;--accent:#9cc3ff;--gold:#f1c453;--ok:#7bd389;--warn:#ffc870}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 16px 64px}
h1{font-size:clamp(28px,5vw,40px);line-height:1.15;margin:0 0 12px;letter-spacing:-.01em}
h2{font-size:22px;margin:44px 0 12px}h3{font-size:18px;margin:20px 0 6px}
p{margin:0 0 12px}.lead{font-size:19px;color:var(--muted)}
a{color:var(--accent)}code{font:15px ui-monospace,SFMono-Regular,Menlo,monospace}
.url{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:20px 0}
.url code{font-size:17px;word-break:break-all;flex:1;min-width:200px}
button{font:inherit;font-size:15px;border:0;border-radius:8px;padding:8px 14px;background:var(--accent);color:var(--bg);cursor:pointer}
.etat{display:inline-flex;align-items:center;gap:8px;font-size:15px;color:var(--muted)}
.pt{width:10px;height:10px;border-radius:50%;background:var(--warn)}.pt.ok{background:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card h3{margin-top:0}ol{padding-left:22px}li{margin:4px 0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.stat b{display:block;font-size:24px}.stat span{font-size:14px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:15px}td{padding:8px 6px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{white-space:nowrap}
details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-weight:600}
.note{border-left:4px solid var(--gold);padding:8px 14px;background:var(--card);border-radius:0 8px 8px 0}
footer{margin-top:48px;font-size:14px;color:var(--muted)}
@media (max-width:480px){.url code{font-size:14px;min-width:0}}
"""


def render(etat_fn):
    r = resume(etat_fn)
    e = html.escape
    etat = ("<span class=\"pt ok\"></span>En service%s" % (", bases à jour du %s" % r["maj"] if r["maj"] else "")
            if r["pret"] else "<span class=\"pt\"></span>Bases en cours de chargement, réessayer plus tard")
    stats = ""
    if r["pret"]:
        items = [(r["articles"], "articles de codes, lois, JO et conventions"), (r["decisions"], "décisions de justice")]
        if r["ue"]:
            items.append((r["ue"], "textes et arrêts de l'UE"))
        stats = "<div class=\"stats\">%s</div>" % "".join(
            "<div class=\"card stat\"><b>%s</b><span>%s</span></div>" % (nombre(n), lab) for n, lab in items)
    outils = "".join("<tr><td><code>%s</code></td><td>%s</td></tr>" % (e(n), e(d)) for n, d in OUTILS)
    faq = "".join("<details><summary>%s</summary><p>%s</p></details>" % (e(q), e(a)) for q, a in FAQ)
    return """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(titre)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(site)s/">
<meta name="robots" content="index,follow,max-snippet:-1">
<meta name="theme-color" content="#1d3557">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="text/plain" href="/llms.txt" title="llms.txt">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Droit français sourcé">
<meta property="og:title" content="%(titre)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(site)s/">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">%(ld)s</script>
<style>%(css)s</style>
</head>
<body>
<main>
<header>
<p class="etat">%(etat)s</p>
<h1>Le droit français officiel, sourcé, dans Claude et ChatGPT</h1>
<p class="lead">Un serveur MCP gratuit qui fait chercher votre assistant dans les codes, les lois, le Journal officiel, les conventions collectives, la jurisprudence et le droit européen avant de répondre. Chaque affirmation est suivie de sa source : article, identifiant Légifrance ou CELEX, lien et date de version.</p>
</header>

<div class="url"><code id="u">%(site)s/mcp</code><button type="button" onclick="navigator.clipboard.writeText(document.getElementById('u').textContent).then(()=>{this.textContent='Copié'})">Copier l'adresse</button></div>
%(stats)s

<h2 id="installer">Ajouter le serveur en 30 secondes</h2>
<div class="grid">
<section class="card"><h3>Dans Claude</h3><ol><li>Ouvrir <b>Paramètres</b>, puis <b>Connecteurs</b>.</li><li>Cliquer sur <b>Ajouter un connecteur personnalisé</b>.</li><li>Nom : <i>Droit français</i>. URL : <code>%(site)s/mcp</code>. Pas d'authentification.</li><li>Dans une conversation, activer le connecteur et demander : « Que dit l'article 1240 du Code civil ? »</li></ol></section>
<section class="card"><h3>Dans ChatGPT</h3><ol><li>Ouvrir <b>Paramètres</b>, puis <b>Applications et connecteurs</b>.</li><li>Selon l'offre, activer le <b>mode développeur</b> dans les paramètres avancés.</li><li><b>Créer</b> un connecteur avec l'URL <code>%(site)s/mcp</code>, authentification <b>aucune</b>.</li><li>Le choisir dans le menu des outils d'une conversation.</li></ol></section>
</div>

<h2 id="sources">Ce que contient la base</h2>
<div class="grid">
<section class="card"><h3>Législation</h3><p>Codes, lois, décrets et arrêtés consolidés avec toutes leurs versions datées (LEGI), Journal officiel tel que publié (JORF), conventions collectives par IDCC (KALI).</p></section>
<section class="card"><h3>Jurisprudence</h3><p>Conseil d'État et juridictions administratives (JADE), Cour de cassation (CASS, INCA), cours d'appel (CAPP), Conseil constitutionnel, délibérations de la CNIL.</p></section>
<section class="card"><h3>Droit de l'Union</h3><p>Règlements et directives en vigueur dans leur dernière version consolidée (RGPD, règlement sur l'IA, DSA, DMA...), traités, Charte des droits fondamentaux, arrêts de la Cour de justice et du Tribunal, en français.</p></section>
</div>

<h2 id="methode">Une méthode qui réduit les erreurs</h2>
<p>Le serveur impose un protocole à l'assistant : chercher avant de répondre, croiser la loi et la jurisprudence, prendre la version du texte en vigueur à la date des faits, vérifier chaque référence avec <code>verifier_references</code> (une référence introuvable ou une citation absente est signalée), citer la source après chaque affirmation et terminer par un bloc « Sources ». Quand la base ne contient pas la réponse, l'assistant doit le dire.</p>

<h2 id="outils">Les 11 outils</h2>
<table>%(outils)s</table>

<h2 id="limites">Limites</h2>
<div class="note"><p><b>Information juridique, pas conseil.</b> La version qui fait foi est celle publiée sur <a href="https://www.legifrance.gouv.fr">Légifrance</a> ou <a href="https://eur-lex.europa.eu">EUR-Lex</a>. Pour un cas concret, consultez un avocat.</p></div>
<p>Service gratuit fourni sans garantie de disponibilité ni d'exactitude, limité à 60 requêtes par minute et par adresse IP. Jurisprudence non exhaustive : seules les décisions diffusées en open data y figurent ; les arrêts des cours d'appel s'arrêtent fin 2023 ; certaines délibérations de la CNIL et certains arrêts du Tribunal de l'UE n'existent pas en texte français. Les versions consolidées du droit de l'UE n'ont pas de valeur officielle.</p>

<h2 id="faq">Questions fréquentes</h2>
%(faq)s

<footer>
<p>Données : DILA, Légifrance open data, sous <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/">Licence Ouverte 2.0</a> ; EUR-Lex, Office des publications de l'Union européenne. Ce service n'est ni édité ni approuvé par la DILA, Légifrance ou l'Union européenne.</p>
<p>Code libre (licence MIT) : <a href="%(repo)s">%(repo_court)s</a>. État technique : <a href="/health">/health</a>.</p>
</footer>
</main>
</body>
</html>""" % {"titre": e(TITRE), "desc": e(DESCRIPTION), "site": SITE, "ld": json_ld().replace("</", "<\\/"),
             "css": CSS, "etat": etat, "stats": stats, "outils": outils, "faq": faq, "repo": REPO,
             "repo_court": "github.com/JohnJackHouzi/droit-francais-skill"}


def robots():
    return "User-agent: *\nAllow: /\nDisallow: /mcp\n\nSitemap: %s/sitemap.xml\n" % SITE


def sitemap():
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>%s/</loc><changefreq>daily</changefreq></url>"
            "<url><loc>%s/llms.txt</loc><changefreq>weekly</changefreq></url></urlset>\n" % (SITE, SITE))


def llms(etat_fn):
    r = resume(etat_fn)
    lignes = [
        "# Droit français sourcé (serveur MCP)",
        "",
        "> " + DESCRIPTION,
        "",
        "Adresse du serveur MCP (Streamable HTTP, sans authentification) : %s/mcp" % SITE,
        "Mise à jour des bases : %s" % (r["maj"] or "voir %s/health" % SITE),
        "",
        "## Sources",
        "- Légifrance open data (DILA) : LEGI, JORF, KALI, JADE, CASS, CAPP, INCA, CONSTIT, CNIL, Licence Ouverte 2.0",
        "- EUR-Lex via l'API Cellar de l'Office des publications de l'UE : règlements, directives, traités, arrêts de la CJUE",
        "",
        "## Outils",
    ] + ["- %s : %s" % o for o in OUTILS] + [
        "",
        "## Protocole de citation",
        "Chercher avant de répondre ; croiser loi et jurisprudence ; version du texte à la date des faits ; vérifier chaque "
        "référence avec verifier_references ; citer la source après chaque affirmation (ex. Code civil, art. 1240 ; "
        "Cass. soc., 12 juillet 2023, n° 21-21.185 ; RGPD, art. 17 ; CJUE, C-131/12) ; terminer par un bloc Sources "
        "avec identifiant Légifrance ou CELEX et lien. Information juridique, pas conseil.",
        "",
        "## Questions fréquentes",
    ] + ["- %s %s" % (q, a) for q, a in FAQ] + [
        "",
        "## Liens",
        "- Code source : %s" % REPO,
        "- État des bases : %s/health" % SITE,
        "",
    ]
    return "\n".join(lignes)
