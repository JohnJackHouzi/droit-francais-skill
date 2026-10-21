#!/usr/bin/env python3
"""Première installation des bases DILA dans DROIT_DATA, puis mises à jour quotidiennes.

Une base à la fois : téléchargement du dump global, extraction, indexation, puis suppression
de l'archive et des XML avant de passer à la suivante. Arrêt si l'espace libre passe sous
DROIT_MIN_FREE_GO (15 Go par défaut). Le fichier .installation-en-cours dans DROIT_DATA
signale au serveur que les bases ne sont pas prêtes.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
MIN_FREE = float(os.environ.get("DROIT_MIN_FREE_GO", "15")) * 1e9
URL = "https://echanges.dila.gouv.fr/OPENDATA/%s/"
UA = {"User-Agent": "droit-francais-skill/1.0"}
LEGI_BASES = ("kali", "legi", "jorf")
JURI_BASES = ("constit", "cnil", "cass", "capp", "inca", "jade")
MARKER = os.path.join(DATA, ".installation-en-cours")


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "[install]", msg, flush=True)


class EspaceInsuffisant(Exception):
    pass


def check_space(step, besoin=0):
    libre = shutil.disk_usage(DATA).free
    log("espace libre %.1f Go avant : %s" % (libre / 1e9, step))
    if libre - besoin < MIN_FREE:
        raise EspaceInsuffisant(
            "%.1f Go libres (besoin estimé %.1f Go) : arrêt avant « %s », il faut garder %.0f Go libres"
            % (libre / 1e9, besoin / 1e9, step, MIN_FREE / 1e9))


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def global_dump(base):
    page = get(URL % base.upper()).decode("utf-8", "replace")
    noms = sorted(set(re.findall(r'href="(Freemium_%s_global_(\d{8}-\d{6})\.tar\.gz)"' % base, page)))
    if not noms:
        raise RuntimeError("aucun dump global trouvé pour %s" % base)
    return noms[-1]


def taille(url):
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length") or 0)


def telecharger(url, dest):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, \
            open(dest + ".part", "wb") as fh:
        shutil.copyfileobj(r, fh, 1 << 20)
    os.replace(dest + ".part", dest)


def extraire(archive, dest):
    dest_abs = os.path.realpath(dest)
    with tarfile.open(archive, "r|gz") as tar:
        for m in tar:
            if not (m.isfile() or m.isdir()):
                continue
            cible = os.path.realpath(os.path.join(dest, m.name))
            if not (cible == dest_abs or cible.startswith(dest_abs + os.sep)):
                raise RuntimeError("chemin suspect dans l'archive : %s" % m.name)
            tar.extract(m, dest, set_attrs=False)


def meta_get(db, table, key_col, val_col, key):
    if not os.path.exists(db):
        return None
    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT %s FROM %s WHERE %s=?" % (val_col, table, key_col), (key,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    con.close()
    return row[0] if row else None


def meta_set(db, table, pairs):
    con = sqlite3.connect(db)
    con.executemany("INSERT OR REPLACE INTO %s VALUES (?,?)" % table, pairs)
    con.commit()
    con.close()


def run(script, *args):
    cmd = [sys.executable, "-I", os.path.join(HERE, script), *args]
    log("lance " + " ".join(cmd[2:]))
    subprocess.run(cmd, check=True)


def installer_base(base, groupe):
    db = os.path.join(DATA, groupe + ".sqlite")
    if groupe == "legi":
        fait = meta_get(db, "meta", "k", "v", "built_" + base)
    else:
        fait = meta_get(db, "meta", "cle", "valeur", "dump_" + base)
    if fait:
        log("%s déjà construite (%s), ignorée" % (base, fait))
        return False
    nom, stamp = global_dump(base)
    url = URL % base.upper() + nom
    archive = os.path.join(DATA, nom)
    dossier = os.path.join(DATA, base)
    if not os.path.exists(archive):
        poids = taille(url)
        check_space("téléchargement %s (%.1f Go)" % (nom, poids / 1e9), poids)
        log("téléchargement " + url)
        telecharger(url, archive)
    poids = os.path.getsize(archive)
    shutil.rmtree(dossier, ignore_errors=True)
    check_space("extraction %s" % nom, poids * 8)
    log("extraction dans " + dossier)
    extraire(archive, dossier)
    os.remove(archive)
    check_space("indexation %s" % base)
    if groupe == "legi":
        run("build_legi.py", "--bases", base, "--no-fts")
        meta_set(db, "meta", [("last_increment_" + base, stamp)])
    else:
        run("build_juri.py", "--bases", base, "--no-fts")
        meta_set(db, "meta", [("dump_" + base, stamp), ("incremental_" + base, stamp)])
    shutil.rmtree(dossier, ignore_errors=True)
    log("%s terminée, XML et archive supprimés" % base)
    return True


def installer(bases):
    os.makedirs(DATA, exist_ok=True)
    for groupe, liste in (("legi", LEGI_BASES), ("juri", JURI_BASES)):
        nouveau = False
        for base in liste:
            if base in bases:
                nouveau |= installer_base(base, groupe)
        db = os.path.join(DATA, groupe + ".sqlite")
        if nouveau or not fts_present(db):
            check_space("index plein texte %s" % groupe)
            run("build_%s.py" % groupe, "--fts-only")


def fts_present(db):
    if not os.path.exists(db):
        return False
    table = "articles_fts_docsize" if db.endswith("legi.sqlite") else "decisions_fts_docsize"
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    try:
        return con.execute("SELECT 1 FROM %s LIMIT 1" % table).fetchone() is not None
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


def mettre_a_jour():
    for script in ("update_legi.py", "update_juri.py"):
        try:
            run(script)
        except subprocess.CalledProcessError as exc:
            log("échec %s (code %s), nouvel essai au prochain passage" % (script, exc.returncode))


def attendre(heure):
    now = time.time()
    t = time.gmtime(now)
    cible = now - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec) + heure * 3600
    if cible <= now:
        cible += 86400
    log("prochaine mise à jour dans %.1f h (%02d:00 UTC)" % ((cible - now) / 3600, heure))
    time.sleep(cible - now)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bases", default=os.environ.get("DROIT_BASES") or ",".join(LEGI_BASES + JURI_BASES))
    ap.add_argument("--service", action="store_true",
                    help="installer si besoin, puis appliquer les incrémentaux chaque jour (mode conteneur)")
    ap.add_argument("--sans-installation", action="store_true",
                    help="ne pas télécharger les dumps (bases envoyées par rsync)")
    ap.add_argument("--heure", type=int, default=int(os.environ.get("DROIT_UPDATE_HOUR_UTC", "3")))
    args = ap.parse_args()
    bases = set(args.bases.split(","))

    if not args.sans_installation:
        open(MARKER, "w").close()
        try:
            installer(bases)
        except EspaceInsuffisant as exc:
            log("ARRÊT : %s" % exc)
            sys.exit(2)
        os.remove(MARKER)
        log("installation terminée")
    if not args.service:
        return
    mettre_a_jour()
    while True:
        attendre(args.heure)
        mettre_a_jour()


if __name__ == "__main__":
    main()
