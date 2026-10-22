#!/usr/bin/env python3
"""Recalcule la colonne chemin (plan du texte) des articles avec l'intitulé en vigueur à la date de chaque version.

Relit en flux, sans rien extraire sur le disque, le dump global puis tous les incrémentaux d'une base
(LEGI par défaut). Écrit les changements dans un fichier TSV (id, chemin) puis, avec --appliquer, les
applique à legi.sqlite.
"""
import argparse
import csv
import os
import re
import sys
import tarfile
import time
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legi_common as lc
from update_legi import ROOT_URL, http_get, list_increments


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def lire_archive(fileobj, chemins):
    n = 0
    with tarfile.open(fileobj=fileobj, mode="r|gz") as tar:
        for m in tar:
            name = os.path.basename(m.name)
            if not (m.isfile() and name.startswith("LEGIARTI") and name.endswith(".xml")):
                continue
            try:
                root = ET.fromstring(tar.extractfile(m).read())
            except ET.ParseError:
                continue
            aid = lc.txt(root, "META/META_COMMUN/ID")
            meta = root.find("META/META_SPEC/META_ARTICLE")
            texte = root.find("CONTEXTE/TEXTE")
            if aid is None or meta is None or texte is None:
                continue
            chemins[aid] = lc.chemin_a_date(texte, lc.clean_date(lc.txt(meta, "DATE_DEBUT")))
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, help="Freemium_legi_global_*.tar.gz local")
    ap.add_argument("--db", default=lc.DB_PATH)
    ap.add_argument("--sortie", default=os.path.join(lc.DATA_DIR, "chemins_corriges.tsv"))
    ap.add_argument("--jusqua", help="dernier incrémental à relire (défaut : celui appliqué à la base)")
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    con = lc.connect(a.db, readonly=not a.appliquer)
    jusqua = a.jusqua or con.execute("SELECT v FROM meta WHERE k='last_increment_legi'").fetchone()[0]
    chemins = {}
    log("dump %s" % a.dump)
    with open(a.dump, "rb") as fh:
        log("dump : %d articles" % lire_archive(fh, chemins))
    stamp_dump = re.search(r"(\d{8}-\d{6})", os.path.basename(a.dump)).group(1)
    todo = [(s, n) for s, n in list_increments("legi") if stamp_dump < s <= jusqua]
    log("%d incrémentaux à relire jusqu'à %s" % (len(todo), jusqua))
    for i, (s, name) in enumerate(todo, 1):
        req = urllib.request.Request(ROOT_URL % "LEGI" + name, headers={"User-Agent": "droit-francais-skill/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            lire_archive(r, chemins)
        if i % 50 == 0:
            log("  %d/%d" % (i, len(todo)))

    changes = 0
    with open(a.sortie, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out, delimiter="\t")
        cur = con.execute("SELECT id, chemin FROM articles WHERE base='legi'")
        for aid, ancien in cur:
            nouveau = chemins.get(aid)
            if nouveau is not None and nouveau != ancien:
                w.writerow([aid, nouveau])
                changes += 1
    log("%d chemins à corriger sur %d articles relus -> %s" % (changes, len(chemins), a.sortie))
    if a.appliquer:
        appliquer(con, a.sortie)


def appliquer(con, tsv):
    con.execute("DROP TRIGGER IF EXISTS articles_au")
    with open(tsv, encoding="utf-8") as fh:
        rows = [(c, i) for i, c in csv.reader(fh, delimiter="\t")]
    con.executemany("UPDATE articles SET chemin=? WHERE id=?", rows)
    con.executescript(lc.TRIGGERS)
    con.commit()
    log("%d chemins mis à jour (chemin ne fait pas partie de l'index plein texte)" % len(rows))


if __name__ == "__main__":
    main()
