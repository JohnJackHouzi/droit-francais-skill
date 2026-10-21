#!/usr/bin/env python3
"""Construit ou complète eu.sqlite (droit de l'UE en français) depuis l'API Cellar de l'Office des publications.

  build_eu.py                      périmètre de départ (RGPD, IA, DSA, DMA, consommation, commerce
                                   électronique, droit d'auteur, traités et Charte)
  build_eu.py --celex 32019L0790   actes précis
  build_eu.py --chiffrer           compte et estime les volumes sans rien télécharger
  build_eu.py --actes-en-vigueur   tous les règlements et directives de base en vigueur
  build_eu.py --cjue --depuis 2015 arrêts de la Cour de justice et du Tribunal
"""
import argparse
import datetime
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eu_common as ec

DEPART = [
    "32016R0679",  # RGPD
    "32024R1689",  # règlement sur l'intelligence artificielle
    "32022R2065",  # DSA
    "32022R1925",  # DMA
    "32000L0031",  # commerce électronique
    "32011L0083",  # droits des consommateurs
    "32005L0029",  # pratiques commerciales déloyales
    "31993L0013",  # clauses abusives
    "32019L0770",  # contenus et services numériques
    "32019L0771",  # vente de biens
    "32019L2161",  # omnibus consommateurs
    "32023L2225",  # crédit à la consommation
    "32024L2853",  # produits défectueux
    "32001L0029",  # droit d'auteur dans la société de l'information
    "32019L0790",  # droit d'auteur dans le marché unique numérique
    "32002L0058",  # vie privée et communications électroniques
    "32023R2854",  # Data Act
    "32022R0868",  # gouvernance des données
    "12016P/TXT",  # Charte des droits fondamentaux
    "12016M/TXT",  # traité sur l'Union européenne
    "12016E/TXT",  # traité sur le fonctionnement de l'Union européenne
]

PFX = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
RT = "http://publications.europa.eu/resource/authority/resource-type/"
FRA = "<http://publications.europa.eu/resource/authority/language/FRA>"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def metadonnees(celexes):
    vals = " ".join('"%s"^^xsd:string' % c for c in celexes)
    q = PFX + """SELECT ?celex ?type ?date ?force ?ecli ?titre WHERE {
  VALUES ?celex { %s }
  ?w cdm:resource_legal_id_celex ?celex .
  OPTIONAL { ?w cdm:work_has_resource-type ?type }
  OPTIONAL { ?w cdm:work_date_document ?date }
  OPTIONAL { ?w cdm:resource_legal_in-force ?force }
  OPTIONAL { ?w cdm:case-law_ecli ?ecli }
  OPTIONAL { ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language %s ; cdm:expression_title ?titre }
}""" % (vals, FRA)
    out = {}
    for r in ec.sparql(q):
        d = out.setdefault(r["celex"], {})
        for k in ("type", "date", "force", "ecli", "titre"):
            if r.get(k) and not d.get(k):
                d[k] = r[k].rsplit("/", 1)[-1] if k == "type" else " ".join(r[k].replace("#", " ").split())
    return out


def derniere_consolidation(celex):
    if not celex[:1] == "3":
        return None
    q = PFX + 'SELECT ?c WHERE { ?w cdm:resource_legal_id_celex ?c . FILTER(STRSTARTS(STR(?c), "0%s-")) }' % celex[1:]
    today = datetime.date.today().strftime("%Y%m%d")
    versions = sorted(r["c"] for r in ec.sparql(q) if r["c"].split("-")[-1] <= today)
    return versions[-1] if versions else None


def texte_html(celex):
    s, ctype, body = ec.http(ec.CELEX_URL + celex.replace("/", "%2F"), "application/xhtml+xml")
    if s == 200 and body:
        return body
    q = PFX + """SELECT ?m WHERE { ?w cdm:resource_legal_id_celex "%s"^^xsd:string .
  ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language %s .
  ?m cdm:manifestation_manifests_expression ?e ; cdm:manifestation_type ?t . FILTER(STR(?t) IN ("html","xhtml")) }""" % (celex, FRA)
    for r in ec.sparql(q):
        for n in range(1, 5):
            s, ctype, body = ec.http("%s/DOC_%d" % (r["m"], n))
            if s == 200 and body and "html" in ctype:
                return body
    return None


def traiter(celex, meta):
    try:
        return _traiter(celex, meta)
    except Exception as exc:
        log("  %s : erreur %r" % (celex, exc))
        return celex, meta.get(celex, {}), None, None


def _traiter(celex, meta):
    m = meta.get(celex, {})
    typ = m.get("type") or ""
    version = None if typ in ("JUDG", "ORDER", "OPIN_AG") else derniere_consolidation(celex)
    source = version or celex
    raw = texte_html(source)
    if raw is None and version:
        source, raw = celex, texte_html(celex)
    if raw is None:
        return celex, m, None, None
    lignes = ec.html_to_lines(raw)
    if typ in ("JUDG", "ORDER", "OPIN_AG"):
        parties = [(ec.TYPES.get(typ, typ).lower(), m.get("titre"), "\n".join(lignes))]
    else:
        parties = ec.split_acte(lignes)
    return celex, m, source if version and source == version else None, parties


def enregistrer(con, celex, m, version, parties):
    old = con.execute("SELECT 1 FROM docs WHERE celex=?", (celex,)).fetchone()
    if old:
        con.execute("DELETE FROM parties WHERE celex=?", (celex,))
        con.execute("DELETE FROM docs WHERE celex=?", (celex,))
    date_version = version.split("-")[-1] if version else None
    if date_version:
        date_version = "%s-%s-%s" % (date_version[:4], date_version[4:6], date_version[6:])
    con.execute("INSERT INTO docs (celex, celex_version, date_version, type, titre, date, en_vigueur, ecli, affaire, maj) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (celex, version, date_version, m.get("type"), m.get("titre"), m.get("date"),
                 m.get("force"), m.get("ecli"), ec.affaire(celex), time.strftime("%Y-%m-%d")))
    con.executemany("INSERT INTO parties (celex, ordre, num, num_norm, titre, contenu) VALUES (?,?,?,?,?,?)",
                    [(celex, i, n, ec.norm_num(n), t, c) for i, (n, t, c) in enumerate(parties)])


def liste_actes_en_vigueur():
    q = PFX + """SELECT DISTINCT ?c WHERE { ?w cdm:resource_legal_in-force "true"^^xsd:boolean ;
  cdm:work_has_resource-type ?t ; cdm:resource_legal_id_celex ?c .
  FILTER(?t IN (<%sREG>, <%sDIR>)) FILTER(STRSTARTS(STR(?c), "3")) }""" % (RT, RT)
    return sorted(r["c"] for r in ec.sparql(q))


def liste_cjue(depuis):
    q = PFX + """SELECT DISTINCT ?c WHERE { ?w cdm:work_has_resource-type <%sJUDG> ; cdm:resource_legal_id_celex ?c ;
  cdm:work_date_document ?d . FILTER(STRSTARTS(STR(?c), "6")) FILTER(?d >= "%s-01-01"^^xsd:date) }""" % (RT, depuis)
    return sorted(r["c"] for r in ec.sparql(q))


def chiffrer(depuis):
    actes = liste_actes_en_vigueur()
    cjue = liste_cjue(depuis)
    log("règlements et directives de base en vigueur : %d" % len(actes))
    log("arrêts CJUE et Tribunal depuis %s : %d" % (depuis, len(cjue)))
    log("estimation (moyennes mesurées : actes ~250 Ko, arrêts ~90 Ko, ~1 s par document) :")
    log("  actes : %.1f Go téléchargés, ~%.1f h à 4 en parallèle" % (len(actes) * 250e3 / 1e9, len(actes) * 1.0 / 4 / 3600))
    log("  arrêts : %.1f Go téléchargés, ~%.1f h à 4 en parallèle" % (len(cjue) * 90e3 / 1e9, len(cjue) * 1.0 / 4 / 3600))
    log("  base finale estimée : %.1f Go (texte ~30 %% du HTML, plus l'index plein texte)"
        % ((len(actes) * 250e3 + len(cjue) * 90e3) * 0.3 * 2 / 1e9))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--celex", nargs="+")
    ap.add_argument("--actes-en-vigueur", action="store_true")
    ap.add_argument("--cjue", action="store_true")
    ap.add_argument("--depuis", default="1954")
    ap.add_argument("--chiffrer", action="store_true")
    ap.add_argument("--reprendre", action="store_true", help="sauter les CELEX déjà présents")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=ec.DB_PATH)
    a = ap.parse_args()

    if a.chiffrer:
        return chiffrer(a.depuis)
    if a.celex:
        cibles = a.celex
    elif a.actes_en_vigueur:
        cibles = liste_actes_en_vigueur()
    elif a.cjue:
        cibles = liste_cjue(a.depuis)
    else:
        cibles = DEPART
    con = ec.connect(a.db)
    if a.reprendre:
        deja = {r[0] for r in con.execute("SELECT celex FROM docs")}
        cibles = [c for c in cibles if c not in deja]
    log("%d document(s) à traiter" % len(cibles))
    ok = manquants = 0
    for i in range(0, len(cibles), 50):
        lot = cibles[i:i + 50]
        meta = metadonnees(lot)
        with ThreadPoolExecutor(a.workers) as pool:
            for celex, m, version, parties in pool.map(lambda c: traiter(c, meta), lot):
                if not parties:
                    manquants += 1
                    log("  %s : pas de texte français disponible" % celex)
                    continue
                enregistrer(con, celex, m, version, parties)
                ok += 1
        con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("derniere_mise_a_jour", time.strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
        log("%d/%d traités (%d sans texte)" % (min(i + 50, len(cibles)), len(cibles), manquants))
    con.close()


if __name__ == "__main__":
    main()
