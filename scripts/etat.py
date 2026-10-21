#!/usr/bin/env python3
"""État des bases : comptes, dates des dumps et des derniers incrémentaux appliqués."""
import json
import os
import sqlite3
import sys

DATA = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
MARKER = os.path.join(DATA, ".installation-en-cours")
BASES = {
    "legi.sqlite": ("articles_fts_docsize", "SELECT base, count(*) FROM articles GROUP BY base", "SELECT k, v FROM meta"),
    "juri.sqlite": ("decisions_fts_docsize", "SELECT base, count(*) FROM decisions GROUP BY base", "SELECT cle, valeur FROM meta"),
    "eu.sqlite": ("parties_fts_docsize", "SELECT type, count(*) FROM docs GROUP BY type", "SELECT k, v FROM meta"),
}
OBLIGATOIRES = ("legi.sqlite", "juri.sqlite")


def lire(nom, comptes=True):
    chemin = os.path.join(DATA, nom)
    fts, q_comptes, q_meta = BASES[nom]
    if not os.path.exists(chemin):
        return {"present": False}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % chemin, uri=True, timeout=10)
        pret = con.execute("SELECT 1 FROM %s LIMIT 1" % fts).fetchone() is not None
        info = {"present": True, "pret": pret, "meta": dict(con.execute(q_meta).fetchall())}
        if comptes and pret:
            info["comptes"] = dict(con.execute(q_comptes).fetchall())
        con.close()
        return info
    except sqlite3.Error as exc:
        return {"present": True, "pret": False, "erreur": str(exc)}


def etat(comptes=True):
    bases = {n: lire(n, comptes) for n in BASES}
    installation = os.path.exists(MARKER)
    pret = not installation and all(bases[n].get("pret") for n in OBLIGATOIRES)
    return {"pret": pret, "installation_en_cours": installation, "bases": bases}


def main():
    e = etat(comptes="--rapide" not in sys.argv)
    if "--json" in sys.argv:
        print(json.dumps(e, ensure_ascii=False))
        return
    print("Bases prêtes : %s%s" % ("oui" if e["pret"] else "non",
                                  " (installation en cours)" if e["installation_en_cours"] else ""))
    for nom, b in e["bases"].items():
        if not b.get("present"):
            print("\n%s : absente" % nom)
            continue
        print("\n%s%s" % (nom, "" if b.get("pret") else " : PAS PRÊTE " + b.get("erreur", "(index plein texte absent)")))
        for k, v in sorted((b.get("comptes") or {}).items()):
            print("  %-8s %d" % (k, v))
        for k, v in sorted((b.get("meta") or {}).items()):
            print("  %s = %s" % (k, v))


if __name__ == "__main__":
    main()
