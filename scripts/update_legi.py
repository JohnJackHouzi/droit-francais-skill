#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legi_common as lc

ROOT_URL = "https://echanges.dila.gouv.fr/OPENDATA/%s/"
GLOBAL_STAMP = "20250713-140000"
UA = {"User-Agent": "droit-francais-skill/1.0"}


def http_get(url, dest=None, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp:
                if dest is None:
                    return resp.read()
                with open(dest + ".part", "wb") as fh:
                    shutil.copyfileobj(resp, fh)
                os.replace(dest + ".part", dest)
                return None
        except Exception as exc:
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError("téléchargement impossible: %s (%r)" % (url, last))


def list_increments(base):
    html = http_get(ROOT_URL % base.upper()).decode("utf-8", "replace")
    pat = re.compile(r'href="(%s_(\d{8}-\d{6})\.tar\.gz)"' % base.upper())
    seen = {}
    for name, stamp in pat.findall(html):
        seen[stamp] = name
    return [(s, seen[s]) for s in sorted(seen)]


def safe_extract(tar, dest):
    dest_abs = os.path.realpath(dest)
    keep = []
    for m in tar.getmembers():
        if not (m.isfile() or m.isdir()):
            continue
        target = os.path.realpath(os.path.join(dest, m.name))
        if not (target == dest_abs or target.startswith(dest_abs + os.sep)):
            raise RuntimeError("chemin suspect dans l'archive: %s" % m.name)
        keep.append(m)
    if hasattr(tarfile, "data_filter"):
        tar.extractall(dest, members=keep, filter="data")
    else:
        tar.extractall(dest, members=keep)


def iter_xml(root):
    chunk = []
    for dirpath, _d, files in os.walk(root):
        if "/eli" in dirpath:
            continue
        for name in files:
            if name.endswith(".xml") and lc.FILE_RE.match(name):
                chunk.append(os.path.join(dirpath, name))
                if len(chunk) >= 200:
                    yield chunk
                    chunk = []
    if chunk:
        yield chunk


def read_deletions(root, base):
    ids = {"ARTI": [], "TEXT": [], "CONT": []}
    for dirpath, _d, files in os.walk(root):
        for name in files:
            if name.startswith("liste_suppression") and name.endswith(".dat"):
                with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        m = lc.FILE_RE.match(os.path.basename(line) + ".xml")
                        if not m:
                            continue
                        kind = m.group(2)
                        if kind == "TEXT" and "/texte/version/" not in line:
                            continue
                        ids[kind].append(os.path.basename(line))
    return ids


def apply_archive(con, base, stamp, root, pool, log):
    n_a = n_t = n_c = 0
    errors = []
    for results in pool.imap_unordered(lc.parse_files, iter_xml(root)):
        a, t, c, errs = lc.store_upsert(con, results)
        n_a += a
        n_t += t
        n_c += c
        errors.extend(errs)
    dels = read_deletions(root, base)
    d_a = d_t = d_c = 0
    if dels["ARTI"]:
        con.executemany("DELETE FROM articles WHERE id = ?", [(i,) for i in dels["ARTI"]])
        d_a = len(dels["ARTI"])
    if dels["TEXT"]:
        con.executemany("DELETE FROM textes WHERE id = ?", [(i,) for i in dels["TEXT"]])
        d_t = len(dels["TEXT"])
    if dels["CONT"]:
        con.executemany("DELETE FROM conteneur_textes WHERE conteneur_id = ?", [(i,) for i in dels["CONT"]])
        con.executemany("DELETE FROM conteneurs WHERE id = ?", [(i,) for i in dels["CONT"]])
        d_c = len(dels["CONT"])
    if base == "kali":
        con.execute("UPDATE textes SET idcc = (SELECT c.idcc FROM conteneur_textes ct JOIN conteneurs c "
                    "ON c.id = ct.conteneur_id WHERE ct.texte_id = textes.id LIMIT 1) "
                    "WHERE base = 'kali' AND idcc IS NULL")
    con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("last_increment_" + base, stamp))
    con.commit()
    log("%s %s : +%d articles, +%d textes, +%d conteneurs ; supprimés : %d articles, %d textes, %d conteneurs ; %d erreurs"
        % (base, stamp, n_a, n_t, n_c, d_a, d_t, d_c, len(errors)))
    for e in errors[:5]:
        log("  erreur %s %s" % (e[1], e[2]))
    return n_a, n_t, d_a


def main():
    ap = argparse.ArgumentParser(description="Applique les fichiers incrémentaux DILA à legi.sqlite")
    ap.add_argument("--bases", default="legi,jorf,kali")
    ap.add_argument("--db", default=lc.DB_PATH)
    ap.add_argument("--cache", default=os.path.join(lc.DATA_DIR, "incrementals"))
    ap.add_argument("--depuis", help="horodatage YYYYMMDD-HHMMSS (défaut: dernier appliqué, sinon dump global %s)" % GLOBAL_STAMP)
    ap.add_argument("--max", type=int, default=0, help="n'appliquer que les N premières archives par base")
    ap.add_argument("--jour", help="n'appliquer que les archives de ce jour YYYYMMDD (test)")
    ap.add_argument("--garder", action="store_true", help="conserver les .tar.gz téléchargés")
    ap.add_argument("--liste", action="store_true", help="afficher ce qui serait appliqué et sortir")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    args = ap.parse_args()

    def log(msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    if not os.path.exists(args.db):
        sys.exit("Base absente: %s (lancer build_legi.py d'abord)" % args.db)
    con = lc.connect(args.db)
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA journal_mode=WAL")
    has_fts = con.execute("SELECT 1 FROM sqlite_master WHERE name='articles_fts'").fetchone()
    if not has_fts:
        sys.exit("La base n'a pas d'index FTS: terminer build_legi.py (sans --no-fts) avant toute mise à jour.")
    os.makedirs(args.cache, exist_ok=True)
    with mp.Pool(args.workers) as pool:
        for base in args.bases.split(","):
            built = con.execute("SELECT v FROM meta WHERE k = ?", ("built_" + base,)).fetchone()
            if not built and not args.depuis:
                log("%s : base jamais construite (build_legi.py), ignorée" % base)
                continue
            row = con.execute("SELECT v FROM meta WHERE k = ?", ("last_increment_" + base,)).fetchone()
            since = args.depuis or (row["v"] if row else GLOBAL_STAMP)
            todo = [(s, n) for s, n in list_increments(base) if s > since]
            if args.jour:
                todo = [(s, n) for s, n in todo if s.startswith(args.jour)]
            if args.max:
                todo = todo[: args.max]
            log("%s : %d archive(s) à appliquer après %s" % (base, len(todo), since))
            if args.liste:
                for s, n in todo[:10]:
                    log("  " + n)
                continue
            for stamp, name in todo:
                dest = os.path.join(args.cache, name)
                if not os.path.exists(dest):
                    http_get(ROOT_URL % base.upper() + name, dest)
                tmp = tempfile.mkdtemp(prefix="legi_inc_", dir=args.cache)
                try:
                    with tarfile.open(dest) as tar:
                        safe_extract(tar, tmp)
                    apply_archive(con, base, stamp, tmp, pool, log)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                if not args.garder:
                    os.remove(dest)
    con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("derniere_mise_a_jour", time.strftime("%Y-%m-%d %H:%M:%S")))
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
