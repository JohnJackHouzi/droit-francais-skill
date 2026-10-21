import argparse
import os
import sys
import time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import juri_common as jc


def lister(dossier):
    for racine, dirs, fichiers in os.walk(dossier):
        dirs.sort()
        for f in sorted(fichiers):
            if f.endswith(".xml"):
                yield os.path.join(racine, f)


def traiter(args):
    chemin, base = args
    try:
        with open(chemin, encoding="utf-8") as fh:
            d = jc.parse_decision(fh.read(), base)
    except Exception as e:
        return ("erreur", chemin, repr(e))
    if d is None:
        return ("erreur", chemin, "pas d'ID")
    return ("ok", d)


def construire_base(con, base, source, workers, limite):
    t0 = time.time()
    con.execute("DELETE FROM numeros WHERE id IN (SELECT id FROM decisions WHERE base=?)", (base,))
    con.execute("DELETE FROM decisions WHERE base=?", (base,))
    con.commit()
    taches = ((p, base) for p in lister(source))
    if limite:
        taches = ((p, b) for i, (p, b) in enumerate(taches) if i < limite)
    n = erreurs = 0
    lot, lot_num = [], []
    with Pool(workers) as pool:
        for res in pool.imap(traiter, taches, chunksize=50):
            if res[0] == "erreur":
                erreurs += 1
                if erreurs <= 10:
                    print("  erreur", res[1], res[2], flush=True)
                continue
            d = res[1]
            lot.append(jc.ligne_sql(d))
            lot_num.extend((jc.norm_numero(x), d["id"]) for x in d["_numeros"] if x)
            n += 1
            if len(lot) >= 2000:
                con.executemany(jc.INSERT_SQL, lot)
                con.executemany("INSERT INTO numeros (num, id) VALUES (?, ?)", lot_num)
                lot, lot_num = [], []
            if n % 20000 == 0:
                con.commit()
                print("  %s : %d decisions (%.0fs)" % (base, n, time.time() - t0), flush=True)
    if lot:
        con.executemany(jc.INSERT_SQL, lot)
        con.executemany("INSERT INTO numeros (num, id) VALUES (?, ?)", lot_num)
    con.commit()
    print("%s : %d decisions, %d erreurs, %.0fs" % (base, n, erreurs, time.time() - t0), flush=True)
    return n


def reconstruire_fts(con):
    t0 = time.time()
    print("FTS : reconstruction...", flush=True)
    con.execute("INSERT INTO decisions_fts(decisions_fts) VALUES('rebuild')")
    con.commit()
    print("FTS : fait en %.0fs" % (time.time() - t0), flush=True)


def main():
    ap = argparse.ArgumentParser(description="Construit juri.sqlite depuis les dumps DILA")
    ap.add_argument("--bases", nargs="+", default=list(jc.BASES), choices=jc.BASES)
    ap.add_argument("--source", default=jc.DATA_DIR, help="dossier contenant <base>/ extrait")
    ap.add_argument("--db", default=jc.DB_PATH)
    ap.add_argument("--workers", type=int, default=max(2, min(6, cpu_count() - 2)))
    ap.add_argument("--limite", type=int, default=0, help="test : nombre max de fichiers par base")
    ap.add_argument("--no-fts", action="store_true")
    ap.add_argument("--fts-only", action="store_true")
    a = ap.parse_args()

    con = jc.open_db(a.db)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-400000")
    if not a.fts_only:
        for base in a.bases:
            dossier = os.path.join(a.source, base)
            if not os.path.isdir(dossier):
                print("%s : dossier absent (%s), ignore" % (base, dossier), flush=True)
                continue
            construire_base(con, base, dossier, a.workers, a.limite)
            con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("dump_" + base, "20250713-140000"))
            con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("incremental_" + base, "20250713-140000"))
            con.commit()
        con.executescript(jc.INDEXES)
    if not a.no_fts:
        reconstruire_fts(con)
        con.execute("INSERT INTO decisions_fts(decisions_fts) VALUES('optimize')")
        con.commit()
    for base, n in con.execute("SELECT base, count(*) FROM decisions GROUP BY base ORDER BY base"):
        print("  %-8s %d" % (base, n))
    con.close()


if __name__ == "__main__":
    main()
