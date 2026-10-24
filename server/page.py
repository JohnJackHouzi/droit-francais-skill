import html
import json
import os
import time

SITE = os.environ.get("DROIT_PUBLIC_URL", "https://droit.studjoow.com").rstrip("/")
REPO = "https://github.com/JohnJackHouzi/droit-francais-skill"
PRIX = os.environ.get("DROIT_PRIX", "4,99")
ESSAI_PAR_JOUR = int(os.environ.get("DROIT_ESSAI_PAR_JOUR", "20"))
PLAFOND = int(os.environ.get("DROIT_PLAFOND_ABONNE", "500"))
PRIX_PRO = os.environ.get("DROIT_PRIX_PRO", "19")
PRIX_PRO_AN = os.environ.get("DROIT_PRIX_PRO_AN", "190")
PLAFOND_PRO = int(os.environ.get("DROIT_PLAFOND_PRO", "3000"))
OFFRES_PAGE = {
    "particulier": ("Particulier", PRIX, "mois", PLAFOND),
    "pro": ("Pro", PRIX_PRO, "mois", PLAFOND_PRO),
    "pro-an": ("Pro annuel", PRIX_PRO_AN, "an", PLAFOND_PRO),
}
LIEN_ABONNEMENT = os.environ.get("DROIT_LIEN_ABONNEMENT", "").strip()
STUDIO = {"@type": "Organization", "@id": "https://studjoow.com/#organization", "name": "Studjoow", "url": "https://studjoow.com",
          "description": "Studio créatif et tech : sites sur mesure, branding, IA, SEO et GEO.",
          "logo": "https://studjoow.com/brand/logo-long-blanc.svg", "email": "hello@studjoow.com",
          "foundingDate": "2007",
          "founder": {"@type": "Person", "@id": "https://studjoow.com/#johnhouzi", "name": "John Houzi",
                      "url": "https://studjoow.com/studio"}}
AUTRES_PROJETS = [
    ("Mishpat", "https://mishpat.studjoow.com",
     "Le même principe pour le droit israélien : plus de 6 000 textes (lois, ordonnances, règlements) et l'historique de leurs publications officielles. Gratuit."),
    ("Vérifie mon projet", "https://github.com/JohnJackHouzi/studjoow-conformite",
     "Un plugin Claude Code qui passe un projet web au crible du droit français et européen, en s'appuyant sur ce serveur."),
    ("Le Lab Studjoow", "https://studjoow.com/lab",
     "Les autres outils du studio en accès libre : audit SEO et GEO Sk:vr, rayon X de marque, agent SEO Next.js."),
]
TITRE = "Droit français sourcé : le droit officiel dans Claude et ChatGPT"
DESCRIPTION = ("Branchez le droit français et européen officiel sur Claude ou ChatGPT : codes, lois, Journal officiel, "
               "conventions collectives, jurisprudence et EUR-Lex. Chaque réponse sourcée et vérifiée. "
               "Essai gratuit, puis %s € par mois." % PRIX)

FAQ = [
    ("Qu'est-ce que ce service ?",
     "Un serveur MCP (Model Context Protocol) qui donne à Claude, ChatGPT ou tout assistant compatible un accès en "
     "lecture aux données ouvertes officielles du droit français (DILA, Légifrance) et du droit de l'Union "
     "européenne (EUR-Lex). L'assistant cherche dans les textes avant de répondre et cite chaque source avec son "
     "identifiant et son lien."),
    ("Pourquoi payer si le code est libre ?",
     "Le code est sous licence MIT : chacun peut héberger son propre serveur gratuitement. L'abonnement paie le "
     "service clé en main : le serveur, 33 Go de bases indexées, les mises à jour de la DILA chaque nuit et la "
     "maintenance. Vous collez une adresse, c'est tout."),
    ("Que comprend l'essai gratuit ?",
     "%d requêtes par jour sur l'adresse publique, sans inscription, avec les mêmes sources et les mêmes outils. "
     "Assez pour essayer sur de vraies questions avant de vous abonner." % ESSAI_PAR_JOUR),
    ("Comment fonctionne l'abonnement ?",
     "%s € par mois, sans engagement. Ajoutez le connecteur %s/abonne/mcp dans Claude ou ChatGPT et connectez-vous "
     "avec votre e-mail et un code : %d requêtes par jour, bien au-delà d'un usage intensif. Pour les clients sans "
     "connexion, une adresse personnelle est aussi fournie. Résiliable à tout moment depuis la page Mon compte, avec "
     "effet à la fin du mois payé." % (PRIX, SITE, PLAFOND)),
    ("Quelle différence entre Particulier et Pro ?",
     "Les deux donnent accès aux mêmes sources et aux mêmes outils. L'offre Pro (%s € par mois, ou %s € par an) "
     "monte à %d requêtes par jour, émet les factures au nom de votre entreprise et inclut un support prioritaire "
     "par e-mail : elle est pensée pour un usage professionnel quotidien (juristes, RH, DPO, avocats, TPE)."
     % (PRIX_PRO, PRIX_PRO_AN, PLAFOND_PRO)),
    ("Que se passe-t-il quand l'essai gratuit est épuisé ?",
     "L'assistant reçoit un message clair indiquant que le quota du jour est atteint, avec le lien d'abonnement. "
     "L'essai repart le lendemain à minuit (UTC)."),
    ("Mon adresse personnelle a fuité, que faire ?",
     "Régénérez-la depuis la page Mon compte : l'ancienne cesse aussitôt de fonctionner. Vous pouvez aussi y "
     "déconnecter tous vos assistants. Le plus sûr reste la connexion par e-mail (%s/abonne/mcp), sans adresse secrète "
     "à copier." % SITE),
    ("Les réponses sont-elles fiables ?",
     "Chaque référence peut être contrôlée par l'outil verifier_references avant d'être citée : une référence "
     "introuvable ou une citation absente du texte est signalée. Cela réduit fortement les inventions, sans "
     "remplacer la lecture du texte officiel sur Légifrance ou EUR-Lex. C'est de l'information juridique, pas un "
     "conseil : pour un cas concret, consultez un avocat."),
    ("Quelles sources sont couvertes ?",
     "Les codes et lois consolidés avec toutes leurs versions datées (LEGI), le Journal officiel (JORF), les "
     "conventions collectives (KALI), la jurisprudence administrative (JADE), judiciaire (CASS, INCA, CAPP), "
     "constitutionnelle (CONSTIT) et de la CNIL, ainsi que les règlements, directives, traités et arrêts de la Cour "
     "de justice de l'Union européenne en français."),
]


USAGES = [
    ("Particuliers", "Connaître vos droits, texte à l'appui.",
     ["Mon propriétaire peut-il garder ma caution ?", "Combien de temps pour retourner une commande en ligne ?"],
     "Une mise en demeure qui cite les bons articles."),
    ("Salariés et RH", "Votre convention collective, pas une moyenne.",
     ["Quel préavis pour un cadre, convention Syntec ?", "Combien de jours de congé pour un mariage, IDCC 1486 ?"],
     "La règle de votre branche, à la date des faits."),
    ("Entrepreneurs", "Lancer sans angle mort.",
     ["Quelles mentions obligatoires sur mes factures ?", "Mon site doit-il afficher un droit de rétractation ?"],
     "Les obligations qui s'appliquent, article par article."),
    ("Juristes, avocats, DPO", "Citer juste, à la bonne date.",
     ["Version de l'article L1237-19 au 1er mars 2019 ?", "Arrêts récents de la chambre sociale sur le forfait jours ?"],
     "Pourvoi, ECLI, version : tout est traçable."),
    ("Étudiants", "Comprendre un arrêt plutôt que le réciter.",
     ["Que juge l'arrêt C-131/12 de la CJUE ?", "Comment l'article 1240 a-t-il remplacé l'ancien 1382 ?"],
     "Le texte intégral, pas un résumé de mémoire."),
    ("Journalistes", "Vérifier une citation en dix secondes.",
     ["Cet article de loi cité dans le débat existe-t-il ?", "Que dit vraiment le règlement IA sur les deepfakes ?"],
     "La source exacte, avec son lien officiel."),
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
    ("analyser_conformite", "Pré-analyse de conformité d'un projet : RGPD, cookies, vente en ligne, IA, DSA, droit d'auteur, article par article"),
    ("etat_base", "Date de mise à jour et volume de chaque base"),
]

SOURCES = [
    ("LEGI", "Codes et lois consolidés", "toutes les versions datées de chaque article"),
    ("JORF", "Journal officiel", "les textes tels que publiés"),
    ("KALI", "Conventions collectives", "accords et avenants, par IDCC"),
    ("JADE", "Juridictions administratives", "Conseil d'État, cours et tribunaux administratifs"),
    ("CASS", "Cour de cassation", "arrêts publiés et inédits (INCA), cours d'appel (CAPP)"),
    ("CONSTIT", "Conseil constitutionnel", "décisions DC et QPC"),
    ("CNIL", "CNIL", "délibérations"),
    ("EUR-Lex", "Droit de l'Union", "règlements, directives, traités, Charte, arrêts de la CJUE"),
]

LOGO_STUDJOOW = '<svg role="img" aria-label="Studjoow" class="logo-sj" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 421.36 103.17"><g><g><rect fill="#b1338a" x="411.66" y="68.85" width="9.7" height="9"/><g><path fill="#b1338a" d="M218.61,68.63c2.4-.8,5.2.6,6,3,.8,2.1,0,4.6-1.9,5.9-1.5,1-3.3,1-4.8.2-2-.9-2.9-3.3-2.6-5.4.3-1.7,1.5-3.2,3.2-3.7h.1Z"/><path fill="#b1338a" d="M222.01,44.73c2.4-.8,5.2.6,6,3,.8,2.1,0,4.6-1.9,5.9-1.5,1-3.3,1-4.8.2-2-.9-2.9-3.3-2.6-5.4.3-1.7,1.5-3.2,3.2-3.7h.1Z"/><path fill="currentColor" d="M331.71,33.33c-3.6-3.8-8.3-6.7-13.6-7.6-4.3-.9-8.6-.1-12.5,1.6-3.2,1.5-6.1,3.7-8.4,6.3-.8-1.1-1.9-2.1-3.2-2.6-1.3-.5-2.5-.2-3.8-.2-2.2-1.8-4.7-3.3-7.4-4.2-4.9-1.7-10.4-1.7-15.2.2-3.8,1.5-6.9,4.4-9,7.7-2.8,4.3-4.2,9.4-4.9,14.4-.9,7.8,2,15.7,7.4,21.5,3.6,3.8,8.3,6.7,13.6,7.7,4.3.8,8.6.1,12.5-1.6,4.5-2.1,8.2-5.5,10.9-9.5.2.3.4.6.7.9l1.6,2.1c2.2,2.9,5.1,5.3,8.5,6.7.4.2.8.3,1.2.4,4.9,1.7,10.4,1.7,15.2-.2,3.8-1.5,6.9-4.4,9-7.7,2.8-4.3,4.2-9.4,4.9-14.4.9-7.8-2-15.7-7.4-21.5h-.1ZM288.11,61.23c-2.3,2.7-5.5,4.8-9,5.7-2.6.7-5.4.4-7.6-1-2.2-1.4-3.9-3.3-5-5.7-2.4-4.9-2.2-10.4-.4-15.5.8-2.1,1.8-4.1,3.4-5.8,1.8-1.9,4.1-3.3,6.8-3.4,3.1-.3,5.4,1.3,7.8,2.9-.2.8-.7,1.5-.4,2.3.4,1.2,1.5,2.2,2.3,3.1,2.6,3,4.7,6.4,4.7,10.4.1,2.5-1,4.8-2.5,6.8h0l-.1.2ZM326.71,58.73c-.8,2.1-1.8,4.1-3.4,5.8-1.8,1.9-4.1,3.3-6.8,3.4-1.1,0-2.1,0-3-.3-2.8-.8-4.9-3.1-5.9-5.8l-.2-.7c-.4-1-.9-1.8-1.5-2.7-2.2-2.7-3.8-5.8-3.8-9.3-.1-2.5,1-4.8,2.5-6.8,2.3-2.7,5.5-4.8,9-5.7,2.6-.7,5.4-.4,7.6,1s4,3.3,5,5.7c2.4,4.9,2.2,10.4.4,15.5h0l.1-.1Z"/><path fill="currentColor" d="M227.91.33c3.8-1.2,8.2,1,9.4,4.8,1.2,3.3,0,7.2-2.9,9.2-2.3,1.5-5.1,1.6-7.6.3-3.1-1.4-4.6-5.2-4-8.4.5-2.7,2.4-5.1,5.1-5.9Z"/><path fill="currentColor" d="M377.21,29.33c-1.9,4.6-3.3,9.4-4.4,14.4-.9,4.2-1.9,10.3-3.8,14-4.4,8.9-7.8,11.2-11.5,1-2-4.8-3.2-12.4-3.8-17.8-.5-4.2-.6-13.1-4.7-14.4-1.3-.4-2.6.1-3.6,1.2-4,4.4-2.3,16.3-1.6,21.8v.2c2,10.6,5,20.7,14.3,26.3,11.5,6.6,17.6-1.9,21.3-13.6h0c2.2,6.4,5.5,10.2,11.2,13.6,11.3,6.5,16.2-1.6,20.1-13.1,1.7-4.3,2.8-9.9,3.9-15,1-5.8,3.3-14.5.7-19.1h0c-4.6-5.7-8.6,2.7-9.4,7.4-1.5,6.6-2.3,15.5-5.4,21.5-4.4,8.9-6.8,11.2-10.5,1-2-4.8-3.2-12.4-3.8-17.8-.5-4.2-.6-13.1-4.7-14.4-.6-.2-1.1-.2-1.7,0-1,.3-1.9,1.2-2.3,2.2l-.3.7h0v-.1Z"/><g><path fill="currentColor" d="M46.42,41.35c-3.69-1.93-8.79-3.52-15.3-4.75-3.34-.7-5.8-1.23-7.74-2.11-1.76-.7-3.17-1.58-3.87-2.64-.88-1.06-1.23-2.29-1.23-3.87s.88-3.69,2.46-4.92c1.76-1.23,4.04-1.93,6.86-1.93s4.4.53,5.98,1.41c1.76.88,2.99,2.11,4.04,3.69s1.58,3.52,1.76,5.63l16.35-.7c-.53-4.57-1.76-8.62-4.04-12.13s-5.28-6.15-9.32-8.26c-4.04-1.93-8.79-2.99-14.77-2.99s-10.2.88-14.07,2.64-6.86,4.22-8.97,7.21c-2.11,3.17-3.17,6.68-3.17,10.9s.88,7.21,2.46,9.85,4.4,4.75,7.91,6.33c3.69,1.76,8.44,3.17,14.42,4.4,3.87.88,6.86,1.58,8.62,2.46,1.93.88,3.17,1.76,3.87,2.81.7,1.06,1.06,2.29,1.06,3.69s-.35,2.81-1.23,3.87-1.93,1.76-3.34,2.29-3.34.7-5.45.7-4.92-.53-6.68-1.41-3.17-2.11-4.4-3.87c-1.06-1.76-1.76-3.69-2.11-6.15l-16.53.7c.35,4.92,1.58,9.14,4.04,12.66,2.46,3.52,5.63,6.33,10.02,8.26,4.22,1.93,9.5,2.99,15.47,2.99s10.38-.88,14.42-2.46c4.04-1.76,7.03-4.04,9.32-7.21,2.11-3.17,3.17-6.86,3.17-11.25s-.88-6.51-2.46-9.14-4.22-4.92-7.91-6.86l.35.18Z"/><path fill="currentColor" d="M84.41,7.68h-16.35v18.2h-8.44v11.78h8.44v23.21c0,5.63,1.23,9.67,3.87,12.31,2.64,2.64,6.68,3.87,12.13,3.87h13.72v-11.78h-7.03c-2.11,0-3.69-.53-4.75-1.41s-1.58-2.64-1.58-5.1v-21.1h13.36v-11.78h-13.36s0-18.2,0-18.2Z"/><path fill="currentColor" d="M134.35,54.19c0,3.87-.7,6.68-2.11,8.44-1.41,1.76-3.34,2.64-5.8,2.64s-3.87-.88-4.92-2.46c-1.06-1.58-1.58-4.22-1.58-7.91v-29.19h-16.35v33.06c0,6.15,1.41,10.9,4.4,14.24,2.99,3.34,7.03,5.1,12.49,5.1s8.97-1.41,11.78-4.04c1.41-1.41,2.64-3.17,3.52-5.28v8.26h14.95V25.88h-16.35v28.31h0Z"/></g><g><path fill="currentColor" d="M208.21,7.85h-16.35v25.23c-1.41-2.64-3.34-4.75-5.98-6.15s-5.8-2.29-9.5-2.29-7.91,1.06-11.08,3.34c-3.17,2.11-5.63,5.28-7.21,9.32-1.76,4.04-2.64,8.79-2.64,14.24s.88,10.2,2.64,14.24c1.76,4.04,4.04,7.03,7.21,9.32,2.99,2.11,6.68,3.34,11.08,3.34s6.68-.7,9.5-2.29c2.64-1.41,4.75-3.52,6.15-6.33l.35,7.39h1.43s0,.02,0,.03h12.62s0-.02,0-.03h1.78V7.85ZM190.8,59.99v-.35c-.7,2.11-1.76,3.69-3.17,4.92-1.41,1.06-3.17,1.58-5.28,1.58s-5.28-1.41-7.03-4.04-2.64-6.15-2.64-10.55.88-8.09,2.64-10.73,4.04-3.87,7.03-3.87,3.87.53,5.28,1.58c1.41,1.06,2.46,2.64,3.17,4.92.7,2.11,1.06,4.92,1.06,8.26s-.35,5.98-1.06,8.26Z"/><path fill="currentColor" d="M248.51,41.63l-.1-.1c-.2-5-1.4-9.5-2.7-14.3-.6-1.9-1.1-3.9-2.9-5-1.3-.9-2.6-.6-4.1-.5-2.6,1.5-5.4,1.9-8.3,2.4-3.5.7-6.9.9-10.3,1.9-3.2,1-5.7,5.2-3.9,8.4,1,2.4,3.9,3.1,6.3,3.2,4.2-.2,8.4-1,12.5-2,.9,2.5,1,5,1.3,7.7.6,7,.2,24.6-1.6,31.5-1,4.7-2.8,9-6.3,12.4-2.2,2.38-5.07,3.25-8.15,3.53-3.08-.28-5.95-1.15-8.15-3.53-1.14-1.11-1.92-2.31-2.61-3.6-.62-1.14-1.81-1.86-3.11-1.86h-7.07c-2.79,0-4.48,3.08-2.98,5.44,1.96,3.09,3.64,4.96,5.87,7.52l.4.5c.9.7,1.7,1.4,2.5,2.2,3.5,3.1,7.9,5.2,12.6,5.6.66.07,1.33.1,2.01.12v.02c.18,0,.35,0,.53,0,.18,0,.35.01.53,0v-.02c.68-.02,1.36-.05,2.02-.12,4.7-.4,9.1-2.5,12.6-5.6.8-.8,1.6-1.5,2.5-2.2l.4-.5c3.4-3.9,5.8-8.5,7.4-13.4,2.9-9.7,4.1-29.8,2.8-39.7Z"/></g></g></g></g></svg>'

ICONE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
         'fill="#b1338a"/><path d="M32 12v40M18 52h28M14 24h36M20 24l-8 16h16zM44 24l-8 16h16z" stroke="#ffffff" '
         'stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

FONTS = """@font-face{font-family:'Instrument Serif';font-style:normal;font-weight:400;font-display:swap;src:url(/static/fonts/instrument-serif-normal-400.woff2) format('woff2')}
@font-face{font-family:'Instrument Serif';font-style:italic;font-weight:400;font-display:swap;src:url(/static/fonts/instrument-serif-italic-400.woff2) format('woff2')}
@font-face{font-family:'Plus Jakarta Sans';font-style:normal;font-weight:400 700;font-display:swap;src:url(/static/fonts/plus-jakarta-sans-normal-400-700.woff2) format('woff2')}
@font-face{font-family:'Geist Mono';font-style:normal;font-weight:400 500;font-display:swap;src:url(/static/fonts/geist-mono-normal-400.woff2) format('woff2')}"""

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


def insec(t):
    return t.replace(" ?", "&#8239;?").replace(" :", "&#160;:").replace(" !", "&#8239;!")


def nombre(n):
    return "{:,}".format(n).replace(",", " ")


def json_ld():
    prix = PRIX.replace(",", ".")
    graph = [
        STUDIO,
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": "Droit français sourcé",
         "inLanguage": "fr-FR", "description": DESCRIPTION, "publisher": {"@id": "https://studjoow.com/#organization"}},
        {"@type": "SoftwareApplication", "@id": SITE + "/#app", "name": "Droit français sourcé (serveur MCP)",
         "applicationCategory": "BusinessApplication", "applicationSubCategory": "Recherche juridique",
         "operatingSystem": "Tous (service web)", "image": SITE + "/og.png",
         "url": SITE + "/", "installUrl": SITE + "/mcp", "softwareHelp": REPO, "codeRepository": REPO,
         "license": "https://opensource.org/licenses/MIT", "inLanguage": "fr-FR",
         "offers": [
             {"@type": "Offer", "name": "Essai gratuit", "price": "0", "priceCurrency": "EUR",
              "description": "%d requêtes par jour, sans inscription" % ESSAI_PAR_JOUR},
             {"@type": "Offer", "name": "Abonnement", "price": prix, "priceCurrency": "EUR",
              "priceSpecification": {"@type": "UnitPriceSpecification", "price": prix, "priceCurrency": "EUR",
                                     "billingDuration": "P1M", "unitText": "MONTH"},
              "description": "%d requêtes par jour par adresse personnelle, sans engagement" % PLAFOND},
             {"@type": "Offer", "name": "Pro", "price": PRIX_PRO.replace(",", "."), "priceCurrency": "EUR",
              "priceSpecification": {"@type": "UnitPriceSpecification", "price": PRIX_PRO.replace(",", "."),
                                     "priceCurrency": "EUR", "billingDuration": "P1M", "unitText": "MONTH"},
              "description": "%d requêtes par jour, facture au nom de l'entreprise, support par e-mail" % PLAFOND_PRO},
             {"@type": "Offer", "name": "Pro annuel", "price": PRIX_PRO_AN.replace(",", "."), "priceCurrency": "EUR",
              "priceSpecification": {"@type": "UnitPriceSpecification", "price": PRIX_PRO_AN.replace(",", "."),
                                     "priceCurrency": "EUR", "billingDuration": "P1Y", "unitText": "ANN"},
              "description": "Offre Pro payée à l'année, deux mois offerts"},
         ],
         "author": {"@id": "https://studjoow.com/#organization"}, "publisher": {"@id": "https://studjoow.com/#organization"},
         "description": DESCRIPTION, "featureList": [o[1] for o in OUTILS]},
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
:root{
  --bg:#f2f3fb;--paper:#ffffff;--fg:#1b0b16;--ink:#3a3f4e;--muted:#7e8493;--line:#d8dbe4;--rule:rgba(27,11,22,.07);
  --accent:#b1338a;--accent2:#e0539f;--soft:#eddaec;--deep:#040e30;--onaccent:#fff;--ok:#00a06d;--ko:#bf000f;
  --serif:'Instrument Serif',Georgia,'Times New Roman',serif;
  --sans:'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#040e30;--paper:#0a1640;--fg:#f7f8fb;--ink:#c9cdd8;--muted:#8a90a3;--line:#1e2b5e;--rule:rgba(247,248,251,.06);
  --accent:#e0539f;--accent2:#e0539f;--soft:#2a1640;--onaccent:#040e30;--ok:#34d39b;--ko:#ff6b7a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:16.5px/1.65 var(--sans);overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.5;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .05 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
a{color:inherit}
.wrap{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:0 24px}
code,.mono{font-family:var(--mono);font-size:.88em}
.serif{font-family:var(--serif);font-weight:400}
::selection{background:var(--accent);color:var(--onaccent)}

/* barre */
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:22px 0;flex-wrap:wrap}
.marque{display:inline-flex;align-items:center;gap:9px;text-decoration:none;color:var(--muted);font-size:13px;letter-spacing:.02em}
.logo-sj{height:19px;width:auto;color:var(--fg)}
.nav{display:flex;gap:22px;align-items:center;font-size:14px}
.nav a{text-decoration:none;color:var(--ink)}.nav a:hover{color:var(--accent)}
.etat{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;color:var(--muted);font-family:var(--mono)}
.pt{width:8px;height:8px;border-radius:50%;background:#f99c00;box-shadow:0 0 0 4px rgba(249,156,0,.15)}
.pt.ok{background:var(--ok);box-shadow:0 0 0 4px rgba(0,160,109,.15);animation:pouls 2.4s infinite}
@keyframes pouls{50%{box-shadow:0 0 0 7px rgba(0,160,109,0)}}

/* hero */
.hero{display:grid;grid-template-columns:1.08fr .92fr;gap:56px;align-items:center;padding:40px 0 72px;position:relative}
.hero::after{content:"";position:absolute;right:-12%;top:-8%;width:620px;height:620px;border-radius:50%;z-index:-1;
  background:radial-gradient(closest-side,rgba(177,51,138,.18),transparent 70%);filter:blur(10px)}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
  display:flex;align-items:center;gap:10px;margin:0 0 22px}
.eyebrow::before{content:"§";font-family:var(--serif);font-size:22px;letter-spacing:0;line-height:1}
h1{font-family:var(--serif);font-weight:400;font-size:clamp(46px,7.2vw,92px);line-height:.96;letter-spacing:-.02em;margin:0 0 26px}
h1 em{font-style:italic;color:var(--accent)}
.lead{font-size:clamp(17px,1.6vw,19.5px);color:var(--ink);max-width:560px;margin:0 0 30px}
.url{display:flex;align-items:center;gap:10px;background:var(--paper);border:1px solid var(--line);border-radius:14px;
  padding:8px 8px 8px 18px;max-width:560px;box-shadow:0 1px 0 var(--rule),0 18px 40px -24px rgba(4,14,48,.35)}
.url code{flex:1;font-size:15px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn{font:600 14.5px/1 var(--sans);border:0;border-radius:10px;padding:13px 18px;cursor:pointer;text-decoration:none;
  display:inline-flex;align-items:center;gap:8px;transition:transform .15s ease,box-shadow .15s ease,background .15s}
.btn:hover{transform:translateY(-1px)}
.btn-1{background:var(--accent);color:var(--onaccent);box-shadow:0 10px 24px -12px var(--accent)}
.btn-2{background:transparent;color:var(--fg);border:1px solid var(--line)}
.btn-2:hover{border-color:var(--accent)}
.btn[aria-disabled=true]{opacity:.55;cursor:not-allowed;transform:none}
.ctas{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}
.mini{font-size:13px;color:var(--muted);margin-top:14px}

/* fiche animée */
.fiche{position:relative;background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:26px 26px 22px;
  box-shadow:0 40px 80px -40px rgba(4,14,48,.45);transform:rotate(.6deg)}
.fiche::before{content:"";position:absolute;inset:0;border-radius:18px;pointer-events:none;
  background:repeating-linear-gradient(to bottom,transparent 0 31px,var(--rule) 31px 32px)}
.fiche .marge{position:absolute;left:52px;top:0;bottom:0;width:1px;background:rgba(224,83,159,.35)}
.fiche-tete{display:flex;justify-content:space-between;font:12px var(--mono);color:var(--muted);margin-bottom:16px;padding-left:40px}
.q{font-family:var(--serif);font-size:25px;line-height:1.2;padding-left:40px;margin:0 0 14px;position:relative}
.q::before{content:"Q.";position:absolute;left:0;top:2px;font:600 13px var(--mono);color:var(--accent)}
.r{padding-left:40px;position:relative;font-size:15px;color:var(--ink);margin:0 0 16px}
.r::before{content:"R.";position:absolute;left:0;top:1px;font:600 13px var(--mono);color:var(--accent)}
.r cite{font-style:normal;font-family:var(--mono);font-size:12.5px;background:var(--soft);color:var(--fg);padding:1px 6px;border-radius:5px}
.refs{list-style:none;margin:0;padding:0 0 0 40px;display:grid;gap:8px}
.refs li{display:flex;align-items:center;justify-content:space-between;gap:10px;font:12.5px/1.4 var(--mono);
  border:1px dashed var(--line);border-radius:9px;padding:9px 10px;background:var(--bg)}
.tampon{font:600 10.5px var(--mono);letter-spacing:.12em;padding:4px 7px;border:1.5px solid currentColor;border-radius:4px;
  transform:rotate(-6deg);white-space:nowrap}
.tampon.ok{color:var(--ok)}.tampon.ko{color:var(--ko)}
.refs li.faux span:first-child{text-decoration:line-through;color:var(--muted)}
@media (prefers-reduced-motion:no-preference){
  .anim{opacity:0;animation:monte .7s cubic-bezier(.2,.7,.2,1) forwards}
  .q.anim{animation-delay:.25s}.r.anim{animation-delay:.9s}
  .refs li:nth-child(1){animation-delay:1.5s}.refs li:nth-child(2){animation-delay:1.8s}.refs li:nth-child(3){animation-delay:2.1s}
  .tampon{opacity:0;animation:tampon .35s cubic-bezier(.3,1.6,.5,1) forwards}
  .refs li:nth-child(1) .tampon{animation-delay:2.5s}.refs li:nth-child(2) .tampon{animation-delay:2.8s}.refs li:nth-child(3) .tampon{animation-delay:3.1s}
  .hero-txt>*{opacity:0;animation:monte .8s cubic-bezier(.2,.7,.2,1) forwards}
  .hero-txt>*:nth-child(2){animation-delay:.08s}.hero-txt>*:nth-child(3){animation-delay:.16s}.hero-txt>*:nth-child(4){animation-delay:.24s}.hero-txt>*:nth-child(5){animation-delay:.32s}
}
@keyframes monte{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes tampon{from{opacity:0;transform:scale(2.2) rotate(-14deg)}to{opacity:1;transform:scale(1) rotate(-6deg)}}

/* chiffres */
.chiffres{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--fg);border-bottom:1px solid var(--line)}
.chiffres div{padding:26px 22px 24px;border-left:1px solid var(--line)}.chiffres div:first-child{border-left:0;padding-left:0}
.chiffres b{display:block;font-family:var(--serif);font-weight:400;font-size:clamp(34px,4vw,50px);line-height:1;letter-spacing:-.01em}
.chiffres span{font-size:13.5px;color:var(--muted)}

/* sections */
section{padding:96px 0 0}
.titre{display:grid;grid-template-columns:140px 1fr;gap:24px;margin-bottom:40px;align-items:baseline}
.titre .num{font-family:var(--serif);font-size:56px;line-height:1;color:var(--accent)}
.titre h2{font-family:var(--serif);font-weight:400;font-size:clamp(34px,4.4vw,54px);line-height:1.02;letter-spacing:-.015em;margin:0}
.titre p{grid-column:2;margin:12px 0 0;color:var(--ink);max-width:640px}
.etapes{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin-left:164px;border-top:1px solid var(--line)}
.etapes div{padding:24px 26px 0 0}
.etapes b{font:500 12px var(--mono);color:var(--accent);letter-spacing:.1em}
.etapes h3{font:600 18px/1.3 var(--sans);margin:8px 0 6px}
.etapes p{margin:0;color:var(--ink);font-size:15px}
.sources{margin-left:164px;border-top:1px solid var(--fg)}
.sources div{display:grid;grid-template-columns:110px 260px 1fr;gap:18px;padding:15px 0;border-bottom:1px solid var(--line);align-items:baseline}
.sources code{color:var(--accent);font-weight:500}
.sources span{color:var(--muted);font-size:14.5px}
.sources div:hover{background:linear-gradient(90deg,var(--soft),transparent 60%)}

/* vérification */
.bande{margin-top:96px;background:var(--deep);color:#f7f8fb;position:relative;overflow:hidden}
.bande::before{content:"";position:absolute;inset:0;opacity:.6;
  background:radial-gradient(600px 300px at 85% 0%,rgba(224,83,159,.35),transparent 70%),radial-gradient(500px 300px at 0% 100%,rgba(177,51,138,.25),transparent 70%)}
.bande .wrap{display:grid;grid-template-columns:1fr 1.05fr;gap:56px;padding-top:88px;padding-bottom:88px}
.bande h2{font-family:var(--serif);font-weight:400;font-size:clamp(36px,4.4vw,56px);line-height:1;margin:0 0 18px}
.bande h2 em{color:#e0539f}
.bande p{color:#c9cdd8;margin:0 0 14px}
.terminal{background:rgba(4,14,48,.7);border:1px solid rgba(247,248,251,.12);border-radius:14px;padding:20px 22px;
  font:13px/1.75 var(--mono);color:#dfe3ee;box-shadow:0 30px 60px -30px #000;overflow-x:auto}
.terminal .p{color:#e0539f}.terminal .ok{color:#34d39b}.terminal .ko{color:#ff6b7a}.terminal .d{color:#8a90a3}

/* tarifs */
.tarifs{display:grid;grid-template-columns:.9fr 1.05fr 1.05fr;gap:18px;margin-left:164px;align-items:stretch}
.offre{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:28px 26px;display:flex;flex-direction:column}
.offre h3{font:600 13px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
.prix{font-family:var(--serif);font-size:62px;line-height:1;margin:0}.prix small{font:500 15px var(--sans);color:var(--muted);margin-left:6px}
.offre ul{list-style:none;padding:0;margin:20px 0 24px;display:grid;gap:9px;font-size:15px;color:var(--ink)}
.offre li{padding-left:22px;position:relative}.offre li::before{content:"§";position:absolute;left:0;color:var(--accent);font-family:var(--serif);font-size:17px;line-height:1.3}
.offre .btn{margin-top:auto;justify-content:center}
.offre.vedette{border:1.5px solid var(--accent);position:relative;box-shadow:0 30px 60px -36px var(--accent)}
.offre.vedette .etiquette{position:absolute;top:-12px;left:24px;background:var(--accent);color:var(--onaccent);font:600 11px var(--mono);
  letter-spacing:.1em;text-transform:uppercase;padding:5px 9px;border-radius:6px}
.offre.pro{background:var(--deep);border-color:var(--deep);color:#f7f8fb;position:relative;overflow:hidden}
.offre.pro::before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(420px 220px at 100% 0%,rgba(224,83,159,.3),transparent 70%)}
.offre.pro>*{position:relative}
.offre.pro h3{color:#8a90a3}.offre.pro ul{color:#c9cdd8}.offre.pro li::before{color:#e0539f}
.offre.pro .etiquette{position:absolute;top:-12px;left:24px;background:#e0539f;color:#040e30;font:600 11px var(--mono);
  letter-spacing:.1em;text-transform:uppercase;padding:5px 9px;border-radius:6px;z-index:1}
.offre.pro{overflow:visible}
.offre .annuel{margin:8px 0 0;font-size:13.5px;color:#e0539f}
.offre.pro .btn-1{background:#e0539f;color:#040e30;box-shadow:none}
.btn-lien{background:transparent;color:inherit;text-decoration:underline;text-underline-offset:3px;font-weight:500;padding:12px 0 0;justify-content:center}
.libre-bande{margin:18px 0 0 164px;display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;
  border:1px dashed var(--line);border-radius:16px;padding:18px 22px}
.libre-bande b{display:block;font:600 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.libre-bande span{color:var(--ink);font-size:15px}

/* usages */
.usages-gain{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:0 0 34px 164px;border-top:1px solid var(--fg)}
.usages-gain div{padding:18px 24px 0 0}
.usages-gain b{display:block;font-family:var(--serif);font-weight:400;font-size:27px;line-height:1.1;margin-bottom:6px}
.usages-gain span{color:var(--ink);font-size:14.5px}
.usages{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-left:164px}
.usage{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:24px 22px 22px;display:flex;flex-direction:column;
  transition:transform .2s ease,box-shadow .2s ease,border-color .2s}
.usage:hover{transform:translateY(-3px);border-color:var(--accent);box-shadow:0 26px 50px -34px rgba(177,51,138,.55)}
.usage .qui{font:600 11.5px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
.usage h3{font-family:var(--serif);font-weight:400;font-size:26px;line-height:1.08;margin:0 0 16px}
.bulles{list-style:none;margin:0 0 16px;padding:0;display:grid;gap:8px}
.bulles li{position:relative;background:var(--bg);border:1px solid var(--line);border-radius:14px 14px 14px 4px;padding:9px 12px 9px 30px;
  font-size:14px;line-height:1.4;color:var(--fg)}
.bulles li::before{content:"«";position:absolute;left:11px;top:6px;font-family:var(--serif);font-size:20px;color:var(--accent)}
.usage .gain{margin-top:auto;padding-top:12px;border-top:1px dashed var(--line);font-size:14px;color:var(--ink)}
.usage .gain::before{content:"→ ";color:var(--accent);font-weight:600}
.phare{grid-column:1/-1;display:grid;grid-template-columns:1.1fr .9fr;gap:36px;align-items:center;background:var(--deep);color:#f7f8fb;
  border-radius:22px;padding:34px 34px;position:relative;overflow:hidden}
.phare::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(520px 260px at 92% 10%,rgba(224,83,159,.32),transparent 70%)}
.phare>*{position:relative}
.phare .qui{color:#e0539f}
.phare h3{font-family:var(--serif);font-weight:400;font-size:clamp(30px,3.4vw,42px);line-height:1.02;margin:0 0 12px}
.phare h3 em{color:#e0539f}
.phare p{color:#c9cdd8;margin:0 0 10px;font-size:15.5px}
.phare .terminal{margin:0}
.usages-cta{display:flex;gap:12px;flex-wrap:wrap;margin:26px 0 0 164px}
@media (max-width:900px){
  .usages,.usages-gain,.usages-cta{margin-left:0}
  .usages{grid-template-columns:1fr}.usages-gain{grid-template-columns:1fr;gap:4px}
  .phare{grid-template-columns:1fr;padding:26px 20px;gap:22px}
}
@media (min-width:901px) and (max-width:1100px){.usages{grid-template-columns:repeat(2,1fr)}}

/* installation */
.install{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-left:164px}
.install div{border-top:2px solid var(--fg);padding-top:16px}
.install h3{font:600 17px var(--sans);margin:0 0 10px}
.install ol{margin:0;padding-left:18px;color:var(--ink);font-size:15px}.install li{margin:5px 0}
.install pre{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:12px;font:12px/1.6 var(--mono);overflow-x:auto;margin:10px 0 0}

/* outils + faq */
.outils{margin-left:164px;columns:2;column-gap:36px}
.outils p{break-inside:avoid;margin:0 0 14px;font-size:15px;color:var(--ink)}
.outils code{display:block;color:var(--fg);font-weight:500;margin-bottom:2px}
.faq{margin-left:164px;border-top:1px solid var(--fg)}
details{border-bottom:1px solid var(--line);padding:18px 0}
summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:16px;font:600 17px var(--sans)}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";font-family:var(--serif);font-size:28px;line-height:.8;color:var(--accent);transition:transform .2s}
details[open] summary::after{transform:rotate(45deg)}
details p{margin:10px 0 0;color:var(--ink);max-width:760px}
.note{margin:28px 0 0 164px;border-left:3px solid var(--accent);padding:14px 18px;background:var(--paper);border-radius:0 12px 12px 0;font-size:15px;color:var(--ink)}

/* studjoow */
.studio{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:0;margin-left:164px;border-top:1px solid var(--fg)}
.studio>div{padding:22px 28px 0 0}
.studio b{display:block;font:500 12px var(--mono);color:var(--accent);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px}
.studio p{margin:0 0 14px;color:var(--ink);font-size:15px}
.studio-projets a{display:block;font:600 16px var(--sans);color:var(--fg);text-decoration:none;margin-bottom:2px}
.studio-projets a:hover{color:var(--accent)}
.studio-contact{display:flex;flex-direction:column;align-items:flex-start}
.studio-contact .btn-lien{padding-top:12px}
@media (max-width:900px){.studio{grid-template-columns:1fr;margin-left:0}.studio>div{padding-right:0}}

footer{margin-top:110px;border-top:1px solid var(--fg);padding:34px 0 60px;font-size:13.5px;color:var(--muted)}
footer .wrap{display:grid;grid-template-columns:1.2fr 1fr;gap:30px}
footer a{color:var(--ink)}
footer .marque{color:var(--muted);font-size:13.5px}footer .logo-sj{height:22px}

@media (max-width:900px){
  .hero{grid-template-columns:1fr;gap:40px;padding-top:20px}.fiche{transform:none}
  .nav{display:none}
  .chiffres{grid-template-columns:repeat(2,1fr)}.chiffres div:nth-child(3){border-left:0;padding-left:0}
  .chiffres div:nth-child(n+3){border-top:1px solid var(--line)}
  .titre{grid-template-columns:1fr;gap:6px}.titre p{grid-column:1}.titre .num{font-size:40px}
  .etapes,.sources,.tarifs,.install,.outils,.faq,.note,.libre-bande{margin-left:0}
  .etapes,.tarifs,.install{grid-template-columns:1fr;gap:18px}
  .sources div{grid-template-columns:90px 1fr}.sources span{grid-column:2}
  .outils{columns:1}.bande .wrap{grid-template-columns:1fr;gap:32px}
  footer .wrap{grid-template-columns:1fr}
}
@media (max-width:480px){.wrap{padding:0 16px}h1{font-size:44px}.url code{font-size:13px}.fiche{padding:20px 16px}
  .q,.r,.refs,.fiche-tete{padding-left:30px}.fiche .marge{left:38px}.q{font-size:21px}}
"""


def _boutons_abonnement(classe="btn btn-1", offre="particulier", texte=None):
    if LIEN_ABONNEMENT:
        lien = LIEN_ABONNEMENT + ("" if offre == "particulier" or "?" in LIEN_ABONNEMENT else "?offre=" + offre)
        return '<a class="%s" href="%s" rel="nofollow">%s</a>' % (
            classe, html.escape(lien), html.escape(texte or "S'abonner pour %s € / mois" % PRIX))
    return '<span class="%s" aria-disabled="true">Abonnement : ouverture prochaine</span>' % classe


def render(etat_fn):
    r = resume(etat_fn)
    e = html.escape
    etat = ('<span class="pt ok"></span>en service · bases du %s' % (r["maj"] or "jour")
            if r["pret"] else '<span class="pt"></span>bases en cours de chargement')
    chiffres = ""
    if r["pret"]:
        items = [(r["articles"], "articles de codes, lois, JO et conventions"),
                 (r["decisions"], "décisions de justice")]
        if r["ue"]:
            items.append((r["ue"], "textes et arrêts de l'UE"))
        items.append((len(OUTILS), "outils à disposition de l'assistant"))
        chiffres = '<div class="wrap"><div class="chiffres">%s</div></div>' % "".join(
            "<div><b>%s</b><span>%s</span></div>" % (nombre(n), lab) for n, lab in items[:4])
    sources = "".join('<div><code>%s</code><b>%s</b><span>%s</span></div>' % (e(c), e(t), e(d)) for c, t, d in SOURCES)
    outils = "".join("<p><code>%s</code>%s</p>" % (e(n), e(d)) for n, d in OUTILS)
    usages = "".join(
        '<article class="usage"><p class="qui">%s</p><h3>%s</h3><ul class="bulles">%s</ul><p class="gain">%s</p></article>'
        % (e(qui), insec(e(titre)), "".join("<li>%s</li>" % insec(e(q)) for q in qs), insec(e(gain))) for qui, titre, qs, gain in USAGES)
    faq = "".join("<details><summary>%s</summary><p>%s</p></details>" % (e(q), e(a)) for q, a in FAQ)
    projets = "".join('<p><a href="%s">%s</a>%s</p>' % (e(u), e(n), e(d)) for n, u, d in AUTRES_PROJETS)
    v = {
        "pied": PIED,
        "titre": e(TITRE), "desc": e(DESCRIPTION), "site": SITE, "ld": json_ld().replace("</", "<\\/"),
        "fonts": FONTS, "css": CSS, "etat": etat, "chiffres": chiffres, "sources": sources, "outils": outils,
        "faq": faq, "projets": projets, "usages": usages, "plafond": nombre(PLAFOND), "repo": REPO, "logo": LOGO_STUDJOOW, "prix": PRIX, "essai": str(ESSAI_PAR_JOUR),
        "abonner": _boutons_abonnement(), "abonner2": _boutons_abonnement("btn btn-1"),
        "abonner_pro": _boutons_abonnement("btn btn-1", "pro", "Choisir Pro mensuel"),
        "abonner_pro_an": _boutons_abonnement("btn btn-lien", "pro-an", "Payer à l'année : %s €" % PRIX_PRO_AN),
        "prix_pro": PRIX_PRO, "prix_pro_an": PRIX_PRO_AN, "plafond_pro": nombre(PLAFOND_PRO),
        "ia_part": os.environ.get("DROIT_IA_PAR_MOIS", "5"), "ia_pro": os.environ.get("DROIT_IA_PAR_MOIS_PRO", "100"),
    }
    page = PAGE
    for k, val in v.items():
        page = page.replace("{{%s}}" % k, val)
    return page


PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{titre}}</title>
<meta name="description" content="{{desc}}">
<link rel="canonical" href="{{site}}/">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta name="theme-color" content="#b1338a">
<meta name="author" content="Studjoow">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/static/icones/icone-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/static/fonts/instrument-serif-normal-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/static/fonts/plus-jakarta-sans-normal-400-700.woff2" as="font" type="font/woff2" crossorigin>
<link rel="alternate" type="text/plain" href="/llms.txt" title="llms.txt">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Droit français sourcé">
<meta property="og:title" content="{{titre}}">
<meta property="og:description" content="{{desc}}">
<meta property="og:url" content="{{site}}/">
<meta property="og:image" content="{{site}}/og.png">
<meta property="og:image:width" content="1280">
<meta property="og:image:height" content="640">
<meta property="og:image:alt" content="Le droit français officiel, sourcé, dans Claude et ChatGPT. Un projet Studjoow.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{{site}}/og.png">
<script type="application/ld+json">{{ld}}</script>
<style>{{fonts}}{{css}}</style>
</head>
<body>
<div class="wrap">
<header class="bar">
<a href="https://studjoow.com" class="marque"><span>Un projet</span>{{logo}}</a>
<nav class="nav" aria-label="Sections"><a href="#usages">Usages</a><a href="#methode">Méthode</a><a href="#sources">Sources</a><a href="#tarifs">Tarifs</a><a href="#studjoow">Studjoow</a><a href="#faq">FAQ</a></nav>
<span class="etat">{{etat}}</span>
</header>

<main>
<div class="hero">
<div class="hero-txt">
<p class="eyebrow">Serveur MCP · droit français et européen</p>
<h1>Le droit,<br><em>cité à la source.</em></h1>
<p class="lead">Branchez Claude ou ChatGPT sur les textes officiels : codes, lois, Journal officiel, conventions collectives, jurisprudence et EUR-Lex. Chaque affirmation arrive avec son article, son identifiant Légifrance et sa date de version. Et chaque référence est vérifiée avant d'être citée.</p>
<div class="url"><code id="u">{{site}}/mcp</code><button type="button" class="btn btn-1" onclick="navigator.clipboard.writeText(document.getElementById('u').textContent).then(()=>{this.textContent='Copié'})">Copier l'adresse</button></div>
<div class="ctas"><a class="btn btn-2" href="#installer">Essayer gratuitement</a>{{abonner}}</div>
</div>

<div class="fiche" aria-label="Exemple de réponse sourcée">
<span class="marge"></span>
<div class="fiche-tete"><span>dossier n° 1240</span><span>droit.studjoow.com</span></div>
<p class="q anim">Mon voisin a abîmé ma clôture. Sur quoi fonder une demande ?</p>
<p class="r anim">Sur la responsabilité pour faute : « tout fait quelconque de l'homme, qui cause à autrui un dommage, oblige celui par la faute duquel il est arrivé à le réparer » <cite>C. civ., art. 1240</cite>.</p>
<ul class="refs">
<li class="anim"><span>Code civil, art. 1240 · LEGIARTI000032041571</span><span class="tampon ok">Vérifié</span></li>
<li class="anim"><span>version du 01/10/2016 à ce jour</span><span class="tampon ok">En vigueur</span></li>
<li class="anim faux"><span>Code civil, art. 1240-1</span><span class="tampon ko">Introuvable</span></li>
</ul>
</div>
</div>
</main>
</div>

{{chiffres}}

<div class="wrap">
<section id="usages">
<div class="titre"><span class="num">§ 1</span><div><h2>Ce que vous pouvez<br>en faire.</h2></div><p>Posez votre question à Claude ou ChatGPT comme d'habitude. La différence : la réponse s'appuie sur le texte officiel, à la bonne date, et chaque référence est vérifiée avant d'arriver jusqu'à vous.</p></div>
<div class="usages-gain">
<div><b>Moins d'erreurs.</b><span>Une référence introuvable est signalée au lieu d'être inventée.</span></div>
<div><b>Du temps gagné.</b><span>L'article, la jurisprudence et les liens, sans fouiller Légifrance.</span></div>
<div><b>Des sources à montrer.</b><span>Chaque affirmation arrive avec son identifiant officiel.</span></div>
</div>
<div class="usages">
{{usages}}
<div class="phare">
<div><p class="qui mono">Le contrôle avant envoi</p><h3>Un contrat, des conclusions, une note rédigés par une IA ?<br><em>Vérifiez avant d'envoyer.</em></h3><p>Collez le texte dans la conversation : chaque article et chaque arrêt cités sont recherchés dans la base officielle, chaque citation comparée mot pour mot. Ce qui n'existe pas est signalé.</p></div>
<div class="terminal" role="img" aria-label="Exemple de contrôle d'un texte avant envoi">
<div><span class="p">verifier_references</span> <span class="d">4 références du projet de contrat</span></div>
<div><span class="ok">[OK]</span> Code civil, art. 1231-5 (clause pénale)</div>
<div><span class="p">[ATTENTION]</span> Code de commerce, art. L441-10 : abrogé au 01/01/2027</div>
<div><span class="ok">[OK]</span> RGPD, art. 28 (sous-traitant)</div>
<div><span class="ko">[INTROUVABLE]</span> Cass. com., n° 21-99.999</div>
<div class="d">     → 1 à corriger, 1 à mettre à jour avant envoi</div>
</div>
</div>
</div>
<div class="usages-cta"><a class="btn btn-1" href="#installer">Essayer gratuitement</a><a class="btn btn-2" href="/conformite">Analyser mon projet</a><a class="btn btn-2" href="#tarifs">Voir les tarifs</a></div>
</section>

<section id="methode">
<div class="titre"><span class="num">§ 2</span><div><h2>Chercher, citer, vérifier.</h2></div><p>Le serveur impose une méthode à l'assistant. Il ne répond jamais de mémoire : il lit les textes, puis prouve ce qu'il avance.</p></div>
<div class="etapes">
<div><b>01 · CHERCHER</b><h3>Dans les textes officiels</h3><p>Recherche plein texte dans 5 millions d'articles et 1,2 million de décisions, à la date des faits.</p></div>
<div><b>02 · CITER</b><h3>Après chaque affirmation</h3><p>Article, numéro de pourvoi ou CELEX, lien Légifrance ou EUR-Lex et version utilisée, puis un bloc « Sources ».</p></div>
<div><b>03 · VÉRIFIER</b><h3>Avant d'écrire</h3><p>Chaque référence est contrôlée : introuvable ou citation absente du texte, elle est signalée au lieu d'être inventée.</p></div>
</div>
</section>

<section id="sources">
<div class="titre"><span class="num">§ 3</span><div><h2>Les sources officielles,<br>mises à jour chaque nuit.</h2></div><p>Données ouvertes de la DILA (Légifrance) et de l'Office des publications de l'Union européenne, rechargées automatiquement tous les jours.</p></div>
<div class="sources">{{sources}}</div>
</section>
</div>

<div class="bande" id="verification">
<div class="wrap">
<div>
<h2>Une référence fausse<br><em>ne passe pas.</em></h2>
<p>Les assistants inventent parfois des articles ou des arrêts. Ici, l'outil <code>verifier_references</code> contrôle chaque référence dans la base et chaque citation mot pour mot.</p>
<p>Ce qui n'existe pas est marqué introuvable. L'assistant doit le corriger ou le retirer.</p>
</div>
<div class="terminal" role="img" aria-label="Exemple de vérification de références">
<div><span class="p">verifier_references</span> <span class="d">« Code civil 1240 », « RGPD art. 17 », « Cass. 99-99.999 »</span></div>
<div><span class="ok">[OK]</span> Code civil, art. 1240 (version du 2016-10-01 à ce jour, VIGUEUR)</div>
<div class="d">     LEGIARTI000032041571 · legifrance.gouv.fr</div>
<div><span class="ok">[OK]</span> RGPD, art. 17, Droit à l'effacement (« droit à l'oubli »)</div>
<div class="d">     CELEX 32016R0679 · eur-lex.europa.eu</div>
<div><span class="ko">[INTROUVABLE]</span> Cass. 99-99.999 : ne pas citer cette référence</div>
</div>
</div>
</div>

<div class="wrap">
<section id="tarifs">
<div class="titre"><span class="num">§ 4</span><div><h2>Le code est libre.<br>L'hébergement, clé en main.</h2></div><p>Le logiciel est sous licence MIT : chacun peut l'héberger gratuitement. L'abonnement paie le serveur, les 33 Go de bases indexées et leur mise à jour quotidienne.</p></div>
<div class="tarifs">
<div class="offre"><h3>Essai</h3><p class="prix">0 €</p><ul><li>{{essai}} requêtes par jour</li><li>Sans inscription</li><li>Toutes les sources et les 12 outils</li></ul><a class="btn btn-2" href="#installer">Ajouter l'adresse publique</a></div>
<div class="offre vedette"><span class="etiquette">Le plus simple</span><h3>Particulier</h3><p class="prix">{{prix}} €<small>/ mois</small></p><ul><li>{{plafond}} requêtes par jour</li><li>Adresse personnelle pour Claude et ChatGPT</li><li>Bases mises à jour chaque nuit</li><li>{{ia_part}} analyses de conformité par mois</li><li>Sans engagement, résiliable à tout moment</li></ul>{{abonner2}}</div>
<div class="offre pro"><span class="etiquette">Professionnels</span><h3>Pro</h3><p class="prix">{{prix_pro}} €<small>/ mois</small></p><p class="annuel">ou {{prix_pro_an}} € par an, deux mois offerts</p><ul><li>{{plafond_pro}} requêtes par jour</li><li>Facture au nom de votre entreprise</li><li>{{ia_pro}} analyses de conformité par mois</li><li>Usage professionnel autorisé</li><li>Support prioritaire par e-mail</li></ul>{{abonner_pro}}{{abonner_pro_an}}</div>
</div>
<div class="libre-bande"><div><b>Auto-hébergé · 0 €</b><span>Code libre sous licence MIT : votre serveur, vos bases, environ 70 Go de disque.</span></div><a class="btn btn-2" href="{{repo}}">Voir sur GitHub</a></div>
</section>

<section id="installer">
<div class="titre"><span class="num">§ 5</span><div><h2>Installer en 30 secondes.</h2></div><p>Une adresse à coller, rien à télécharger. Abonné ? Utilisez <code>{{site}}/abonne/mcp</code> et cliquez sur « Se connecter » : votre e-mail et un code suffisent.</p></div>
<div class="install">
<div><h3>Claude</h3><ol><li>Paramètres, puis <b>Connecteurs</b></li><li><b>Ajouter un connecteur personnalisé</b></li><li>URL : <code>{{site}}/mcp</code></li><li>Demander : « Que dit l'article 1240 du Code civil ? »</li></ol></div>
<div><h3>ChatGPT</h3><ol><li>Paramètres, puis <b>Applications et connecteurs</b></li><li>Selon l'offre, activer le <b>mode développeur</b></li><li><b>Créer</b> un connecteur, URL ci-dessus (sans authentification pour l'essai, OAuth pour l'abonnement)</li><li>Le choisir dans le menu des outils</li></ol></div>
<div><h3>Claude Code, Cursor, VS Code</h3><pre>claude mcp add --transport http \\
  droit-francais {{site}}/mcp</pre><pre>{"mcpServers":{"droit-francais":
 {"type":"http","url":"{{site}}/mcp"}}}</pre></div>
</div>
</section>

<section id="outils">
<div class="titre"><span class="num">§ 6</span><div><h2>Douze outils pour l'assistant.</h2></div></div>
<div class="outils">{{outils}}</div>
</section>

<section id="studjoow">
<div class="titre"><span class="num">§ 7</span><div><h2>Derrière l'outil,<br>un studio.</h2></div><p>Droit by Studjoow est conçu, hébergé et maintenu par Studjoow, le studio créatif et tech de John Houzi. Un studio à une personne, en activité depuis 2007 : sites sur mesure, identité visuelle, intégrations IA, SEO et GEO. Un seul interlocuteur, du cadrage à la mise en ligne.</p></div>
<div class="studio">
<div class="studio-pourquoi"><b>Pourquoi cet outil</b><p>Les assistants citent parfois des articles qui n'existent pas. Studjoow a construit ce serveur pour que chaque réponse parte du texte officiel et que chaque référence soit contrôlée, puis l'a ouvert à tous, code compris.</p></div>
<div class="studio-projets"><b>Les autres projets</b>{{projets}}</div>
<div class="studio-contact"><b>Travailler avec Studjoow</b><p>Un site, une marque ou un outil d'IA branché sur vos propres données ?</p><a class="btn btn-1" href="https://studjoow.com">Découvrir Studjoow</a><a class="btn btn-lien" href="mailto:hello@studjoow.com">hello@studjoow.com</a></div>
</div>
</section>

<section id="faq">
<div class="titre"><span class="num">§ 8</span><div><h2>Questions fréquentes.</h2></div></div>
<div class="faq">{{faq}}</div>
<p class="note"><b>Information juridique, pas conseil.</b> La version qui fait foi est celle de <a href="https://www.legifrance.gouv.fr">Légifrance</a> ou d'<a href="https://eur-lex.europa.eu">EUR-Lex</a>. Jurisprudence non exhaustive : seules les décisions diffusées en open data y figurent (cours d'appel jusqu'à fin 2023). Pour un cas concret, consultez un avocat.</p>
</section>
</div>

{{pied}}
</body>
</html>"""


def robots():
    return "User-agent: *\nAllow: /\nDisallow: /mcp\nDisallow: /admin\nDisallow: /compte\nDisallow: /merci\nDisallow: /abonnement\n\nSitemap: %s/sitemap.xml\n" % SITE


def sitemap():
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>%s/</loc><changefreq>daily</changefreq></url>"
            "<url><loc>%s/llms.txt</loc><changefreq>weekly</changefreq></url>"
            "<url><loc>%s/conformite</loc><changefreq>monthly</changefreq></url>"
            "<url><loc>%s/cgv</loc><changefreq>monthly</changefreq></url>"
            "<url><loc>%s/mentions-legales</loc><changefreq>yearly</changefreq></url>"
            "<url><loc>%s/confidentialite</loc><changefreq>yearly</changefreq></url></urlset>\n" % ((SITE,) * 6))


def llms(etat_fn):
    r = resume(etat_fn)
    lignes = [
        "# Droit français sourcé (serveur MCP)",
        "",
        "> " + DESCRIPTION,
        "",
        "Adresse publique du serveur MCP (Streamable HTTP, sans authentification) : %s/mcp" % SITE,
        "Essai gratuit : %d appels d'outils par jour et par IP sur l'adresse publique." % ESSAI_PAR_JOUR,
        "Abonnement : %s € par mois, sans engagement, %d requêtes par jour : %s/abonnement" % (PRIX, PLAFOND, SITE),
        "Abonnés : connecteur %s/abonne/mcp avec connexion OAuth 2.1 (e-mail + code), ou adresse personnelle %s/mcp/<clé> pour les clients sans OAuth." % (SITE, SITE),
        "Offre Pro : %s € par mois ou %s € par an, %d requêtes par jour, facture au nom de l'entreprise : %s/abonnement?offre=pro" % (PRIX_PRO, PRIX_PRO_AN, PLAFOND_PRO, SITE),
        "Auto-hébergement : gratuit, code sous licence MIT (%s)." % REPO,
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
        "- Conditions générales de vente : %s/cgv" % SITE,
        "- Conçu et maintenu par Studjoow, studio créatif et tech : https://studjoow.com",
        "",
        "## Qui est derrière",
        "Studjoow, le studio créatif et tech de John Houzi, en activité depuis 2007 : sites sur mesure, identité visuelle, "
        "intégrations IA, SEO et GEO. Contact : hello@studjoow.com.",
    ] + ["- %s (%s) : %s" % (n, u, d) for n, u, d in AUTRES_PROJETS] + [
        "",
    ]
    return "\n".join(lignes)


EDITEUR = ("John Houzi, nom commercial Studjoow, travailleur indépendant agréé en Israël (Ossek Mourshé), "
           "Tax ID 337927834, 49 Abarbanel, Tel Aviv 6608912, Israël")
CONTACT = "hello@studjoow.com"
MEDIATEUR = os.environ.get("DROIT_MEDIATEUR", "").strip()

CSS_DOC = """
.doc{max-width:760px;margin:24px 0 0}
.doc h1{font-size:clamp(40px,6vw,64px);margin:0 0 18px}
.doc h2{font-family:var(--serif);font-weight:400;font-size:30px;line-height:1.1;margin:44px 0 12px}
.doc h3{font:600 17px var(--sans);margin:26px 0 8px}
.doc p,.doc li{color:var(--ink)}.doc ul,.doc ol{padding-left:20px}
.doc .maj{font:12.5px var(--mono);color:var(--muted)}
.carte{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:28px 26px;margin:22px 0;max-width:640px}
.carte h2{margin-top:0}
.coche{display:flex;gap:12px;align-items:flex-start;margin:14px 0;font-size:15px;color:var(--ink)}
.coche input{margin-top:4px;width:18px;height:18px;accent-color:var(--accent);flex:none}
.champ{width:100%;font:15px var(--mono);padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg)}
.alerte{border-left:3px solid var(--ko);background:var(--paper);padding:12px 16px;border-radius:0 10px 10px 0;margin:14px 0}
.info{border-left:3px solid var(--ok);background:var(--paper);padding:12px 16px;border-radius:0 10px 10px 0;margin:14px 0}
.statut{font:600 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;padding:4px 8px;border-radius:6px;border:1.5px solid currentColor}
.statut.actif{color:var(--ok)}.statut.suspendu{color:#f99c00}.statut.revoque{color:var(--ko)}
dl.fiche-compte{display:grid;grid-template-columns:170px 1fr;gap:8px 16px;margin:18px 0;font-size:15px}
dl.fiche-compte dt{color:var(--muted)}dl.fiche-compte dd{margin:0}
.choix-offres{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 0}
.choix{font:500 13.5px var(--sans);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:8px 14px;color:var(--ink);background:var(--paper)}
.choix.actif{border-color:var(--accent);color:var(--accent);font-weight:600}
form.ligne{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}form.ligne .champ{flex:1;min-width:220px}
@media (max-width:480px){dl.fiche-compte{grid-template-columns:1fr}}
"""

PIED = """<footer>
<div class="wrap">
<div><a href="https://studjoow.com" class="marque"><span>Conçu et maintenu par</span>{{logo}}</a><p>Studio créatif et tech : sites sur mesure, branding, IA, SEO et GEO.</p></div>
<div><p>Données : DILA, Légifrance open data, sous <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/">Licence Ouverte 2.0</a> ; EUR-Lex, Office des publications de l'Union européenne. Service ni édité ni approuvé par la DILA, Légifrance ou l'Union européenne. Information juridique, pas conseil.</p><p><a href="/mentions-legales">Mentions légales</a> · <a href="/cgv">CGV</a> · <a href="/confidentialite">Confidentialité</a> · <a href="/compte">Mon compte</a></p><p>Code libre (MIT) : <a href="{{repo}}">GitHub</a> · État : <a href="/health">/health</a> · <a href="/llms.txt">llms.txt</a></p></div>
</div>
</footer>"""


def gabarit(titre, contenu, description="", indexer=True):
    e = html.escape
    page = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · Droit français sourcé</title>
<meta name="description" content="%s">
<meta name="robots" content="%s">
<meta name="theme-color" content="#b1338a">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/static/icones/icone-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/static/fonts/instrument-serif-normal-400.woff2" as="font" type="font/woff2" crossorigin>
<style>%s%s%s</style>
</head>
<body>
<div class="wrap">
<header class="bar">
<a href="/" class="marque"><span>Droit français sourcé · un projet</span>{{logo}}</a>
<nav class="nav" aria-label="Pages"><a href="/#tarifs">Tarifs</a><a href="/#installer">Installer</a><a href="/compte">Mon compte</a></nav>
</header>
<main class="doc">%s</main>
</div>
%s
</body>
</html>""" % (e(titre), e(description or titre), "index,follow" if indexer else "noindex,nofollow",
              FONTS, CSS, CSS_DOC, contenu, PIED)
    return page.replace("{{logo}}", LOGO_STUDJOOW).replace("{{repo}}", REPO)


def page_ferme():
    return gabarit("Abonnement bientôt ouvert", "<h1>Bientôt.</h1><p>L'abonnement ouvre prochainement. "
                   "En attendant, l'essai gratuit reste disponible sur l'adresse publique <code>%s/mcp</code>.</p>"
                   '<p><a class="btn btn-2" href="/">Retour à l\'accueil</a></p>' % SITE, indexer=False)


def page_abonnement(erreur=None, offre="particulier"):
    nom, prix, periode, plafond = OFFRES_PAGE.get(offre, OFFRES_PAGE["particulier"])
    alerte = '<p class="alerte">%s</p>' % html.escape(erreur) if erreur else ""
    pro = offre != "particulier"
    avantages = ("<li>%s requêtes par jour par adresse personnelle (et 60 par minute au plus)</li>" % nombre(plafond)
                 + ("<li>Facture au nom de votre entreprise : raison sociale et numéro de TVA demandés au paiement</li>"
                    "<li>Support prioritaire par e-mail</li>" if pro else "")
                 + "<li>Toutes les sources, les 12 outils, bases mises à jour chaque nuit</li>"
                 + "<li>Sans engagement : résiliable à tout moment depuis votre compte, effet à la fin de la période payée</li>")
    choix = "".join(
        '<a class="choix%s" href="/abonnement?offre=%s">%s · %s €/%s</a>' % (" actif" if k == offre else "", k, n, p, per)
        for k, (n, p, per, _) in OFFRES_PAGE.items())
    return gabarit("S'abonner", """<h1>S'abonner.</h1>
<p>Accès au droit français et européen officiel, dans Claude, ChatGPT et tout assistant compatible MCP.</p>
<nav class="choix-offres" aria-label="Offres">%s</nav>
<div class="carte">
<p class="mini">Offre %s</p>
<p class="prix">%s €<small>/ %s</small></p>
<ul>%s</ul>
%s
<form method="post" action="/abonnement?offre=%s">
<input type="hidden" name="offre" value="%s">
<label class="coche"><input type="checkbox" name="cgv" value="1" required><span>J'accepte les <a href="/cgv" target="_blank">conditions générales de vente</a> et j'ai lu la <a href="/confidentialite" target="_blank">politique de confidentialité</a>.</span></label>
<label class="coche"><input type="checkbox" name="execution" value="1" required><span>Je veux utiliser le service tout de suite. Si je change d'avis dans les 14 jours, je suis remboursé, moins les jours déjà utilisés (art. L221-25 du Code de la consommation).</span></label>
<p><button class="btn btn-1" type="submit">Payer %s € et recevoir mon adresse</button></p>
<p class="mini">Paiement sécurisé par Stripe. Vos coordonnées bancaires ne transitent jamais par nos serveurs.</p>
</form>
</div>
<p class="mini">Déjà abonné ? <a href="/compte">Gérer mon abonnement</a>. Le code reste libre : <a href="%s">héberger son propre serveur</a> est gratuit.</p>
""" % (choix, html.escape(nom), prix, periode, avantages, alerte, offre, offre, prix, REPO),
        "Abonnement %s à %s € par %s au serveur MCP Droit français sourcé." % (nom, prix, periode), indexer=False)


def _copier(url):
    e = html.escape(url)
    return ('<div class="url"><code id="u">%s</code><button type="button" class="btn btn-1" '
            "onclick=\"navigator.clipboard.writeText(document.getElementById('u').textContent).then(()=>{this.textContent='Copié'})\">"
            "Copier</button></div>" % e)


INSTALLER = """<h2>L'installer avec votre compte</h2>
<ol><li><b>Claude</b> : Paramètres, puis Connecteurs, puis <b>Ajouter un connecteur personnalisé</b>. Adresse : <code>%s/abonne/mcp</code>, puis <b>Se connecter</b> : saisissez votre e-mail et le code reçu.</li>
<li><b>ChatGPT</b> : Paramètres, puis Applications et connecteurs, <b>Créer</b> un connecteur avec la même adresse, authentification OAuth.</li>
<li><b>Sans connexion</b> (Claude Code, Cursor, anciens clients) : collez plutôt votre adresse personnelle, ci-dessus.</li></ol>
<p>Si vous utilisiez l'adresse publique de l'essai, remplacez-la.</p>""" % SITE


def page_merci(url, message=None, email=None, envoye=False):
    if not url:
        return gabarit("Abonnement", "<h1>Abonnement.</h1><p class=\"info\">%s</p>"
                       '<p><a class="btn btn-1" href="/compte">Mon compte</a></p>' % html.escape(message or ""), indexer=False)
    courriel = ("<p>Une copie vient d'être envoyée à <b>%s</b>.</p>" % html.escape(email)) if envoye and email else \
        "<p>Copiez-la maintenant : elle ne sera plus affichée sur cette page.</p>"
    return gabarit("Merci", """<h1>Merci.</h1>
<p>Votre abonnement est actif. Le plus simple : ajoutez le connecteur <code>%s/abonne/mcp</code> et connectez-vous avec votre e-mail (voir plus bas). Pour les clients sans connexion, voici aussi votre adresse personnelle :</p>
%s
<p class="alerte"><b>Affichée une seule fois.</b> Gardez-la pour vous : elle donne accès à votre abonnement. En cas de doute, régénérez-la depuis <a href="/compte">votre compte</a>.</p>
%s
%s
<p class="mini">Gérer ou résilier à tout moment : <a href="/compte">Mon compte</a>. Information juridique, pas conseil.</p>
""" % (SITE, _copier(url), courriel, INSTALLER), indexer=False)


def page_compte(erreur=None, info=None):
    bloc = ('<p class="alerte">%s</p>' % html.escape(erreur)) if erreur else ('<p class="info">%s</p>' % html.escape(info) if info else "")
    return gabarit("Mon compte", """<h1>Mon compte.</h1>
%s
<div class="carte"><h2>J'ai mon adresse personnelle</h2>
<p>Collez-la pour voir l'état de l'abonnement, le gérer, le résilier ou régénérer l'adresse.</p>
<form class="ligne" method="post" action="/compte"><input class="champ" name="adresse" placeholder="%s/mcp/..." autocomplete="off" required><button class="btn btn-1" type="submit">Ouvrir</button></form></div>
<div class="carte"><h2>J'ai perdu mon adresse</h2>
<p>Indiquez l'e-mail utilisé au paiement : vous recevrez un lien d'accès valable une heure.</p>
<form class="ligne" method="post" action="/compte/lien"><input class="champ" type="email" name="email" placeholder="vous@exemple.fr" autocomplete="email" required><button class="btn btn-2" type="submit">Recevoir un lien</button></form></div>
<p class="mini">Pas encore abonné ? <a href="/abonnement">S'abonner pour %s € / mois</a>.</p>
""" % (bloc, SITE, PRIX), indexer=False)


def _date_fr(s):
    return "%s/%s/%s" % (s[8:10], s[5:7], s[:4]) if s else "inconnue"


def _offre_ligne(row):
    try:
        cle = row["offre"] or "particulier"
    except (IndexError, KeyError):
        cle = "particulier"
    nom, prix, periode, plafond = OFFRES_PAGE.get(cle, OFFRES_PAGE["particulier"])
    return "%s · %s € par %s · %s requêtes par jour" % (nom, prix, periode, nombre(plafond))


def page_gestion(row, url, nouvelle=False, info=None):
    e = html.escape
    libelles = {"actif": "Actif", "suspendu": "Suspendu (paiement en échec)", "revoque": "Terminé"}
    fin = ("Résiliation prévue le %s" if row["resiliation_prevue"] else "Prochain prélèvement le %s") % _date_fr(row["fin_periode"])
    if row["statut"] == "revoque":
        fin = "Terminé le %s" % _date_fr(row["maj_le"])
    email = row["email"] or ""
    if "@" in email:
        nom, dom = email.split("@", 1)
        email = nom[:2] + "•" * max(len(nom) - 2, 1) + "@" + dom
    cache = '<input type="hidden" name="adresse" value="%s">' % e(url)
    import oauth
    lignes = oauth.assistants_connectes(row["abonnement"])
    assistants = ("<ul>%s</ul>" % "".join("<li><b>%s</b> · connecté le %s</li>" % (e(l["nom"]), _date_fr(l["dernier"])) for l in lignes)
                  if lignes else '<p class="mini">Aucun assistant connecté par « Se connecter ». Ajoutez le connecteur %s/abonne/mcp dans Claude ou ChatGPT.</p>' % SITE)
    if info:
        assistants = '<p class="info">%s</p>' % e(info) + assistants
    adresse_html = (_copier(url) + '<p class="info">Nouvelle adresse créée : l\'ancienne ne fonctionne plus. Remplacez-la dans vos connecteurs.</p>') if nouvelle else \
        '<p class="mini">Adresse personnelle : <code>%s/mcp/%s…</code></p>' % (SITE, e(url.rsplit("/", 1)[1][:6]))
    return gabarit("Mon abonnement", """<h1>Mon abonnement.</h1>
<div class="carte">
<p><span class="statut %s">%s</span></p>
<dl class="fiche-compte"><dt>Offre</dt><dd>%s</dd><dt>E-mail</dt><dd>%s</dd><dt>Échéance</dt><dd>%s</dd><dt>Abonné depuis</dt><dd>%s</dd></dl>
%s
<form class="ligne" method="post" action="/compte/portail">%s<button class="btn btn-1" type="submit">Gérer le paiement ou résilier</button></form>
<form class="ligne" method="post" action="/compte/regenerer" onsubmit="return confirm('L\\'adresse actuelle cessera de fonctionner. Continuer ?')">%s<button class="btn btn-2" type="submit">Régénérer mon adresse</button></form>
<p class="mini">La gestion du paiement, des factures et la résiliation se font sur le portail sécurisé de Stripe. Une résiliation prend effet à la fin de la période payée.</p>
</div>
<div class="carte"><h2>Assistants connectés</h2>%s
<form class="ligne" method="post" action="/compte/deconnecter">%s<button class="btn btn-2" type="submit">Déconnecter tous mes assistants</button></form></div>
%s""" % (e(row["statut"]), libelles.get(row["statut"], row["statut"]), e(_offre_ligne(row)), e(email), fin, _date_fr(row["cree_le"]),
         adresse_html, cache, cache, assistants, cache, INSTALLER if nouvelle else ""), indexer=False)


def cgv():
    mediation = ("<p>Conformément aux articles L611-1 et suivants du Code de la consommation, le consommateur peut recourir "
                 "gratuitement au médiateur de la consommation : %s.</p>" % html.escape(MEDIATEUR)) if MEDIATEUR else ""
    return gabarit("Conditions générales de vente", """<h1>Conditions générales de vente.</h1>
<p class="maj">En vigueur au 22 octobre 2026</p>
<h2>1. Objet et prestataire</h2>
<p>Les présentes conditions régissent l'abonnement au service « Droit français sourcé », accessible sur %(site)s, fourni par %(editeur)s (ci-après « Studjoow »). Contact : <a href="mailto:%(contact)s">%(contact)s</a>.</p>
<h2>2. Le service</h2>
<p>Le service est un serveur MCP (Model Context Protocol) qui donne à un assistant d'intelligence artificielle compatible un accès en lecture aux données ouvertes du droit français (DILA, Légifrance) et du droit de l'Union européenne (EUR-Lex). Il fournit de l'<b>information juridique, pas un conseil</b> : les réponses formulées par l'assistant relèvent de cet assistant, la version qui fait foi est celle publiée sur Légifrance ou EUR-Lex, et la jurisprudence disponible n'est pas exhaustive. Pour un cas concret, consultez un avocat.</p>
<p>Le logiciel est libre (licence MIT) : chacun peut l'héberger gratuitement. L'abonnement rémunère l'hébergement, les bases indexées, leur mise à jour quotidienne et la maintenance.</p>
<p>Les abonnés disposent aussi d'une analyse de conformité en ligne (5 par mois en Particulier, 100 en Pro) : une pré-analyse générée par une intelligence artificielle à partir des textes officiels, qui ne constitue ni un avis juridique ni une certification de conformité.</p>
<h2>3. Essai gratuit</h2>
<p>L'adresse publique %(site)s/mcp est utilisable sans inscription dans la limite de %(essai)s appels d'outils par jour et par adresse IP. Cette limite peut évoluer.</p>
<h2>4. Prix et paiement</h2>
<p>Trois formules, prix nets : <b>Particulier, %(prix)s € par mois</b> ; <b>Pro, %(prix_pro)s € par mois</b> ; <b>Pro annuel, %(prix_pro_an)s € par an</b>. Studjoow facture depuis Israël (Tax ID 337927834), sans TVA hors d'Israël. Le paiement est prélevé par carte via Stripe à la souscription puis à chaque échéance, mensuelle ou annuelle selon la formule. Toute modification de prix est annoncée par e-mail au moins 30 jours avant de s'appliquer ; l'abonné peut résilier avant.</p>
<h2>5. Accès au service</h2>
<p>Après le paiement, une adresse personnelle est affichée une seule fois et envoyée par e-mail. Elle est strictement personnelle : ne la partagez pas. Elle peut être régénérée à tout moment depuis la page <a href="/compte">Mon compte</a>, l'ancienne cessant alors de fonctionner. Chaque adresse personnelle est réservée à une seule personne et comprend, par jour, jusqu'à %(plafond)s appels d'outils (Particulier) ou %(plafond_pro)s (Pro), et au plus 60 requêtes par minute ; au-delà, l'accès reprend le lendemain. L'offre Pro autorise l'usage professionnel, émet les factures au nom de l'entreprise indiquée au paiement et inclut un support prioritaire par e-mail. En cas d'usage manifestement abusif (revente, partage public de l'adresse, extraction massive), Studjoow peut suspendre l'accès après en avoir informé l'abonné.</p>
<h2>6. Durée et résiliation</h2>
<p>L'abonnement est sans engagement et se renouvelle à chaque échéance (mois ou année). L'abonné peut le résilier à tout moment depuis <a href="/compte">Mon compte</a> (portail Stripe) ; la résiliation prend effet à la fin de la période déjà payée, sans remboursement de la période en cours, hors droit de rétractation. En cas d'échec de paiement, l'accès est suspendu jusqu'à régularisation, puis l'abonnement prend fin si le paiement n'aboutit pas.</p>
<h2>7. Droit de rétractation</h2>
<p>Le consommateur dispose d'un délai de 14 jours à compter de la souscription pour se rétracter, sans motif (art. L221-18 du Code de la consommation). Lors de la commande, il demande expressément que le service commence immédiatement, avant la fin de ce délai. S'il se rétracte ensuite, il verse un montant proportionné au service fourni jusqu'à la communication de sa décision (art. L221-25) ; Studjoow rembourse le reste sous 14 jours, par le même moyen de paiement.</p>
<p>Pour se rétracter, il suffit d'envoyer une déclaration sans ambiguïté à <a href="mailto:%(contact)s">%(contact)s</a>, par exemple avec le formulaire ci-dessous.</p>
<h3>Formulaire de rétractation</h3>
<p>À l'attention de Studjoow, 49 Abarbanel, Tel Aviv 6608912, Israël, %(contact)s :<br>Je vous notifie par la présente ma rétractation du contrat portant sur la prestation de services ci-dessous : abonnement Droit français sourcé.<br>Commandé le : … · Nom du consommateur : … · Adresse e-mail utilisée : … · Date : …</p>
<h2>8. Responsabilité et disponibilité</h2>
<p>Studjoow s'efforce d'assurer un service disponible et des bases à jour, sans garantie de disponibilité continue ni d'exhaustivité. Les données proviennent de sources publiques dont Studjoow n'est pas l'éditeur. Studjoow ne répond pas des réponses rédigées par l'assistant d'intelligence artificielle utilisé, ni des décisions prises sur leur fondement. Rien dans les présentes ne limite les droits que le consommateur tient de la loi.</p>
<h2>9. Données personnelles</h2>
<p>Voir la <a href="/confidentialite">politique de confidentialité</a>.</p>
<h2>10. Litiges et droit applicable</h2>
<p>Les présentes conditions sont soumises au droit français, sans préjudice des dispositions impératives plus protectrices du pays de résidence du consommateur. En cas de difficulté, écrivez d'abord à <a href="mailto:%(contact)s">%(contact)s</a> : nous répondons sous 7 jours ouvrés.</p>
%(mediation)s
""" % {"site": SITE, "editeur": html.escape(EDITEUR), "contact": CONTACT, "prix": PRIX, "essai": ESSAI_PAR_JOUR,
       "mediation": mediation, "plafond": nombre(PLAFOND), "plafond_pro": nombre(PLAFOND_PRO),
       "prix_pro": PRIX_PRO, "prix_pro_an": PRIX_PRO_AN}, "Conditions générales de vente de l'abonnement Droit français sourcé.")


def mentions():
    return gabarit("Mentions légales", """<h1>Mentions légales.</h1>
<h2>Éditeur</h2>
<p>%s.<br>Courriel : <a href="mailto:%s">%s</a>.<br>Directeur de la publication : John Houzi.</p>
<h2>Hébergeur</h2>
<p>Hetzner Online GmbH, Industriestrasse 25, 91710 Gunzenhausen, Allemagne, <a href="https://www.hetzner.com">hetzner.com</a>.</p>
<h2>Données</h2>
<p>Les textes et décisions proviennent des données ouvertes de la Direction de l'information légale et administrative (DILA, Légifrance), réutilisées sous <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/">Licence Ouverte 2.0</a>, qui autorise la réutilisation commerciale sous réserve de mentionner la source et la date de mise à jour (visible sur <a href="/health">/health</a>). Le droit de l'Union provient d'EUR-Lex, © Union européenne, <a href="https://eur-lex.europa.eu">eur-lex.europa.eu</a>, réutilisé conformément à la décision 2011/833/UE. Seuls les textes publiés au Journal officiel font foi. Ce service n'est ni édité ni approuvé par la DILA, Légifrance ou l'Union européenne.</p>
<h2>Code source</h2>
<p>Le logiciel est libre, sous licence MIT : <a href="%s">%s</a>.</p>
<h2>Nature du service</h2>
<p>Information juridique, pas conseil. Pour un cas concret, consultez un avocat.</p>
""" % (html.escape(EDITEUR), CONTACT, CONTACT, REPO, REPO), "Mentions légales du service Droit français sourcé.")


def confidentialite():
    return gabarit("Politique de confidentialité", """<h1>Confidentialité.</h1>
<p class="maj">En vigueur au 22 octobre 2026</p>
<h2>Responsable du traitement</h2>
<p>%s. Contact : <a href="mailto:%s">%s</a>.</p>
<h2>Ce que nous ne collectons pas</h2>
<p>Ni cookie, ni traceur, ni outil de mesure d'audience. Les questions juridiques envoyées par votre assistant aux outils ne sont ni conservées ni associées à votre identité. Les polices sont hébergées sur ce serveur.</p>
<h2>Essai gratuit</h2>
<p>Pour appliquer la limite de %d requêtes par jour, nous conservons une empreinte non réversible de votre adresse IP (HMAC SHA-256 avec un sel secret) et un compteur par jour. Ces lignes sont supprimées automatiquement au bout de 2 jours. Base légale : intérêt légitime (prévenir les abus d'un service gratuit).</p>
<h2>Abonnement</h2>
<ul><li>Données : adresse e-mail, identifiants client et abonnement Stripe, statut et dates de l'abonnement, empreinte SHA-256 de votre adresse personnelle (jamais l'adresse en clair), horodatage de votre demande d'accès immédiat.</li>
<li>Connexion des assistants : nom de l'assistant enregistré (Claude, ChatGPT...), empreintes des jetons de connexion (jamais les jetons en clair), conservées 90 jours au plus ; code de connexion à usage unique, valable 10 minutes.</li>
<li>Finalités : fournir le service, envoyer votre adresse personnelle et les messages liés au compte, prouver votre demande d'exécution immédiate.</li>
<li>Base légale : exécution du contrat ; obligations légales pour la facturation.</li>
<li>Durée : pendant l'abonnement, puis 12 mois après sa fin, avant suppression automatique. Les justificatifs de paiement sont conservés par Stripe selon ses obligations légales.</li></ul>
<h2>Destinataires et sous-traitants</h2>
<ul><li><b>Stripe</b> (paiement) : vos coordonnées bancaires sont saisies chez Stripe et ne transitent jamais par nos serveurs.</li>
<li><b>Resend</b> (envoi des e-mails), établi aux États-Unis : transfert encadré par les clauses contractuelles types de la Commission européenne.</li>
<li><b>Hetzner Online GmbH</b> (hébergement), Allemagne.</li>
<li><b>OpenAI</b> (analyse de conformité en ligne, seulement si vous la lancez), établi aux États-Unis : la description du projet lui est transmise pour produire le rapport ; elle n'est pas conservée par Studjoow, et le rapport est effacé de notre mémoire au bout d'une heure. Transfert encadré par les clauses contractuelles types.</li></ul>
<p>Les journaux techniques du serveur n'enregistrent ni votre adresse IP ni votre adresse personnelle ; ils tournent sur 30 Mo au plus avant d'être écrasés.</p>
<h2>Vos droits</h2>
<p>Accès, rectification, effacement, limitation, opposition et portabilité : écrivez à <a href="mailto:%s">%s</a>. Vous pouvez aussi saisir la CNIL (<a href="https://www.cnil.fr">cnil.fr</a>).</p>
""" % (html.escape(EDITEUR), CONTACT, CONTACT, ESSAI_PAR_JOUR, CONTACT, CONTACT), "Politique de confidentialité du service Droit français sourcé.")


def md_html(texte):
    """Markdown simple (titres, listes, gras, italique) vers HTML ; tout est échappé avant mise en forme."""
    import re
    lignes, html_out, liste = (texte or "").splitlines(), [], None

    def inline(t):
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return insec(t)

    def fermer():
        nonlocal liste
        if liste:
            html_out.append("</%s>" % liste)
            liste = None

    for l in lignes:
        s = l.strip()
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            fermer()
            niveau = min(len(m.group(1)) + 1, 4)
            html_out.append("<h%d>%s</h%d>" % (niveau, inline(m.group(2)), niveau))
        elif re.match(r"^[-*•]\s+", s):
            if liste != "ul":
                fermer()
                html_out.append("<ul>")
                liste = "ul"
            html_out.append("<li>%s</li>" % inline(re.sub(r"^[-*•]\s+", "", s)))
        elif re.match(r"^\d+[.)]\s+", s):
            if liste != "ol":
                fermer()
                html_out.append("<ol>")
                liste = "ol"
            html_out.append("<li>%s</li>" % inline(re.sub(r"^\d+[.)]\s+", "", s)))
        elif not s:
            fermer()
        else:
            fermer()
            html_out.append("<p>%s</p>" % inline(s))
    fermer()
    return "\n".join(html_out)


CSS_CONF = """
[hidden]{display:none!important}
.conf-form textarea{width:100%;min-height:190px;font:15px/1.55 var(--sans);padding:14px;border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--fg);resize:vertical}
.conf-form label.l{display:block;font:600 13px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:16px 0 8px}
.exemple{font-size:13.5px;color:var(--muted);margin:6px 0 0}
.rapport{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:30px 30px 24px;margin-top:22px}
.rapport h3{font-family:var(--serif);font-weight:400;font-size:30px;line-height:1.1;margin:30px 0 10px}.rapport h3:first-child{margin-top:0}.rapport h4{font:600 17px var(--sans);margin:20px 0 6px}
.rapport li{margin:6px 0}
.rapport b{color:var(--fg)}
.attente{display:flex;align-items:center;gap:14px;font-size:15px;color:var(--ink)}
.roue{width:22px;height:22px;border-radius:50%;border:3px solid var(--soft);border-top-color:var(--accent);animation:tourne 1s linear infinite}
@keyframes tourne{to{transform:rotate(360deg)}}
.ia-mention{font-size:13px;color:var(--muted);border-top:1px dashed var(--line);padding-top:12px;margin-top:22px}
@media print{header,footer,.ctas-rapport,.ia-actions{display:none}.rapport{border:0;padding:0}body::before{display:none}}
"""


def page_conformite(erreur=None, description="", ferme=False):
    if ferme:
        return gabarit("Analyse de conformité", "<h1>Bientôt.</h1><p>L'analyse de conformité en ligne ouvre prochainement.</p>", indexer=False)
    alerte = '<p class="alerte">%s</p>' % html.escape(erreur) if erreur else ""
    return gabarit("Analyse de conformité", """<style>%s</style>
<h1>Votre projet est-il<br>dans les règles ?</h1>
<p>Décrivez votre projet : l'analyse repère les obligations françaises et européennes qui s'appliquent (RGPD, cookies, vente en ligne, abonnements, IA, droit d'auteur, mentions légales...), lit chaque texte officiel et vous rend un rapport sourcé, avec vos priorités.</p>
<p class="mini">Réservé aux abonnés : %d analyses par mois en Particulier, %d en Pro. Durée : une à deux minutes.</p>
%s
<form class="carte conf-form" method="post" action="/conformite" style="max-width:760px">
<label class="l" for="d">Votre projet</label>
<textarea id="d" name="description" required minlength="80" maxlength="6000" placeholder="Activité, public visé (particuliers, entreprises, enfants), données collectées, paiement, abonnement, prestataires (hébergeur, e-mails, paiement), usage de l'IA, contenus publiés par les utilisateurs...">%s</textarea>
<p class="exemple">Exemple : « Boutique en ligne de livres personnalisés pour enfants. Le client saisit le prénom et envoie des photos, paie par Stripe ; les illustrations sont générées par IA, le livre est imprimé et livré. Newsletter et Google Analytics. Hébergé chez Vercel. »</p>
<label class="l" for="a">Votre adresse personnelle</label>
<input class="champ" id="a" name="adresse" placeholder="%s/mcp/..." autocomplete="off" required>
<label class="coche"><input type="checkbox" name="avertissement" value="1" required><span>Je comprends qu'il s'agit d'une pré-analyse générée par une IA à partir des textes officiels : de l'information juridique, pas un avis d'avocat ni une certification de conformité. La description est transmise à OpenAI pour l'analyse et n'est pas conservée par Studjoow.</span></label>
<p><button class="btn btn-1" type="submit">Lancer l'analyse</button></p>
</form>
<p class="mini">Pas encore abonné ? <a href="/abonnement">Particulier</a> ou <a href="/abonnement?offre=pro">Pro</a>.</p>
""" % (CSS_CONF, int(os.environ.get("DROIT_IA_PAR_MOIS", "5")), int(os.environ.get("DROIT_IA_PAR_MOIS_PRO", "100")),
       alerte, html.escape(description), SITE), "Pré-analyse de conformité d'un projet au droit français et européen, sourcée.", indexer=True)


def page_rapport(job):
    return gabarit("Rapport de conformité", """<style>%s</style>
<h1>Rapport de conformité.</h1>
<div id="attente" class="attente"><span class="roue"></span><span id="etape">Analyse en cours : repérage des obligations...</span></div>
<div id="rapport" class="rapport" hidden></div>
<p class="ia-actions" id="actions" hidden><button class="btn btn-1" type="button" onclick="print()">Imprimer ou enregistrer en PDF</button> <a class="btn btn-2" href="/conformite">Nouvelle analyse</a></p>
<p class="ia-mention">Rapport généré par une intelligence artificielle à partir des textes officiels (Légifrance, EUR-Lex). Information juridique, pas un avis : faites valider les points importants par un avocat. Ce rapport reste disponible une heure à cette adresse.</p>
<script>
(function(){
  var job=%s, n=0;
  function suivre(){
    fetch('/conformite/etat/'+job,{cache:'no-store'}).then(function(r){return r.json()}).then(function(d){
      if(d.etat==='fini'){document.getElementById('attente').hidden=true;var r=document.getElementById('rapport');r.innerHTML=d.html;r.hidden=false;document.getElementById('actions').hidden=false;return}
      if(d.etat==='erreur'||d.etat==='inconnu'){document.getElementById('etape').textContent=d.erreur||'Rapport introuvable.';document.querySelector('.roue').hidden=true;return}
      document.getElementById('etape').textContent='Analyse en cours : '+(d.etape||'')+'...';
      if(++n<200)setTimeout(suivre,3000);
    }).catch(function(){setTimeout(suivre,5000)});
  }
  suivre();
})();
</script>
""" % (CSS_CONF, json.dumps(job)), "Rapport de conformité", indexer=False)


CSS_OAUTH = """
:root{--bg:#f2f3fb;--paper:#ffffff;--fg:#1b0b16;--ink:#3a3f4e;--muted:#7e8493;--line:#d8dbe4;--accent:#b1338a;--accent2:#e0539f;--soft:#eddaec;--deep:#040e30;--ko:#bf000f;--ok:#00a06d;
  --serif:'Instrument Serif',Georgia,serif;--sans:'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',sans-serif;--mono:'Geist Mono',ui-monospace,Menlo,monospace}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font:16px/1.6 var(--sans);color:var(--fg);background:var(--deep);
  background-image:radial-gradient(700px 420px at 12% 8%,rgba(177,51,138,.38),transparent 70%),radial-gradient(600px 400px at 95% 100%,rgba(224,83,159,.22),transparent 70%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 16px}
.carte-auth{width:100%;max-width:440px;background:var(--paper);border-radius:24px;padding:34px 32px 26px;box-shadow:0 40px 90px -30px rgba(0,0,0,.6)}
.liaison{display:flex;align-items:center;justify-content:center;gap:12px;margin:0 0 22px}
.liaison img{width:56px;height:56px;border-radius:16px;display:block}
.liaison .assistant{width:56px;height:56px;border-radius:16px;background:var(--soft);color:var(--accent);display:flex;align-items:center;justify-content:center;
  font:400 28px var(--serif)}
.liaison .fil{display:flex;gap:5px}.liaison .fil i{width:6px;height:6px;border-radius:50%;background:var(--line)}
.liaison .fil i:nth-child(2){background:var(--accent2)}
h1{font:400 32px/1.08 var(--serif);text-align:center;margin:0 0 6px;letter-spacing:-.01em}
.sous{text-align:center;color:var(--muted);font-size:14.5px;margin:0 0 24px}
label.l{display:block;font:600 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.champ{width:100%;font:16px var(--sans);padding:14px 16px;border:1.5px solid var(--line);border-radius:12px;background:#fff;color:var(--fg);outline:none;transition:border-color .15s}
.champ:focus{border-color:var(--accent)}
.cases{display:flex;gap:8px;justify-content:space-between}
.cases input{width:100%;max-width:52px;height:60px;text-align:center;font:600 26px var(--mono);border:1.5px solid var(--line);border-radius:12px;background:#fff;color:var(--fg);outline:none}
.cases input:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(177,51,138,.12)}
.btn{display:block;width:100%;margin-top:16px;font:600 15.5px var(--sans);border:0;border-radius:12px;padding:15px 18px;cursor:pointer;background:var(--accent);color:#fff;
  box-shadow:0 12px 26px -14px var(--accent);transition:transform .15s}
.btn:hover{transform:translateY(-1px)}
.alerte{background:#fdecee;color:var(--ko);border-radius:10px;padding:10px 14px;font-size:14px;margin:0 0 16px}
.info{color:var(--ink);font-size:14.5px;margin:0 0 16px;text-align:center}
.liens{display:flex;justify-content:center;gap:18px;flex-wrap:wrap;margin-top:20px;font-size:13.5px}
.liens button{background:none;border:0;padding:0;font:inherit;color:var(--muted);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.liens button:hover{color:var(--accent)}
.garanties{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;margin:22px 0 0;padding:16px 0 0;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.garanties span::before{content:"§ ";color:var(--accent);font-family:var(--serif)}
.pied{margin-top:20px;font-size:12.5px;color:#8a90a3;text-align:center}.pied a{color:#c9cdd8}
@media (max-width:420px){.carte-auth{padding:28px 20px 22px}.cases{gap:6px}.cases input{height:54px;font-size:22px}}
"""


def _masquer(email):
    if "@" not in email:
        return email
    nom, dom = email.split("@", 1)
    return nom[:2] + "•" * max(len(nom) - 2, 2) + "@" + dom


def _page_auth(titre, contenu):
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · Droit by Studjoow</title><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#040e30">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>%s%s</style></head><body>%s
<p class="pied">Droit by Studjoow · <a href="/">droit.studjoow.com</a> · Information juridique, pas conseil.</p></body></html>""" % (
        html.escape(titre), FONTS, CSS_OAUTH, contenu)


def page_oauth(nom_client, demande, etape="email", email="", erreur=None):
    e = html.escape
    alerte = '<p class="alerte">%s</p>' % e(erreur) if erreur else ""
    cache = '<input type="hidden" name="demande" value="%s">' % e(demande)
    initiale = e((nom_client or "A").strip()[:1].upper())

    def lien(action, texte, extra=""):
        return ('<form method="post" action="/oauth/authorize">%s<input type="hidden" name="action" value="%s">%s'
                '<button type="submit">%s</button></form>' % (cache, action, extra, texte))

    if etape == "code":
        sous = "Code envoyé à <b>%s</b> s'il correspond à un abonnement actif." % e(_masquer(email))
        corps = """%s<form method="post" action="/oauth/authorize" id="f">%s<input type="hidden" name="action" value="code">
<input type="hidden" name="code" id="code">
<label class="l">Code à 6 chiffres</label>
<div class="cases" id="cases">%s</div>
<button class="btn" type="submit">Connecter</button></form>
<div class="liens">%s%s</div>
<script>
(function(){var c=[].slice.call(document.querySelectorAll('#cases input')),h=document.getElementById('code');
function maj(){h.value=c.map(function(i){return i.value}).join('')}
c.forEach(function(i,k){
 i.addEventListener('input',function(){var v=i.value.replace(/\\D/g,'');if(v.length>1){v.split('').forEach(function(d,j){if(c[k+j])c[k+j].value=d});(c[Math.min(k+v.length,5)]).focus()}else{i.value=v;if(v&&k<5)c[k+1].focus()}maj();if(h.value.length===6)document.getElementById('f').submit()});
 i.addEventListener('keydown',function(ev){if(ev.key==='Backspace'&&!i.value&&k>0){c[k-1].focus()}});
 i.addEventListener('paste',function(ev){var t=(ev.clipboardData||window.clipboardData).getData('text').replace(/\\D/g,'').slice(0,6);if(!t)return;ev.preventDefault();
  t.split('').forEach(function(d,j){if(c[j])c[j].value=d});maj();(c[t.length]||c[5]).focus();if(t.length===6)document.getElementById('f').submit()});
});c[0].focus();})();
</script>""" % (alerte, cache, "".join('<input inputmode="numeric" autocomplete="%s" maxlength="1" aria-label="Chiffre %d">'
                                       % ("one-time-code" if k == 0 else "off", k + 1) for k in range(6)),
                lien("email", "Renvoyer un code", '<input type="hidden" name="email" value="%s">' % e(email)),
                lien("retour", "Changer d'e-mail"))
    elif etape == "cle":
        sous = "Collez l'adresse personnelle reçue après votre paiement."
        corps = """%s<form method="post" action="/oauth/authorize">%s<input type="hidden" name="action" value="cle">
<label class="l" for="a">Adresse personnelle</label>
<input class="champ" id="a" name="adresse" placeholder="%s/mcp/..." autocomplete="off" required autofocus>
<button class="btn" type="submit">Connecter</button></form>
<div class="liens">%s</div>""" % (alerte, cache, SITE, lien("retour", "Recevoir plutôt un code par e-mail"))
    else:
        sous = "Saisissez l'e-mail de votre abonnement : vous recevrez un code de connexion."
        corps = """%s<form method="post" action="/oauth/authorize">%s<input type="hidden" name="action" value="email">
<label class="l" for="m">Votre e-mail</label>
<input class="champ" id="m" type="email" name="email" value="%s" placeholder="vous@exemple.fr" autocomplete="email" required autofocus>
<button class="btn" type="submit">Recevoir mon code</button></form>
<div class="liens">%s</div>""" % (alerte, cache, e(email), lien("cle", "J'ai mon adresse personnelle"))
    contenu = """<main class="carte-auth">
<div class="liaison"><img src="/static/icones/icone-192.png" alt="Droit by Studjoow"><span class="fil"><i></i><i></i><i></i></span><span class="assistant" aria-hidden="true">%s</span></div>
<h1>Connecter %s</h1>
<p class="sous">%s</p>
%s
<div class="liens">%s</div>
<div class="garanties"><span>Sans mot de passe</span><span>Code valable 10 min</span><span>Déconnexion depuis <a href="/compte" style="color:inherit">votre compte</a></span></div>
</main>""" % (initiale, e(nom_client), sous, corps, lien("refuser", "Annuler"))
    return _page_auth("Connexion", contenu)


def page_oauth_erreur(message):
    return _page_auth("Connexion impossible", """<main class="carte-auth">
<div class="liaison"><img src="/static/icones/icone-192.png" alt="Droit by Studjoow"></div>
<h1>Connexion impossible</h1><p class="alerte" style="margin-top:16px">%s</p>
<p class="info">Besoin d'aide : <a href="mailto:%s">%s</a></p></main>""" % (html.escape(message), CONTACT, CONTACT))
