#!/usr/bin/env python3
"""Liens entre droit de l'UE et droit français (liens.sqlite, construit par build_liens.py).

  search_liens.py ue "directive 2019/770"          textes et articles français liés à un acte européen
  search_liens.py ue RGPD --source mention         seulement les articles qui le citent
  search_liens.py fr "Code de la consommation" L217-4   actes européens liés à un article français
  search_liens.py fr JORFTEXT000043...              actes européens liés à un texte (loi, ordonnance, décret)
"""
import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eu_common as ec
import legi_common as lc

DATA_DIR = ec.DATA_DIR
LIENS = os.path.join(DATA_DIR, "liens.sqlite")
BASE = "https://www.legifrance.gouv.fr"
SOURCES = {"transposition": "Transposition déclarée à l'Union (EUR-Lex, mesures nationales d'exécution)",
           "mention": "Article français qui cite expressément l'acte"}


def ouvrir(chemin):
    if not os.path.exists(chemin):
        sys.exit("Base des liens introuvable : %s (lancer scripts/build_liens.py)" % chemin)
    con = sqlite3.connect("file:%s?mode=ro" % chemin, uri=True)
    con.row_factory = sqlite3.Row
    return con


def natures(legi, ids):
    out = {}
    for i in ids:
        r = legi.execute("SELECT nature FROM textes WHERE id=?", (i,)).fetchone()
        out[i] = (r["nature"] or "").upper() if r else ""
    return out


def lien_legifrance(row, nature):
    i = row["cible_id"]
    if row["cible_type"] == "article":
        return "%s/%s/article_lc/%s" % (BASE, "codes" if nature == "CODE" else "loda", i)
    if i.startswith("JORF"):
        return "%s/jorf/id/%s" % (BASE, i)
    return "%s/%s/%s/%s" % (BASE, "codes" if nature == "CODE" else "loda", "texte_lc" if nature == "CODE" else "id", i)


def titre_acte(eu, celex):
    r = eu.execute("SELECT titre, type, en_vigueur FROM docs WHERE celex=?", (celex,)).fetchone()
    return (r["titre"], r["type"], r["en_vigueur"]) if r else (None, None, None)


def cmd_ue(a, liens, legi, eu):
    celex = ec.celex_de(a.reference)
    if not celex:
        sys.exit("Acte européen non reconnu : %s (CELEX, alias RGPD/DSA/RIA, « directive 93/13/CEE »...)" % a.reference)
    titre, typ, vig = titre_acte(eu, celex)
    print("=" * 100)
    print("%s | CELEX %s" % (titre or "acte absent de la base européenne", celex))
    print("Lien : " + ec.lien(celex))
    cond, args = "celex = ?", [celex]
    if a.source:
        cond += " AND source = ?"
        args.append(a.source)
    rows = liens.execute("SELECT * FROM liens WHERE %s ORDER BY source DESC, cible_type, texte_titre, num" % cond, args).fetchall()
    if not rows:
        print("\nAucun lien trouvé. Les règlements ne sont pas « transposés » : chercher les articles qui les citent "
              "avec rechercher_loi. Les directives non listées n'ont pas de transposition déclarée dans cette base.")
        return
    nat = natures(legi, {r["texte_id"] for r in rows if r["texte_id"]})
    for source in ("transposition", "mention"):
        sel = [r for r in rows if r["source"] == source]
        if not sel:
            continue
        print("\n## %s (%d)" % (SOURCES[source], len(sel)))
        textes = [r for r in sel if r["cible_type"] == "texte"]
        for r in textes[:a.limite]:
            print("- %s [%s] %s" % (r["texte_titre"], r["etat"], lien_legifrance(r, nat.get(r["texte_id"], ""))))
        groupes = {}
        for r in (r for r in sel if r["cible_type"] == "article"):
            groupes.setdefault(r["texte_titre"], []).append(r)
        ordre = sorted(groupes.items(), key=lambda kv: (nat.get(kv[1][0]["texte_id"], "") != "CODE", -len(kv[1]), kv[0]))
        for nom, lst in ordre[:a.limite]:
            nums = ", ".join(sorted({r["num"] for r in lst}, key=lc_natural)[:a.limite * 3])
            print("- %s : art. %s%s" % (nom, nums, " ..." if len({r["num"] for r in lst}) > a.limite * 3 else ""))
            for r in lst[:a.exemples]:
                print("    %s art. %s [%s] %s" % ("→", r["num"], r["etat"], lien_legifrance(r, nat.get(r["texte_id"], ""))))
                if source == "mention":
                    print("      « ... %s ... »" % r["detail"])


def lc_natural(s):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


def cmd_fr(a, liens, legi, eu):
    ref = a.reference.strip()
    ids = []
    if re.match(r"^(LEGI|JORF|KALI)(TEXT|ARTI)\d{12}$", ref):
        ids = [ref]
        par_texte = ref
    elif a.numero:
        import search_legi as sl
        entrees = sl.resolve_textes(legi, ref, strict_code=True)
        tids = sl.texte_ids(entrees)
        if not tids:
            sys.exit("Code ou texte introuvable : " + ref)
        num = lc.norm_num(a.numero)
        for t in tids:
            ids += [r["id"] for r in legi.execute(
                "SELECT id FROM articles INDEXED BY ix_art_texte_num WHERE texte_id=? AND num_norm=? AND base='legi'",
                (t, num))]
        par_texte = None
        if not ids:
            sys.exit("Article introuvable : %s %s" % (ref, a.numero))
    else:
        sys.exit("Donner un code et un numéro d'article, ou un identifiant LEGITEXT/JORFTEXT/LEGIARTI")
    marques = ",".join("?" * len(ids))
    rows = liens.execute("SELECT DISTINCT celex, source, detail, nim_celex FROM liens WHERE cible_id IN (%s) OR texte_id IN (%s) "
                         "ORDER BY source DESC, celex" % (marques, marques), ids + ids).fetchall() if ids else []
    if not rows and a.numero:
        rows = []
    print("=" * 100)
    print("%s %s : %d lien(s) avec le droit de l'Union" % (ref, a.numero or "", len({r["celex"] for r in rows})))
    if not rows:
        print("Aucun acte européen lié dans la base (ce qui ne veut pas dire qu'aucun n'existe : seules les mesures "
              "déclarées à l'Union et les citations expresses sont recensées).")
        return
    vus = set()
    for r in rows:
        if (r["celex"], r["source"]) in vus:
            continue
        vus.add((r["celex"], r["source"]))
        titre, typ, vig = titre_acte(eu, r["celex"])
        print("- [%s] %s | CELEX %s\n    %s\n    %s" % (r["source"], titre or "(titre non chargé)", r["celex"], ec.lien(r["celex"]),
                                                       (r["detail"] or "")[:200]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--liens", default=LIENS)
    ap.add_argument("--legi", default=lc.DB_PATH)
    ap.add_argument("--eu", default=ec.DB_PATH)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("ue")
    u.add_argument("reference")
    u.add_argument("--source", choices=list(SOURCES))
    u.add_argument("--limite", type=int, default=15)
    u.add_argument("--exemples", type=int, default=3)
    f = sub.add_parser("fr")
    f.add_argument("reference")
    f.add_argument("numero", nargs="?")
    a = ap.parse_args()
    liens = ouvrir(a.liens)
    legi = lc.connect(a.legi, readonly=True)
    eu = ec.connect(a.eu, readonly=True)
    (cmd_ue if a.cmd == "ue" else cmd_fr)(a, liens, legi, eu)


if __name__ == "__main__":
    main()
