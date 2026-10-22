import html
import json
import os
import time

SITE = os.environ.get("DROIT_PUBLIC_URL", "https://droit.studjoow.com").rstrip("/")
REPO = "https://github.com/JohnJackHouzi/droit-francais-skill"
STUDIO = {"@type": "Organization", "@id": "https://studjoow.com/#org", "name": "Studjoow", "url": "https://studjoow.com",
          "description": "Studio créatif et tech : sites sur mesure, branding, IA, SEO et GEO.", "logo": "https://studjoow.com/brand/logo-long-blanc.svg"}
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

LOGO_STUDJOOW = '<svg role="img" aria-label="Studjoow" class="logo-sj" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 421.36 103.17"><g><g><rect fill="#b1338a" x="411.66" y="68.85" width="9.7" height="9"/><g><path fill="#b1338a" d="M218.61,68.63c2.4-.8,5.2.6,6,3,.8,2.1,0,4.6-1.9,5.9-1.5,1-3.3,1-4.8.2-2-.9-2.9-3.3-2.6-5.4.3-1.7,1.5-3.2,3.2-3.7h.1Z"/><path fill="#b1338a" d="M222.01,44.73c2.4-.8,5.2.6,6,3,.8,2.1,0,4.6-1.9,5.9-1.5,1-3.3,1-4.8.2-2-.9-2.9-3.3-2.6-5.4.3-1.7,1.5-3.2,3.2-3.7h.1Z"/><path fill="currentColor" d="M331.71,33.33c-3.6-3.8-8.3-6.7-13.6-7.6-4.3-.9-8.6-.1-12.5,1.6-3.2,1.5-6.1,3.7-8.4,6.3-.8-1.1-1.9-2.1-3.2-2.6-1.3-.5-2.5-.2-3.8-.2-2.2-1.8-4.7-3.3-7.4-4.2-4.9-1.7-10.4-1.7-15.2.2-3.8,1.5-6.9,4.4-9,7.7-2.8,4.3-4.2,9.4-4.9,14.4-.9,7.8,2,15.7,7.4,21.5,3.6,3.8,8.3,6.7,13.6,7.7,4.3.8,8.6.1,12.5-1.6,4.5-2.1,8.2-5.5,10.9-9.5.2.3.4.6.7.9l1.6,2.1c2.2,2.9,5.1,5.3,8.5,6.7.4.2.8.3,1.2.4,4.9,1.7,10.4,1.7,15.2-.2,3.8-1.5,6.9-4.4,9-7.7,2.8-4.3,4.2-9.4,4.9-14.4.9-7.8-2-15.7-7.4-21.5h-.1ZM288.11,61.23c-2.3,2.7-5.5,4.8-9,5.7-2.6.7-5.4.4-7.6-1-2.2-1.4-3.9-3.3-5-5.7-2.4-4.9-2.2-10.4-.4-15.5.8-2.1,1.8-4.1,3.4-5.8,1.8-1.9,4.1-3.3,6.8-3.4,3.1-.3,5.4,1.3,7.8,2.9-.2.8-.7,1.5-.4,2.3.4,1.2,1.5,2.2,2.3,3.1,2.6,3,4.7,6.4,4.7,10.4.1,2.5-1,4.8-2.5,6.8h0l-.1.2ZM326.71,58.73c-.8,2.1-1.8,4.1-3.4,5.8-1.8,1.9-4.1,3.3-6.8,3.4-1.1,0-2.1,0-3-.3-2.8-.8-4.9-3.1-5.9-5.8l-.2-.7c-.4-1-.9-1.8-1.5-2.7-2.2-2.7-3.8-5.8-3.8-9.3-.1-2.5,1-4.8,2.5-6.8,2.3-2.7,5.5-4.8,9-5.7,2.6-.7,5.4-.4,7.6,1s4,3.3,5,5.7c2.4,4.9,2.2,10.4.4,15.5h0l.1-.1Z"/><path fill="currentColor" d="M227.91.33c3.8-1.2,8.2,1,9.4,4.8,1.2,3.3,0,7.2-2.9,9.2-2.3,1.5-5.1,1.6-7.6.3-3.1-1.4-4.6-5.2-4-8.4.5-2.7,2.4-5.1,5.1-5.9Z"/><path fill="currentColor" d="M377.21,29.33c-1.9,4.6-3.3,9.4-4.4,14.4-.9,4.2-1.9,10.3-3.8,14-4.4,8.9-7.8,11.2-11.5,1-2-4.8-3.2-12.4-3.8-17.8-.5-4.2-.6-13.1-4.7-14.4-1.3-.4-2.6.1-3.6,1.2-4,4.4-2.3,16.3-1.6,21.8v.2c2,10.6,5,20.7,14.3,26.3,11.5,6.6,17.6-1.9,21.3-13.6h0c2.2,6.4,5.5,10.2,11.2,13.6,11.3,6.5,16.2-1.6,20.1-13.1,1.7-4.3,2.8-9.9,3.9-15,1-5.8,3.3-14.5.7-19.1h0c-4.6-5.7-8.6,2.7-9.4,7.4-1.5,6.6-2.3,15.5-5.4,21.5-4.4,8.9-6.8,11.2-10.5,1-2-4.8-3.2-12.4-3.8-17.8-.5-4.2-.6-13.1-4.7-14.4-.6-.2-1.1-.2-1.7,0-1,.3-1.9,1.2-2.3,2.2l-.3.7h0v-.1Z"/><g><path fill="currentColor" d="M46.42,41.35c-3.69-1.93-8.79-3.52-15.3-4.75-3.34-.7-5.8-1.23-7.74-2.11-1.76-.7-3.17-1.58-3.87-2.64-.88-1.06-1.23-2.29-1.23-3.87s.88-3.69,2.46-4.92c1.76-1.23,4.04-1.93,6.86-1.93s4.4.53,5.98,1.41c1.76.88,2.99,2.11,4.04,3.69s1.58,3.52,1.76,5.63l16.35-.7c-.53-4.57-1.76-8.62-4.04-12.13s-5.28-6.15-9.32-8.26c-4.04-1.93-8.79-2.99-14.77-2.99s-10.2.88-14.07,2.64-6.86,4.22-8.97,7.21c-2.11,3.17-3.17,6.68-3.17,10.9s.88,7.21,2.46,9.85,4.4,4.75,7.91,6.33c3.69,1.76,8.44,3.17,14.42,4.4,3.87.88,6.86,1.58,8.62,2.46,1.93.88,3.17,1.76,3.87,2.81.7,1.06,1.06,2.29,1.06,3.69s-.35,2.81-1.23,3.87-1.93,1.76-3.34,2.29-3.34.7-5.45.7-4.92-.53-6.68-1.41-3.17-2.11-4.4-3.87c-1.06-1.76-1.76-3.69-2.11-6.15l-16.53.7c.35,4.92,1.58,9.14,4.04,12.66,2.46,3.52,5.63,6.33,10.02,8.26,4.22,1.93,9.5,2.99,15.47,2.99s10.38-.88,14.42-2.46c4.04-1.76,7.03-4.04,9.32-7.21,2.11-3.17,3.17-6.86,3.17-11.25s-.88-6.51-2.46-9.14-4.22-4.92-7.91-6.86l.35.18Z"/><path fill="currentColor" d="M84.41,7.68h-16.35v18.2h-8.44v11.78h8.44v23.21c0,5.63,1.23,9.67,3.87,12.31,2.64,2.64,6.68,3.87,12.13,3.87h13.72v-11.78h-7.03c-2.11,0-3.69-.53-4.75-1.41s-1.58-2.64-1.58-5.1v-21.1h13.36v-11.78h-13.36s0-18.2,0-18.2Z"/><path fill="currentColor" d="M134.35,54.19c0,3.87-.7,6.68-2.11,8.44-1.41,1.76-3.34,2.64-5.8,2.64s-3.87-.88-4.92-2.46c-1.06-1.58-1.58-4.22-1.58-7.91v-29.19h-16.35v33.06c0,6.15,1.41,10.9,4.4,14.24,2.99,3.34,7.03,5.1,12.49,5.1s8.97-1.41,11.78-4.04c1.41-1.41,2.64-3.17,3.52-5.28v8.26h14.95V25.88h-16.35v28.31h0Z"/></g><g><path fill="currentColor" d="M208.21,7.85h-16.35v25.23c-1.41-2.64-3.34-4.75-5.98-6.15s-5.8-2.29-9.5-2.29-7.91,1.06-11.08,3.34c-3.17,2.11-5.63,5.28-7.21,9.32-1.76,4.04-2.64,8.79-2.64,14.24s.88,10.2,2.64,14.24c1.76,4.04,4.04,7.03,7.21,9.32,2.99,2.11,6.68,3.34,11.08,3.34s6.68-.7,9.5-2.29c2.64-1.41,4.75-3.52,6.15-6.33l.35,7.39h1.43s0,.02,0,.03h12.62s0-.02,0-.03h1.78V7.85ZM190.8,59.99v-.35c-.7,2.11-1.76,3.69-3.17,4.92-1.41,1.06-3.17,1.58-5.28,1.58s-5.28-1.41-7.03-4.04-2.64-6.15-2.64-10.55.88-8.09,2.64-10.73,4.04-3.87,7.03-3.87,3.87.53,5.28,1.58c1.41,1.06,2.46,2.64,3.17,4.92.7,2.11,1.06,4.92,1.06,8.26s-.35,5.98-1.06,8.26Z"/><path fill="currentColor" d="M248.51,41.63l-.1-.1c-.2-5-1.4-9.5-2.7-14.3-.6-1.9-1.1-3.9-2.9-5-1.3-.9-2.6-.6-4.1-.5-2.6,1.5-5.4,1.9-8.3,2.4-3.5.7-6.9.9-10.3,1.9-3.2,1-5.7,5.2-3.9,8.4,1,2.4,3.9,3.1,6.3,3.2,4.2-.2,8.4-1,12.5-2,.9,2.5,1,5,1.3,7.7.6,7,.2,24.6-1.6,31.5-1,4.7-2.8,9-6.3,12.4-2.2,2.38-5.07,3.25-8.15,3.53-3.08-.28-5.95-1.15-8.15-3.53-1.14-1.11-1.92-2.31-2.61-3.6-.62-1.14-1.81-1.86-3.11-1.86h-7.07c-2.79,0-4.48,3.08-2.98,5.44,1.96,3.09,3.64,4.96,5.87,7.52l.4.5c.9.7,1.7,1.4,2.5,2.2,3.5,3.1,7.9,5.2,12.6,5.6.66.07,1.33.1,2.01.12v.02c.18,0,.35,0,.53,0,.18,0,.35.01.53,0v-.02c.68-.02,1.36-.05,2.02-.12,4.7-.4,9.1-2.5,12.6-5.6.8-.8,1.6-1.5,2.5-2.2l.4-.5c3.4-3.9,5.8-8.5,7.4-13.4,2.9-9.7,4.1-29.8,2.8-39.7Z"/></g></g></g></g></svg>'

ICONE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
         'fill="#b1338a"/><path d="M32 12v40M18 52h28M14 24h36M20 24l-8 16h16zM44 24l-8 16h16z" stroke="#ffffff" '
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
        STUDIO,
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": "Droit français sourcé",
         "inLanguage": "fr-FR", "description": DESCRIPTION, "publisher": {"@id": "https://studjoow.com/#org"}},
        {"@type": "SoftwareApplication", "@id": SITE + "/#app", "name": "Serveur MCP Droit français",
         "applicationCategory": "DeveloperApplication", "image": SITE + "/og.png", "operatingSystem": "Tous (service web)",
         "url": SITE + "/", "installUrl": SITE + "/mcp", "softwareHelp": REPO, "codeRepository": REPO,
         "license": "https://opensource.org/licenses/MIT", "inLanguage": "fr-FR", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
         "author": {"@id": "https://studjoow.com/#org"}, "publisher": {"@id": "https://studjoow.com/#org"},
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
:root{--bg:#f2f3fb;--fg:#1b0b16;--muted:#3a3f4e;--card:#fff;--line:#d8dbe4;--accent:#b1338a;--accent2:#e0539f;--soft:#eddaec;--onaccent:#fff;--ok:#00bb7f;--warn:#f99c00}
@media (prefers-color-scheme:dark){:root{--bg:#040e30;--fg:#f7f8fb;--muted:#b4b9c6;--card:#0b1742;--line:#1e2b5e;--accent:#e0539f;--accent2:#e0539f;--soft:#2a1640;--onaccent:#040e30;--ok:#00bb7f;--warn:#f99c00}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 16px 64px}
h1{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:0 0 12px;letter-spacing:-.01em}
h2{font-size:22px;margin:44px 0 12px}h3{font-size:18px;margin:20px 0 6px}
p{margin:0 0 12px}.lead{font-size:19px;color:var(--muted)}
a{color:var(--accent)}code{font:15px ui-monospace,SFMono-Regular,Menlo,monospace}
.url{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:20px 0}
.url code{font-size:17px;word-break:break-all;flex:1;min-width:200px}
button{font:inherit;font-size:15px;border:0;border-radius:8px;padding:8px 14px;background:var(--accent);color:var(--onaccent);cursor:pointer;font-weight:600}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:0 0 18px}
.marque{display:inline-flex;align-items:center;gap:8px;font-size:14px;text-decoration:none;color:var(--muted)}
.logo-sj{height:20px;width:auto;color:var(--fg)}.signature .logo-sj{height:18px}
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
.note{border-left:4px solid var(--accent2);padding:8px 14px;background:var(--card);border-radius:0 8px 8px 0}
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
<meta name="theme-color" content="#b1338a">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="text/plain" href="/llms.txt" title="llms.txt">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Droit français sourcé">
<meta property="og:title" content="%(titre)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(site)s/">
<meta property="og:image" content="%(site)s/og.png">
<meta property="og:image:width" content="1280">
<meta property="og:image:height" content="640">
<meta property="og:image:alt" content="Le droit français officiel, sourcé, dans Claude et ChatGPT. Un projet Studjoow.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="%(site)s/og.png">
<meta name="author" content="Studjoow">
<script type="application/ld+json">%(ld)s</script>
<style>%(css)s</style>
</head>
<body>
<main>
<header>
<p class="top"><a href="https://studjoow.com" class="marque"><span>Un projet</span>%(logo)s</a><span class="etat">%(etat)s</span></p>
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
<p class="signature"><a href="https://studjoow.com" class="marque"><span>Conçu et maintenu par</span>%(logo)s</a><br>Studio créatif et tech : sites sur mesure, branding, IA, SEO et GEO.</p>
</footer>
</main>
</body>
</html>""" % {"titre": e(TITRE), "desc": e(DESCRIPTION), "site": SITE, "ld": json_ld().replace("</", "<\\/"),
             "css": CSS, "etat": etat, "stats": stats, "outils": outils, "faq": faq, "repo": REPO,
             "repo_court": "github.com/JohnJackHouzi/droit-francais-skill", "logo": LOGO_STUDJOOW}


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
        "- Conçu et maintenu par Studjoow, studio créatif et tech : https://studjoow.com",
        "",
    ]
    return "\n".join(lignes)
