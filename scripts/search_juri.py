import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import juri_common as jc

NOMS_BASES = {
    "jade": "juridictions administratives", "cass": "Cour de cassation",
    "capp": "cours d'appel", "inca": "Cour de cassation (inédits)",
    "constit": "Conseil constitutionnel", "cnil": "CNIL",
}


def plier(texte):
    if texte is None:
        return ""
    t = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "a", "à", "au", "aux", "un", "une", "en",
              "que", "qui", "qu", "par", "pour", "sur", "dans", "ce", "ces", "se", "sa", "son", "ses", "il", "elle",
              "est", "ou", "ne", "pas", "s", "n", "y", "c", "j", "m", "t"}


def requete_fts(q):
    morceaux = re.findall(r'"[^"]*"|\S+', q)
    if not any(m.startswith('"') or m in ("AND", "OR", "NOT", "NEAR") for m in morceaux):
        mots = [w for m in morceaux for w in re.findall(r"\w+\*?", m, re.U)]
        utiles = [w for w in mots if plier(w.rstrip("*")) not in MOTS_VIDES]
        morceaux = utiles or mots
    sortie = []
    for m in morceaux:
        if m.startswith('"') or m in ("AND", "OR", "NOT", "NEAR") or re.fullmatch(r"\w+\*?", m, re.U):
            sortie.append(m)
        else:
            sortie.append('"%s"' % m.replace('"', ""))
    return " ".join(sortie)


def ouvrir(chemin):
    if not os.path.exists(chemin):
        sys.exit("Base introuvable : %s (lancer build_juri.py)" % chemin)
    con = sqlite3.connect("file:%s?mode=ro" % chemin, uri=True)
    con.row_factory = sqlite3.Row
    con.create_function("plier", 1, plier, deterministic=True)
    return con


def libelle_resultat(r):
    morceaux = [r["juridiction"] or NOMS_BASES.get(r["base"], r["base"])]
    if r["formation"]:
        f = r["formation"]
        morceaux.append(f.replace("_", " ").capitalize() if "_" in f else f)
    morceaux.append(r["date"] or "date inconnue")
    if r["numero"]:
        morceaux.append("n° " + r["numero"])
    ligne = " | ".join(morceaux)
    if r["solution"]:
        ligne += " | " + r["solution"]
    pub = (r["publication"] or "")
    if pub.startswith("oui"):
        ligne += " | Publié au bulletin"
    elif r["base"] == "jade" and pub:
        ligne += " | " + pub
    return ligne


def coupe(texte, n):
    texte = re.sub(r"\s+", " ", texte or "").strip()
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


def afficher_resultats(lignes, avec_extrait):
    if not lignes:
        print("Aucun résultat.")
        return
    for i, r in enumerate(lignes, 1):
        print("%d. %s" % (i, libelle_resultat(r)))
        if r["titre"]:
            print("   " + coupe(r["titre"], 200))
        if r["sommaire"]:
            print("   Sommaire : " + coupe(r["sommaire"], 400))
        if avec_extrait and r["extrait"]:
            print("   Extrait  : " + re.sub(r"\s+", " ", r["extrait"]).strip())
        if r["ecli"]:
            print("   ECLI     : " + r["ecli"])
        print("   Lien     : " + jc.lien_legifrance(r["base"], r["id"]))
        print("   Id       : " + r["id"])
        print()


def construire_filtres(a):
    where, params = [], []
    if a.base:
        where.append("d.base IN (%s)" % ",".join("?" * len(a.base)))
        params += a.base
    if a.juridiction:
        where.append("plier(d.juridiction) LIKE ?")
        params.append("%" + plier(a.juridiction) + "%")
    if a.formation:
        where.append("plier(d.formation) LIKE ?")
        params.append("%" + plier(a.formation) + "%")
    if a.du:
        where.append("d.date >= ?")
        params.append(a.du)
    if a.au:
        where.append("d.date <= ?")
        params.append(a.au)
    if a.ecli:
        where.append("d.ecli = ?")
        params.append(a.ecli.strip())
    if a.numero:
        where.append("d.id IN (SELECT id FROM numeros WHERE num = ?)")
        params.append(jc.norm_numero(a.numero))
    if a.publie:
        where.append("(d.publication LIKE 'oui%' OR d.publication LIKE 'Publié au recueil%' OR d.publication LIKE 'Mentionné aux tables%')")
    return where, params


def rechercher(con, a):
    where, params = construire_filtres(a)
    if a.q:
        sql = (
            "SELECT d.*, snippet(decisions_fts, 2, '**', '**', ' ... ', 45) AS extrait, "
            "snippet(decisions_fts, 1, '**', '**', ' ... ', 45) AS extrait_sommaire "
            "FROM decisions_fts JOIN decisions d ON d.rowid = decisions_fts.rowid "
            "WHERE decisions_fts MATCH ?"
        )
        params = [requete_fts(a.q)] + params
        if where:
            sql += " AND " + " AND ".join(where)
        sql += " ORDER BY " + ("d.date DESC" if a.tri == "date" else "bm25(decisions_fts, 5.0, 3.0, 1.0)")
    else:
        if not where:
            sys.exit("Donner au moins --q, --numero, --ecli ou un filtre.")
        sql = "SELECT d.*, '' AS extrait, '' AS extrait_sommaire FROM decisions d WHERE " + " AND ".join(where)
        sql += " ORDER BY d.date DESC"
    sql += " LIMIT ?"
    params.append(a.limit)
    return con.execute(sql, params).fetchall()


def afficher_decision(con, ident, max_chars):
    r = con.execute("SELECT * FROM decisions WHERE id = ?", (ident,)).fetchone()
    if not r:
        sys.exit("Décision introuvable : %s" % ident)
    print(libelle_resultat(r))
    print("Titre    : " + (r["titre"] or ""))
    if r["numero_arret"]:
        print("N° arrêt : " + r["numero_arret"])
    if r["nature"]:
        print("Nature   : " + r["nature"])
    if r["ecli"]:
        print("ECLI     : " + r["ecli"])
    print("Lien     : " + jc.lien_legifrance(r["base"], r["id"]))
    if r["sommaire"]:
        print("\n--- Sommaire ---\n" + r["sommaire"])
    print("\n--- Texte intégral ---")
    contenu = r["contenu"] or ""
    if max_chars and len(contenu) > max_chars:
        print(contenu[:max_chars] + "\n[... tronqué à %d caractères sur %d]" % (max_chars, len(contenu)))
    else:
        print(contenu)
    if r["textes_cites"]:
        print("\n--- Textes cités ---\n" + r["textes_cites"])


def main():
    ap = argparse.ArgumentParser(
        description="Recherche dans la jurisprudence française (JADE, CASS, CAPP, INCA, CONSTIT, CNIL).")
    ap.add_argument("commande", nargs="*", help="decision <id> pour afficher une décision en entier")
    ap.add_argument("--q", help="plein texte (mots, \"phrase exacte\", AND/OR/NOT, prefixe*)")
    ap.add_argument("--base", action="append", choices=jc.BASES, help="restreindre à une base (répétable)")
    ap.add_argument("--juridiction", help="nom ou fragment : « conseil d'etat », « cour d'appel de paris »")
    ap.add_argument("--formation", help="formation ou chambre : « sociale », « assemblee plenière »")
    ap.add_argument("--du", help="date minimale AAAA-MM-JJ")
    ap.add_argument("--au", help="date maximale AAAA-MM-JJ")
    ap.add_argument("--numero", help="numéro de pourvoi, de requête, d'affaire ou de décision : 21-12.345")
    ap.add_argument("--ecli")
    ap.add_argument("--publie", action="store_true", help="seulement les décisions publiées (bulletin, Lebon)")
    ap.add_argument("--tri", choices=("pertinence", "date"), default="pertinence")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--max-chars", type=int, default=0, help="decision : tronquer le texte intégral")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=jc.DB_PATH)
    a = ap.parse_args()

    con = ouvrir(a.db)
    if a.commande:
        if a.commande[0] != "decision" or len(a.commande) != 2:
            sys.exit("Usage : search_juri.py decision <ID>")
        afficher_decision(con, a.commande[1], a.max_chars)
        return
    try:
        lignes = rechercher(con, a)
    except sqlite3.OperationalError as e:
        sys.exit("Requête invalide (%s). Mettre les expressions entre guillemets doubles." % e)
    if a.json:
        sortie = []
        for r in lignes:
            d = {k: r[k] for k in r.keys() if k not in ("contenu", "rowid", "extrait_sommaire")}
            d["lien"] = jc.lien_legifrance(r["base"], r["id"])
            sortie.append(d)
        print(json.dumps(sortie, ensure_ascii=False, indent=1))
        return
    resultats = [dict(zip(r.keys(), tuple(r))) for r in lignes]
    for r in resultats:
        if "**" not in (r["extrait"] or "") and "**" in (r["extrait_sommaire"] or ""):
            r["extrait"] = r["extrait_sommaire"]
    afficher_resultats(resultats, True)


if __name__ == "__main__":
    main()
