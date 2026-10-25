#!/usr/bin/env python3
"""Met à jour eu.sqlite depuis l'API Cellar : nouveaux actes en vigueur, nouvelles consolidations,
actes abrogés, nouveaux arrêts de la Cour de justice et du Tribunal.

  update_eu.py                 mise à jour complète (appelée chaque nuit par install.py --service)
  update_eu.py --dry-run       compte ce qui serait fait, sans rien écrire
  update_eu.py --max 100       plafond de documents téléchargés par étape (défaut 400)
"""
import argparse
import datetime
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_eu as be
import eu_common as ec

EN_VIGUEUR = ("1", "true")
RETENTER_APRES_JOURS = 30


def log(msg):
    print(time.strftime("%H:%M:%S"), "eu", msg, flush=True)


def meta_get(con, cle):
    r = con.execute("SELECT v FROM meta WHERE k=?", (cle,)).fetchone()
    return r[0] if r else None


def meta_set(con, cle, valeur):
    con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (cle, valeur))


def date_depart(con):
    v = meta_get(con, "derniere_verification") or meta_get(con, "derniere_mise_a_jour")
    if not v:
        sys.exit("eu.sqlite vide ou sans date : lancer build_eu.py d'abord")
    return datetime.date.fromisoformat(v[:10]) - datetime.timedelta(days=3)


def consolidations_depuis(jour):
    q = be.PFX + """SELECT DISTINCT ?c WHERE { ?w cdm:resource_legal_id_celex ?c .
  FILTER(STRSTARTS(STR(?c), "0")) FILTER(STRAFTER(STR(?c), "-") >= "%s") }""" % jour.strftime("%Y%m%d")
    out = {}
    for r in ec.sparql(q):
        c = r["c"]
        base = "3" + c[1:].rsplit("-", 1)[0]
        out.setdefault(base, set()).add(c)
    return out


def absents_recents(con):
    con.execute("CREATE TABLE IF NOT EXISTS absents (celex TEXT PRIMARY KEY, essai TEXT)")
    limite = (datetime.date.today() - datetime.timedelta(days=RETENTER_APRES_JOURS)).isoformat()
    return {r[0] for r in con.execute("SELECT celex FROM absents WHERE essai > ?", (limite,))}


def importer(con, cibles, workers, dry):
    if dry or not cibles:
        return 0, 0
    ok = sans_texte = 0
    for i in range(0, len(cibles), 50):
        lot = cibles[i:i + 50]
        meta = be.metadonnees(lot)
        with ThreadPoolExecutor(workers) as pool:
            for celex, m, version, parties in pool.map(lambda c: be.traiter(c, meta), lot):
                if not parties:
                    con.execute("INSERT OR REPLACE INTO absents VALUES (?,?)", (celex, time.strftime("%Y-%m-%d")))
                    sans_texte += 1
                    continue
                be.enregistrer(con, celex, m, version, parties)
                con.execute("DELETE FROM absents WHERE celex=?", (celex,))
                ok += 1
        con.commit()
        log("  %d/%d traités (%d sans texte français)" % (min(i + 50, len(cibles)), len(cibles), sans_texte))
    return ok, sans_texte


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=ec.DB_PATH)
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--controle", type=int, default=150, help="actes revérifiés chaque nuit, les moins récemment vus d'abord")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        log("eu.sqlite absente : rien à mettre à jour")
        return
    con = ec.connect(a.db)
    con.execute("CREATE TABLE IF NOT EXISTS absents (celex TEXT PRIMARY KEY, essai TEXT)")
    depart = date_depart(con)
    log("recherche des changements depuis le %s" % depart.isoformat())
    en_base = {r[0]: r[1] for r in con.execute("SELECT celex, en_vigueur FROM docs")}
    ecartes = absents_recents(con)
    bilan = {}

    actes = set(be.liste_actes_en_vigueur())
    log("actes en vigueur selon Cellar : %d" % len(actes))

    nouveaux = sorted(c for c in actes if c not in en_base and c not in ecartes)
    bilan["nouveaux actes"] = len(nouveaux)
    ok, _ = importer(con, nouveaux[:a.max], a.workers, a.dry_run)
    bilan["actes ajoutés"] = ok

    suivis = {c for c, v in en_base.items() if v in EN_VIGUEUR and c.startswith("3")}
    abroges = sorted(suivis - actes)
    if actes and len(actes) >= 0.8 * len(suivis):
        bilan["actes abrogés"] = len(abroges)
        if abroges and not a.dry_run:
            con.executemany("UPDATE docs SET en_vigueur='0', maj=? WHERE celex=?",
                            [(time.strftime("%Y-%m-%d"), c) for c in abroges])
            con.commit()
    else:
        log("liste Cellar anormalement courte (%d pour %d suivis) : abrogations ignorées" % (len(actes), len(suivis)))

    con.execute("CREATE TABLE IF NOT EXISTS consol_vues (celex TEXT, version TEXT, PRIMARY KEY (celex, version))")
    vues = {(r[0], r[1]) for r in con.execute("SELECT celex, version FROM consol_vues")}
    aujourdhui = datetime.date.today().strftime("%Y%m%d")
    cibles_version = {}
    versions_essayees = {}
    consolides = consolidations_depuis(datetime.date(depart.year - 1, 1, 1))
    for base, versions in consolides.items():
        if en_base.get(base) in EN_VIGUEUR:
            actuelle = con.execute("SELECT celex_version FROM docs WHERE celex=?", (base,)).fetchone()[0] or ""
            eligibles = [v for v in versions if v.split("-")[-1] <= aujourdhui and v > actuelle and (base, v) not in vues]
            if eligibles:
                cibles_version[base] = max(eligibles)
                versions_essayees[base] = eligibles
    a_controler = [r[0] for r in con.execute(
        "SELECT celex FROM docs WHERE en_vigueur IN ('1','true') AND type IN ('REG','DIR') "
        "ORDER BY maj, celex LIMIT ?", (a.controle,))]
    for celex in a_controler:
        if celex in cibles_version:
            continue
        derniere = be.derniere_consolidation(celex)
        actuelle = con.execute("SELECT celex_version FROM docs WHERE celex=?", (celex,)).fetchone()[0] or ""
        if derniere and derniere > actuelle and (celex, derniere) not in vues:
            cibles_version[celex] = derniere
            versions_essayees[celex] = [derniere]
        elif not a.dry_run:
            con.execute("UPDATE docs SET maj=? WHERE celex=?", (time.strftime("%Y-%m-%d"), celex))
    if not a.dry_run:
        con.commit()
    a_refaire = sorted(cibles_version)
    bilan["actes à re-consolider"] = len(a_refaire)
    ok, _ = importer(con, a_refaire[:a.max], a.workers, a.dry_run)
    bilan["consolidations mises à jour"] = ok
    if not a.dry_run:
        con.executemany("INSERT OR IGNORE INTO consol_vues VALUES (?,?)",
                        [(c, v) for c in a_refaire[:a.max] for v in versions_essayees[c]])
        con.commit()

    arrets = [c for c in be.liste_cjue(str(depart.year)) if c not in en_base and c not in ecartes]
    bilan["nouveaux arrêts"] = len(arrets)
    ok, sans = importer(con, arrets[:a.max], a.workers, a.dry_run)
    bilan["arrêts ajoutés"] = ok
    bilan["arrêts sans texte français"] = sans

    if not a.dry_run:
        meta_set(con, "derniere_verification", time.strftime("%Y-%m-%d %H:%M:%S"))
        meta_set(con, "derniere_mise_a_jour", time.strftime("%Y-%m-%d %H:%M:%S"))
        con.commit()
    for k, v in bilan.items():
        log("%s : %d" % (k, v))
    if a.dry_run:
        log("(simulation : rien n'a été écrit)")
    con.close()


if __name__ == "__main__":
    main()
