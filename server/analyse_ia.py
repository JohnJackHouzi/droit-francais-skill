import asyncio
import json
import os
import secrets
import time

import httpx

CLE = os.environ.get("DROIT_OPENAI_API_KEY", "")
MODELE = os.environ.get("DROIT_IA_MODELE", "gpt-4.1-mini")
API = os.environ.get("DROIT_OPENAI_API", "https://api.openai.com/v1")
TOURS_MAX = int(os.environ.get("DROIT_IA_TOURS", "12"))
SORTIE_OUTIL_MAX = 6000
QUOTAS = {"particulier": int(os.environ.get("DROIT_IA_PAR_MOIS", "5")),
          "pro": int(os.environ.get("DROIT_IA_PAR_MOIS_PRO", "100"))}

CONSIGNE = """Tu rédiges une pré-analyse de conformité d'un projet au regard du droit français et du droit de l'Union européenne, pour un entrepreneur non juriste.
Méthode obligatoire :
1. Appelle d'abord analyser_conformite avec la description du projet.
2. Lis les textes des points les plus importants (au moins un par domaine détecté) avec lire_article ou lire_texte_ue : ne cite jamais un article de mémoire.
3. Pour chaque obligation, classe-la : MANQUANT, À VÉRIFIER (la description ne dit rien) ou CONFORME EN APPARENCE. Sans information, c'est À VÉRIFIER, jamais conforme.
4. Contrôle avec verifier_references toutes les références que tu cites ; retire celles qui sont introuvables.
Rapport en français, en Markdown simple (titres ##, listes, gras) :
## Synthèse (3 à 5 phrases, les risques principaux)
## Priorités (les 5 actions les plus importantes, dans l'ordre)
## Détail par domaine (pour chaque point : statut, ce que dit le texte avec un court extrait entre guillemets, ce qu'il faut faire, référence)
## Questions pour un avocat
## Sources (une ligne par texte : intitulé, identifiant Légifrance ou CELEX)
Termine par : « Pré-analyse générée par une IA à partir des textes officiels : information juridique, pas un avis. »
Pas de tiret cadratin. Phrases courtes."""


def _fn(nom, description, proprietes, requis):
    return {"type": "function", "function": {"name": nom, "description": description, "parameters": {
        "type": "object", "properties": proprietes, "required": requis, "additionalProperties": False}}}


S = {"type": "string"}
OUTILS = [
    _fn("analyser_conformite", "Liste les obligations probables du projet et le texte à lire pour chacune.",
        {"description": S, "domaines": S}, ["description", "domaines"]),
    _fn("lire_article", "Texte d'un article de code ou de loi en vigueur. code : nom du code ou identifiant LEGITEXT.",
        {"code": S, "numero": S}, ["code", "numero"]),
    _fn("lire_texte_ue", "Article d'un acte de l'UE. reference : RGPD, RIA, DSA, CELEX...",
        {"reference": S, "article": S}, ["reference", "article"]),
    _fn("rechercher_loi", "Recherche plein texte dans les codes et lois.", {"requete": S}, ["requete"]),
    _fn("verifier_references", "Vérifie que des références existent.",
        {"references": {"type": "array", "items": S}}, ["references"]),
]

_travaux = {}


def actif():
    return bool(CLE)


def _purger():
    limite = time.time() - 3600
    for k in [k for k, v in _travaux.items() if v["debut"] < limite]:
        del _travaux[k]


async def _appeler(executer, nom, args):
    try:
        if nom == "analyser_conformite":
            sortie = await executer["analyser_conformite"](args.get("description", ""), args.get("domaines", ""))
        elif nom == "lire_article":
            sortie = await executer["lire_article"](args.get("code", ""), args.get("numero", ""))
        elif nom == "lire_texte_ue":
            sortie = await executer["lire_texte_ue"](args.get("reference", ""), args.get("article", ""), 8000)
        elif nom == "rechercher_loi":
            sortie = await executer["rechercher_loi"](args.get("requete", ""), limite=5)
        elif nom == "verifier_references":
            sortie = await executer["verifier_references"](list(args.get("references") or [])[:20])
        else:
            sortie = "Outil inconnu."
    except Exception as exc:
        sortie = "Erreur de l'outil : %s" % type(exc).__name__
    return sortie[:SORTIE_OUTIL_MAX]


async def _executer(job, description, executer):
    messages = [{"role": "system", "content": CONSIGNE},
                {"role": "user", "content": "Projet à analyser :\n\n" + description}]
    jetons = {"entree": 0, "sortie": 0}
    try:
        async with httpx.AsyncClient(base_url=API, timeout=120, headers={"Authorization": "Bearer " + CLE}) as client:
            for tour in range(TOURS_MAX):
                final = tour == TOURS_MAX - 1
                corps = {"model": MODELE, "messages": messages, "temperature": 0.1}
                if not final:
                    corps["tools"] = OUTILS
                r = await client.post("/chat/completions", json=corps)
                d = r.json()
                if r.status_code >= 400:
                    raise RuntimeError((d.get("error") or {}).get("message", "erreur %d" % r.status_code))
                u = d.get("usage") or {}
                jetons["entree"] += u.get("prompt_tokens", 0)
                jetons["sortie"] += u.get("completion_tokens", 0)
                msg = d["choices"][0]["message"]
                appels = msg.get("tool_calls") or []
                messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
                if not appels:
                    job.update(etat="fini", rapport=msg.get("content") or "", jetons=jetons)
                    return
                job["etape"] = "Lecture des textes (%d outils appelés)" % (job.get("appels", 0) + len(appels))
                job["appels"] = job.get("appels", 0) + len(appels)
                sorties = await asyncio.gather(*[
                    _appeler(executer, a["function"]["name"], json.loads(a["function"].get("arguments") or "{}"))
                    for a in appels])
                for a, sortie in zip(appels, sorties):
                    messages.append({"role": "tool", "tool_call_id": a["id"], "content": sortie})
        job.update(etat="erreur", erreur="Analyse trop longue, réessayer avec une description plus courte.", jetons=jetons)
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
