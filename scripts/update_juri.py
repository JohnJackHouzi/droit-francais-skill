import argparse
import os
import re
import sys
import tarfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import juri_common as jc

URL_BASE = "https://echanges.dila.gouv.fr/OPENDATA/"
DUMP_GLOBAL = "20250713-140000"
DOSSIER_TELECH = os.path.join(jc.DATA_DIR, "_incr")
RE_ID = re.compile(r"\b[A-Z]{4,8}TEXT\d{12}\b")


def lister_incrementaux(base):
    url = "%s%s/" % (URL_BASE, base.upper())
    with urllib.request.urlopen(url, timeout=60) as r:
        page = r.read().decode("utf-8", "replace")
    noms = sorted(set(re.findall(r"%s_(\d{8}-\d{6})\.tar\.gz" % base.upper(), page)))
    return noms


def telecharger(base, horodatage, dossier):
    os.makedirs(dossier, exist_ok=True)
    nom = "%s_%s.tar.gz" % (base.upper(), horodatage)
    dest = os.path.join(dossier, nom)
    tmp = dest + ".part"
    with urllib.request.urlopen("%s%s/%s" % (URL_BASE, base.upper(), nom), timeout=120) as r, open(tmp, "wb") as f:
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
    os.replace(tmp, dest)
    return dest


def lire_archive(chemin, base):
    docs, suppressions = [], set()
    erreurs = 0
    with tarfile.open(chemin, "r|gz") as tar:
        for membre in tar:
            if not membre.isfile():
                continue
            nom = os.path.basename(membre.name)
            contenu = tar.extractfile(membre).read().decode("utf-8", "replace")
            if nom.endswith(".xml"):
                d = jc.parse_decision(contenu, base)
                if d is None:
                    erreurs += 1
                else:
                    docs.append(d)
            elif nom.startswith("liste_suppression"):
                suppressions.update(RE_ID.findall(contenu))
    return docs, suppressions, erreurs


def retirer(con, ident):
    ligne = con.execute(
        "SELECT rowid, titre, sommaire, contenu FROM decisions WHERE id=?", (ident,)).fetchone()
    if not ligne:
        return False
    con.execute(
        "INSERT INTO decisions_fts(decisions_fts, rowid, titre, sommaire, contenu) VALUES('delete', ?, ?, ?, ?)",
        ligne)
    con.execute("DELETE FROM decisions WHERE rowid=?", (ligne[0],))
    con.execute("DELETE FROM numeros WHERE id=?", (ident,))
    return True


def inserer(con, d):
    existait = retirer(con, d["id"])
    cur = con.execute(jc.INSERT_SQL, jc.ligne_sql(d))
    rowid = cur.lastrowid
    con.execute(
        "INSERT INTO decisions_fts(rowid, titre, sommaire, contenu) VALUES (?, ?, ?, ?)",
        (rowid, d["titre"], d["sommaire"], d["contenu"]))
    con.executemany("INSERT INTO numeros (num, id) VALUES (?, ?)",
                    [(jc.norm_numero(x), d["id"]) for x in d["_numeros"] if x])
    return existait


def appliquer(con, base, chemin):
    docs, suppressions, erreurs = lire_archive(chemin, base)
    supprimees = sum(1 for ident in suppressions if retirer(con, ident))
    ajoutees = maj = 0
    for d in docs:
        if inserer(con, d):
            maj += 1
        else:
            ajoutees += 1
    return {"xml": len(docs), "ajoutees": ajoutees, "mises_a_jour": maj,
            "suppressions_demandees": len(suppressions), "supprimees": supprimees, "erreurs": erreurs}


def main():
    ap = argparse.ArgumentParser(
        description="Applique les incrémentaux DILA postérieurs au dump global du 13/07/2025.")
    ap.add_argument("--bases", nargs="+", default=list(jc.BASES), choices=jc.BASES)
    ap.add_argument("--db", default=jc.DB_PATH)
    ap.add_argument("--depuis", help="forcer l'horodatage de départ AAAAMMJJ-HHMMSS (sinon lu dans la base)")
    ap.add_argument("--jour", help="n'appliquer que les incrémentaux de ce jour AAAAMMJJ (test)")
    ap.add_argument("--max", type=int, default=0, help="nombre max d'incrémentaux par base")
    ap.add_argument("--dry-run", action="store_true", help="lister sans télécharger ni appliquer")
    ap.add_argument("--garder", action="store_true", help="conserver les archives téléchargées")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit("Base absente : %s (lancer build_juri.py ou install.py d'abord)" % a.db)
    con = jc.open_db(a.db)
    con.execute("PRAGMA synchronous=NORMAL")
    for base in a.bases:
        if not a.depuis and not con.execute("SELECT 1 FROM meta WHERE cle=?", ("dump_" + base,)).fetchone():
            print("%s : base jamais construite (build_juri.py), ignorée" % base, flush=True)
            continue
        ligne = con.execute("SELECT valeur FROM meta WHERE cle=?", ("incremental_" + base,)).fetchone()
        depuis = a.depuis or (ligne[0] if ligne else DUMP_GLOBAL)
        try:
            tous = lister_incrementaux(base)
        except Exception as e:
            print("%s : liste indisponible (%s)" % (base, e), flush=True)
            continue
        a_faire = [h for h in tous if h > depuis]
        if a.jour:
            a_faire = [h for h in a_faire if h.startswith(a.jour)]
        if a.max:
            a_faire = a_faire[: a.max]
        print("%s : %d incrémentaux à appliquer après %s" % (base, len(a_faire), depuis), flush=True)
        for h in a_faire:
            if a.dry_run:
                print("  (dry-run) %s_%s" % (base.upper(), h))
                continue
            chemin = telecharger(base, h, os.path.join(DOSSIER_TELECH, base))
            try:
                con.execute("BEGIN")
                bilan = appliquer(con, base, chemin)
                con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("incremental_" + base, h))
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            print("  %s : %s" % (h, bilan), flush=True)
            if not a.garder:
                os.remove(chemin)
    con.close()


if __name__ == "__main__":
    main()
