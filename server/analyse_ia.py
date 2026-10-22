"""Analyse de conformité en ligne : le serveur repère les obligations (conformite.py), lit lui-même chaque texte
officiel dans les bases, puis demande au modèle, en un seul appel structuré, de les appliquer au projet.
Les citations renvoyées sont contrôlées mot pour mot dans le texte lu ; le rapport est mis en page ici."""

import asyncio
import json
import os
import re
import secrets
import time
import unicodedata

import httpx

import conformite

CLE = os.environ.get("DROIT_OPENAI_API_KEY", "")
MODELE = os.environ.get("DROIT_IA_MODELE", "gpt-4.1-mini")
API = os.environ.get("DROIT_OPENAI_API", "https://api.openai.com/v1")
TEXTE_MAX = 1800
QUOTAS = {"particulier": int(os.environ.get("DROIT_IA_PAR_MOIS", "5")),
          "pro": int(os.environ.get("DROIT_IA_PAR_MOIS_PRO", "100"))}
STATUTS = ("MANQUANT", "À VÉRIFIER", "CONFORME EN APPARENCE")

CONSIGNE = """Tu rédiges une pré-analyse de conformité d'un projet au regard du droit français et européen, pour un entrepreneur non juriste.
Tu reçois la description du projet puis une liste numérotée d'obligations, chacune avec le TEXTE OFFICIEL lu dans la base (Légifrance, EUR-Lex) et une question de contrôle.
Pour CHAQUE obligation (aucune oubliée, même identifiant) :
- statut : MANQUANT (la description montre que ce n'est pas fait), À VÉRIFIER (la description ne permet pas de savoir) ou CONFORME EN APPARENCE (la description montre que c'est fait). Dans le doute, À VÉRIFIER.
- constat : ce que le texte exige, appliqué à CE projet, en 1 ou 2 phrases simples et concrètes.
- action : ce qu'il faut faire dans ce projet, concret (où, quoi). Chaîne vide si conforme.
- citation : un court extrait (8 à 30 mots) COPIÉ MOT POUR MOT du texte officiel fourni, sans rien changer. Chaîne vide si aucun extrait utile. Jamais la question de contrôle.
Puis : synthese (3 à 5 phrases sur les vrais risques de CE projet), priorites (5 actions concrètes, dans l'ordre), questions_avocat (3 à 5).
Français, phrases courtes, pas de tiret cadratin. Information juridique, pas un avis."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["synthese", "priorites", "obligations", "questions_avocat"],
          "properties": {
              "synthese": {"type": "string"},
              "priorites": {"type": "array", "items": {"type": "string"}},
              "questions_avocat": {"type": "array", "items": {"type": "string"}},
              "obligations": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["id", "statut", "constat", "action", "citation"],
                  "properties": {"id": {"type": "integer"}, "statut": {"type": "string", "enum": list(STATUTS)},
                                 "constat": {"type": "string"}, "action": {"type": "string"}, "citation": {"type": "string"}}}}}}

_travaux = {}


def actif():
    return bool(CLE)


def _purger():
    limite = time.time() - 3600
    for k in [k for k, v in _travaux.items() if v["debut"] < limite]:
        del _travaux[k]


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower().replace("’", "'").replace(" ", " "))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9']+", " ", t).strip()


def _decouper(sortie):
    """Sépare l'en-tête renvoyé par les scripts (identifiant, lien) du texte de l'article."""
    lignes = sortie.splitlines()
    ident = lien = ""
    for l in (x.strip() for x in lignes[:14]):
        if l.startswith(("ID Légifrance", "ID :")) and not ident:
            ident = l.split(":", 1)[1].split("|")[0].strip()
        elif l.startswith("CELEX") and not ident:
            ident = "CELEX " + l.split(":", 1)[1].split("|")[0].strip()
        elif l.startswith("Lien") and not lien:
            lien = l.split(":", 1)[1].strip()
    seps = [k for k, l in enumerate(lignes) if len(l.strip()) > 20 and set(l.strip()) == {"-"}]
    if seps:
        corps = "\n".join(lignes[seps[-1] + 1:])
    else:
        k = next((k for k, l in enumerate(lignes) if l.strip().startswith("Lien")), -1)
        corps = "\n".join(lignes[k + 1:])
    corps = corps.split("\nLiens (historique")[0].split("\nNota :")[0].replace("**", "").strip()
    return ident, lien, corps


async def _lire(executer, outil, args):
    try:
        if outil == "lire_article":
            return await executer["lire_article"](args["code"], args["numero"])
        if outil == "lire_texte_ue":
            return await executer["lire_texte_ue"](args["reference"], args["article"], 6000)
        return await executer["rechercher_loi"](args["requete"], limite=3)
    except Exception as exc:
        return "Lecture impossible : %s" % type(exc).__name__


def _rendre(trouves, obligations, rep):
    par_id = {o.get("id"): o for o in rep.get("obligations", []) if isinstance(o, dict)}
    compte = dict.fromkeys(STATUTS, 0)
    l = ["## Synthèse", rep.get("synthese", "").strip(), "", "## Priorités"]
    l += ["%d. %s" % (k + 1, p) for k, p in enumerate(rep.get("priorites", [])[:5])]
    l += ["", "## Détail par domaine"]
    sources = []
    for cle, titre, _, _ in trouves:
        l += ["", "### %s" % titre]
        for ob in [o for o in obligations if o["domaine"] == cle]:
            r = par_id.get(ob["id"], {})
            statut = r.get("statut") if r.get("statut") in compte else "À VÉRIFIER"
            compte[statut] += 1
            l.append("- **%s** · %s" % (ob["intitule"], statut))
            if r.get("constat"):
                l.append("  %s" % r["constat"].strip())
            cit = (r.get("citation") or "").strip().strip("«»\"' ").strip()
            if cit and len(_norm(cit)) > 12 and _norm(cit) in _norm(ob["texte"]):
                l.append("  « %s »" % cit)
            if r.get("action") and statut != "CONFORME EN APPARENCE":
                l.append("  À faire : %s" % r["action"].strip())
            if ob["lien"]:
                l.append("  Source : [%s](%s)" % (ob["ident"] or "texte officiel", ob["lien"]))
                deja = [k for k, src in enumerate(sources) if src[2] == ob["lien"]]
                if deja:
                    k = deja[0]
                    sources[k] = (sources[k][0].split(", art.")[0], sources[k][1], sources[k][2])
                else:
                    sources.append((ob["intitule"].split(" : ")[0], ob["ident"], ob["lien"]))
    l += ["", "## Questions pour un avocat"] + ["- %s" % q for q in rep.get("questions_avocat", [])[:5]]
    l += ["", "## Sources"] + ["- %s · [%s](%s)" % s for s in sources]
    l += ["", "Pré-analyse générée par une IA à partir des textes officiels : information juridique, pas un avis."]
    return "\n".join(l), compte


async def _executer(job, description, executer):
    jetons = {"entree": 0, "sortie": 0}
    try:
        trouves = conformite.detecter(description)
        obligations = []
        for cle, titre, indices, obls in trouves:
            for outil, args, intitule, question in obls:
                obligations.append({"id": len(obligations) + 1, "domaine": cle, "outil": outil, "args": args,
                                    "intitule": intitule, "question": question})
        job["etape"] = "Lecture de %d textes officiels" % len(obligations)
        sorties = await asyncio.gather(*[_lire(executer, o["outil"], o["args"]) for o in obligations])
        blocs = []
        for o, sortie in zip(obligations, sorties):
            o["ident"], o["lien"], o["texte"] = _decouper(sortie)
            blocs.append("[%d] %s\nQuestion de contrôle : %s\nTexte officiel :\n%s" % (
                o["id"], o["intitule"], o["question"], o["texte"][:TEXTE_MAX]))
        job["etape"] = "Rédaction du rapport (%d obligations)" % len(obligations)
        corps = {"model": MODELE, "temperature": 0.1,
                 "response_format": {"type": "json_schema", "json_schema": {"name": "rapport", "strict": True, "schema": SCHEMA}},
                 "messages": [{"role": "system", "content": CONSIGNE},
                              {"role": "user", "content": "PROJET :\n%s\n\nOBLIGATIONS :\n\n%s" % (description, "\n\n".join(blocs))}]}
        async with httpx.AsyncClient(base_url=API, timeout=180, headers={"Authorization": "Bearer " + CLE}) as client:
            r = await client.post("/chat/completions", json=corps)
        d = r.json()
        if r.status_code >= 400:
            raise RuntimeError((d.get("error") or {}).get("message", "erreur %d" % r.status_code))
        u = d.get("usage") or {}
        jetons.update(entree=u.get("prompt_tokens", 0), sortie=u.get("completion_tokens", 0))
        rapport, compte = _rendre(trouves, obligations, json.loads(d["choices"][0]["message"]["content"]))
        job.update(etat="fini", rapport=rapport, jetons=jetons, compte=compte, appels=len(obligations))
    except Exception as exc:
        job.update(etat="erreur", erreur="Le service d'analyse est indisponible (%s)." % str(exc)[:120], jetons=jetons)


def lancer(description, executer):
    _purger()
    job_id = secrets.token_urlsafe(18)
    job = {"etat": "en_cours", "etape": "Repérage des obligations", "debut": time.time()}
    _travaux[job_id] = job
    asyncio.get_running_loop().create_task(_executer(job, description, executer))
    return job_id


def etat(job_id):
    return _travaux.get(job_id)
