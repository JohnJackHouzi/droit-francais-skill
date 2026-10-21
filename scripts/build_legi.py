#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legi_common as lc


def iter_chunks(root, size):
    chunk = []
    for dirpath, _dirs, files in os.walk(root):
        if "/eli" in dirpath:
            continue
        for name in files:
            if name.endswith(".xml") and lc.FILE_RE.match(name):
                chunk.append(os.path.join(dirpath, name))
                if len(chunk) >= size:
                    yield chunk
                    chunk = []
    if chunk:
        yield chunk


def build_base(con, base, root, workers, log):
    t0 = time.time()
    n_art = n_txt = n_cont = 0
    errors = []
    with mp.Pool(workers) as pool:
        for results in pool.imap_unordered(lc.parse_files, iter_chunks(root, 400), chunksize=1):
            a, t, c, errs = lc.store(con, results)
            n_art += a
            n_txt += t
            n_cont += c
            errors.extend(errs)
            total = n_art + n_txt + n_cont
            if total // 25000 != (total - len(results)) // 25000:
                con.commit()
                log("%s: %d articles, %d textes, %d conteneurs, %d erreurs, %.0fs"
                    % (base, n_art, n_txt, n_cont, len(errors), time.time() - t0))
    con.commit()
    log("%s TERMINE: %d articles, %d textes, %d conteneurs, %d erreurs en %.0fs"
        % (base, n_art, n_txt, n_cont, len(errors), time.time() - t0))
    for e in errors[:20]:
        log("  erreur %s %s" % (e[1], e[2]))
    return errors


def main():
    ap = argparse.ArgumentParser(description="Construit legi.sqlite depuis les dumps DILA extraits")
    ap.add_argument("--bases", default="kali,legi,jorf")
    ap.add_argument("--data", default=lc.DATA_DIR)
    ap.add_argument("--db", default=lc.DB_PATH)
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    ap.add_argument("--no-fts", action="store_true", help="saute index et FTS (à faire au dernier passage)")
    ap.add_argument("--fts-only", action="store_true")
    args = ap.parse_args()

    def log(msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    con = lc.connect(args.db)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-1000000")
    con.execute("PRAGMA temp_store=FILE")
    lc.init_db(con)
    if not args.fts_only:
        for base in args.bases.split(","):
            root = os.path.join(args.data, base)
            if not os.path.isdir(root):
                log("dossier absent, ignoré: %s" % root)
                continue
            build_base(con, base, root, args.workers, log)
            con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("built_" + base, time.strftime("%Y-%m-%d %H:%M:%S")))
            con.commit()
    if not args.no_fts:
        log("index et FTS5 ...")
        t0 = time.time()
        lc.finalize(con)
        log("FTS terminé en %.0fs" % (time.time() - t0))
    con.close()


if __name__ == "__main__":
    main()
