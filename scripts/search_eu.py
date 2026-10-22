#!/usr/bin/env python3
"""Recherche dans eu.sqlite (droit de l'Union européenne en français, source EUR-Lex / Cellar)."""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eu_common as ec

JURI = ("JUDG", "ORDER", "OPIN_AG")


def open_db():
    if not os.path.exists(ec.DB_PATH):
        sys.exit("Base du droit de l'UE absente : %s (lancer build_eu.py)" % ec.DB_PATH)
    return ec.connect(readonly=True)


def entete(d):
    typ = ec.TYPES.get(d["type"] or "", d["type"] or "")
    lignes = [d["titre"] or d["celex"], "CELEX : %s | %s | %s%s" % (
        d["celex"], typ, d["date"] or "date inconnue",
        "" if d["en_vigueur"] is None else (" | en vigueur" if d["en_vigueur"] in ("1", "true") else " | plus en vigueur"))]
    if d["celex_version"]:
        lignes.append("Version consolidée %s (au %s) : la version officielle reste celle publiée au JOUE"
                      % (d["celex_version"], d["date_version"]))
    if d["affaire"] or d["ecli"]:
        lignes.append("Affaire %s | %s" % (d["affaire"] or "?", d["ecli"] or ""))
    lignes.append("Lien : %s" % ec.lien(d["celex"]))
    return "\n".join(lignes)


def trouver_doc(con, ref):
    r = ref.strip()
    d = con.execute("SELECT * FROM docs WHERE celex=? OR ecli=? OR affaire=?", (r.upper(), r.upper(), r.upper())).fetchone()
    if d:
        return d
    celex = ec.celex_de(r)
    if celex:
        return con.execute("SELECT * FROM docs WHERE celex=?", (celex,)).fetchone()
    for c in ec.candidats_numero(r):
        d = con.execute("SELECT * FROM docs WHERE celex=?", (c,)).fetchone()
        if d:
            return d
    return con.execute("SELECT d.* FROM docs d WHERE d.titre LIKE ? "
                       "ORDER BY d.type IN ('JUDG','ORDER','OPIN_AG','JUDG_EXTRACT'), d.date DESC LIMIT 1",
                       ("%" + r + "%",)).fetchone()


def cmd_texte(a):
    con = open_db()
    d = trouver_doc(con, a.ref)
    if not d:
        sys.exit("Texte introuvable dans la base UE : %s" % a.ref)
    print(entete(d))
    if a.article:
        p = con.execute("SELECT * FROM parties WHERE celex=? AND num_norm=?", (d["celex"], ec.norm_num(a.article))).fetchone()
        if not p and a.article.lower().startswith("annexe"):
            p = con.execute("SELECT * FROM parties WHERE celex=? AND lower(num)=?", (d["celex"], a.article.lower())).fetchone()
        if not p:
            sys.exit("\nArticle %s introuvable dans %s" % (a.article, d["celex"]))
        print("\n%s%s\n" % (p["num"], " - " + p["titre"] if p["titre"] else ""))
        print(p["contenu"][: a.max_chars])
        return
    parties = con.execute("SELECT num, titre, length(contenu) n FROM parties WHERE celex=? ORDER BY ordre", (d["celex"],)).fetchall()
    if d["type"] in JURI or a.complet:
        texte = "\n\n".join(r[0] for r in con.execute("SELECT contenu FROM parties WHERE celex=? ORDER BY ordre", (d["celex"],)))
        print("\n" + texte[: a.max_chars])
        if len(texte) > a.max_chars:
            print("\n[... tronqué à %d caractères sur %d ...]" % (a.max_chars, len(texte)))
        return
    print("\nPlan (%d parties) :" % len(parties))
    for p in parties:
        print("  %s%s" % (p["num"], " - " + p["titre"] if p["titre"] else ""))


def fts_query(q):
    if re.search(r'["*]|\b(AND|OR|NOT)\b', q):
        return q
    mots = re.findall(r"\w+", q)
    vides = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "a", "à", "au", "aux", "un", "une", "en", "que",
             "qui", "qu", "par", "pour", "sur", "dans", "ce", "ces", "se", "sa", "son", "ses", "est", "ou", "ne",
             "pas", "s", "n", "y", "c", "j", "m", "t"}
    utiles = [m for m in mots if m.lower() not in vides] or mots
    return " AND ".join('"%s"' % m for m in utiles)


def cmd_recherche(a):
    con = open_db()
    filtre, params = "", [fts_query(a.q)]
    if a.type == "actes":
        filtre += " AND d.type NOT IN ('JUDG','ORDER','OPIN_AG')"
    elif a.type == "jurisprudence":
        filtre += " AND d.type IN ('JUDG','ORDER','OPIN_AG')"
    if a.celex:
        celex = ec.celex_de(a.celex) or a.celex.upper()
        filtre += " AND d.celex = ?"
        params.append(celex)
    if a.du:
        filtre += " AND d.date >= ?"
        params.append(a.du)
    if a.au:
        filtre += " AND d.date <= ?"
        params.append(a.au)
    params.append(a.limit)
    sql = ("SELECT d.*, p.num, p.titre AS ptitre, snippet(parties_fts, 1, '**', '**', ' ... ', 40) AS extrait "
           "FROM parties_fts JOIN parties p ON p.rowid = parties_fts.rowid JOIN docs d ON d.celex = p.celex "
           "WHERE parties_fts MATCH ?%s ORDER BY %s LIMIT ?" % (filtre, "d.date DESC" if a.tri == "date" else "rank"))
    try:
        rows = []
        mots = re.findall(r"\w+", a.q)
        if len(mots) > 1 and fts_query(a.q) != a.q:
            rows = con.execute(sql, ['"%s"' % " ".join(mots)] + params[1:]).fetchall()
        if len(rows) < a.limit:
            vus = {(r["celex"], r["num"]) for r in rows}
            rows += [r for r in con.execute(sql, params).fetchall() if (r["celex"], r["num"]) not in vus]
            rows = rows[: a.limit]
    except Exception as exc:
        sys.exit("Requête invalide (%s). Syntaxe : \"phrase exacte\", AND, OR, NOT, prefixe*" % exc)
    print("Recherche UE : %s\n" % params[0])
    for i, r in enumerate(rows, 1):
        juri = r["type"] in JURI
        cible = ("affaire %s" % r["affaire"]) if juri else r["num"]
        print("[%d] %s - %s" % (i, (r["titre"] or r["celex"])[:160], cible))
        if not juri and r["ptitre"]:
            print("    %s" % r["ptitre"])
        print("    CELEX : %s | %s | %s" % (r["celex"], r["date"], r["ecli"] or ec.TYPES.get(r["type"] or "", r["type"] or "")))
        print("    Lien : %s" % ec.lien(r["celex"]))
        print("    %s\n" % " ".join((r["extrait"] or "").split()))
    print("%d résultat(s)." % len(rows))


def cmd_stats(_a):
    con = open_db()
    for t, n in con.execute("SELECT type, count(*) FROM docs GROUP BY type"):
        print("%-8s %d" % (t, n))
    for k, v in con.execute("SELECT k, v FROM meta"):
        print("%s = %s" % (k, v))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("texte", help="texte <CELEX|RGPD|« règlement (UE) 2016/679 »|C-131/12|ECLI> [--article 17]")
    p.add_argument("ref")
    p.add_argument("--article")
    p.add_argument("--complet", action="store_true")
    p.add_argument("--max-chars", type=int, default=20000)
    p.set_defaults(fn=cmd_texte)
    p = sub.add_parser("recherche", help='recherche --q "droit à l\'effacement" [--type actes|jurisprudence] [--celex RGPD]')
    p.add_argument("--q", required=True)
    p.add_argument("--type", default="tout", choices=("tout", "actes", "jurisprudence"))
    p.add_argument("--celex")
    p.add_argument("--du")
    p.add_argument("--au")
    p.add_argument("--tri", default="pertinence", choices=("pertinence", "date"))
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_recherche)
    p = sub.add_parser("stats")
    p.set_defaults(fn=cmd_stats)
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a.fn(a)


if __name__ == "__main__":
    main()
