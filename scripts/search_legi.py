#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import textwrap
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legi_common as lc

BASE = "https://www.legifrance.gouv.fr"

ALIASES = {
    "cc": "Code civil", "cp": "Code pénal", "cpc": "Code de procédure civile",
    "cpp": "Code de procédure pénale", "ct": "Code du travail",
    "csp": "Code de la santé publique", "css": "Code de la sécurité sociale",
    "cgi": "Code général des impôts", "lpf": "Livre des procédures fiscales",
    "ccom": "Code de commerce", "com": "Code de commerce",
    "conso": "Code de la consommation", "cmf": "Code monétaire et financier",
    "cja": "Code de justice administrative", "cpi": "Code de la propriété intellectuelle",
    "cu": "Code de l'urbanisme", "cch": "Code de la construction et de l'habitation",
    "cesedA".lower(): "Code de l'entrée et du séjour des étrangers et du droit d'asile",
    "casf": "Code de l'action sociale et des familles", "ce": "Code de l'environnement",
    "cdc": "Code des communes", "cgct": "Code général des collectivités territoriales",
    "crpa": "Code des relations entre le public et l'administration",
    "cpce": "Code des postes et des communications électroniques",
    "cass": "Code des assurances", "ced": "Code de l'éducation",
    "cr": "Code rural et de la pêche maritime", "cj": "Code de justice militaire",
}

NUM_TOKEN = re.compile(
    r"^(?:[LRDA]\.?\s*)?\d+(?:[-\.]\d+)*(?:\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|"
    r"decies|undecies|duodecies|terdecies|quaterdecies|quindecies|sexdecies|septdecies|octodecies|"
    r"novodecies|vicies|[A-Z]))*$", re.I)


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def link_article(row):
    base, nature = row["base"], (row["texte_nature"] or "")
    i = row["id"]
    if base == "legi":
        return "%s/%s/article_lc/%s" % (BASE, "codes" if nature.upper() == "CODE" else "loda", i)
    if base == "jorf":
        return "%s/loda/article_lc/%s" % (BASE, i)
    return "%s/conv_coll/article/%s" % (BASE, i)


def link_texte(tid, base, nature):
    if tid.startswith("KALI"):
        return "%s/conv_coll/id/%s" % (BASE, tid)
    if tid.startswith("JORF"):
        return "%s/jorf/id/%s" % (BASE, tid)
    return "%s/%s/%s/%s" % (BASE, "codes" if (nature or "").upper() == "CODE" else "loda",
                            "texte_lc" if (nature or "").upper() == "CODE" else "id", tid)


def natural_key(s):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


def fmt_dates(row):
    d, f = row["date_debut"], row["date_fin"]
    return "du %s au %s" % (d or "date inconnue", f) if f else "du %s à ce jour" % (d or "date inconnue")


def wrap(text, width=110):
    out = []
    for line in (text or "").split("\n"):
        out.append(textwrap.fill(line, width) if len(line) > width else line)
    return "\n".join(out)


def open_db(args):
    path = os.path.expanduser(args.db or lc.DB_PATH)
    if not os.path.exists(path):
        sys.exit("Base introuvable: %s (lancer scripts/build_legi.py)" % path)
    return lc.connect(path, readonly=True)


def valid_date(s):
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        sys.exit("Date invalide (attendu YYYY-MM-DD): %s" % s)
    return s


def date_clause(date, alias="a"):
    p = alias + "." if alias else ""
    return ("(%sdate_debut IS NULL OR %sdate_debut <= ?) AND (%sdate_fin IS NULL OR ? < %sdate_fin)"
            % (p, p, p, p), [date, date])


def resolve_textes(con, name, bases=("legi",), strict_code=False):
    """Retourne la liste des lignes de textes correspondant à un nom, un id, un NOR, un IDCC."""
    raw = name.strip()
    m = re.match(r"^(?:idcc[\s:]*)?(\d{1,5})$", raw, re.I)
    if m and (raw.lower().startswith("idcc") or len(raw) <= 4 and "kali" in bases):
        rows = con.execute("SELECT * FROM conteneurs WHERE CAST(idcc AS INTEGER) = ?", (int(m.group(1)),)).fetchall()
        if rows:
            return [("conteneur", r) for r in rows]
    if re.match(r"^(LEGI|JORF|KALI)(TEXT|CONT)\d{12}$", raw):
        if "CONT" in raw:
            r = con.execute("SELECT * FROM conteneurs WHERE id = ?", (raw,)).fetchone()
            return [("conteneur", r)] if r else []
        rows = con.execute("SELECT * FROM textes WHERE id = ? OR cid = ? ORDER BY base='legi' DESC", (raw, raw)).fetchall()
        return [("texte", r) for r in rows]
    if re.match(r"^[A-Z]{4}\d{7}[A-Z]$", raw):
        rows = con.execute("SELECT * FROM textes WHERE nor = ?", (raw,)).fetchall()
        if rows:
            return [("texte", r) for r in rows]
    f = fold(raw)
    f = ALIASES.get(f, None) and fold(ALIASES[f]) or f
    codes = con.execute("SELECT * FROM textes WHERE base='legi' AND nature='CODE'").fetchall()
    exact, loose = [], []
    for r in codes:
        names = {fold(r["titrefull"]), fold(r["titre"])}
        t = r["titre"] or ""
        if "," in t:
            names.add(fold(t.split(",")[-1].strip(" .")))
            names.add(fold(t.rsplit(",", 1)[0]))
        if f in names:
            exact.append(r)
        elif f and f in fold(r["titrefull"] or r["titre"]):
            loose.append(r)
    pool = exact or loose
    if pool:
        vig = [r for r in pool if (r["etat"] or "").startswith("VIGUEUR")]
        return [("texte", r) for r in (vig or pool)]
    if strict_code:
        return []
    like = "%" + f.replace(" ", "%") + "%"
    rows = con.execute(
        "SELECT * FROM textes WHERE base IN (%s) AND (lower(titrefull) LIKE ? OR lower(titre) LIKE ? OR num = ?) "
        "ORDER BY base='legi' DESC, etat LIKE 'VIGUEUR%%' DESC, date_texte DESC LIMIT 25"
        % ",".join("?" * len(bases)), (*bases, like, like, raw)).fetchall()
    return [("texte", r) for r in rows]


def texte_ids(entries):
    ids = []
    for kind, r in entries:
        if kind == "texte":
            ids.append(r["cid"] or r["id"])
    return ids


def print_article(row, full=True, extra=None, all_liens=False):
    print("=" * 100)
    titre = row["texte_titre"] or ""
    print("%s - article %s" % (titre, row["num"] or "(sans numéro)"))
    print("ID Légifrance : %s" % row["id"])
    print("Version       : %s | état : %s" % (fmt_dates(row), row["etat"] or "non renseigné"))
    if row["chemin"]:
        print("Chemin        : %s" % row["chemin"])
    if row["idcc"]:
        print("IDCC          : %s" % row["idcc"])
    if row["titre_art"]:
        print("Titre         : %s" % row["titre_art"])
    print("Lien          : %s" % link_article(row))
    if extra:
        print(extra)
    print("-" * 100)
    if full:
        print(wrap(row["contenu"]) or "(contenu vide dans la base)")
        if row["nota"]:
            print("\nNota : " + wrap(row["nota"]))
        if row["liens"]:
            try:
                liens = json.loads(row["liens"])
            except ValueError:
                liens = []
            kinds = None if all_liens else ("MODIFIE", "ABROGE", "ABROGE_PARTIELLEMENT", "CREE", "CODIFIE",
                                             "TRANSFERE", "DEPLACE", "ANNULE", "REMPLACE", "PEREMPTION")
            shown = [l for l in liens if kinds is None or l[0] in kinds]
            if shown:
                print("\nLiens (historique des modifications ; --liens pour tout afficher) :" if not all_liens else "\nLiens :")
                for l in shown[:12]:
                    print("  - %s [%s] %s %s" % (l[0], l[1], l[2], l[4]))
                if len(shown) > 12:
                    print("  ... %d autres liens" % (len(shown) - 12))


def cmd_article(args):
    con = open_db(args)
    target = list(args.ref)
    if len(target) == 1 and re.match(r"^(LEGI|JORF|KALI)ARTI\d{12}$", target[0]):
        row = con.execute("SELECT * FROM articles WHERE id = ?", (target[0],)).fetchone()
        if not row:
            sys.exit("Article introuvable: %s" % target[0])
        print_article(row)
        siblings = con.execute("SELECT * FROM articles WHERE lignee = ? ORDER BY date_debut", (row["lignee"],)).fetchall()
        if len(siblings) > 1:
            print("\nToutes les versions de cet article :")
            for s in siblings:
                print("  %s  %-30s %s" % (s["id"], fmt_dates(s), s["etat"]))
        return
    code, num = None, None
    if len(target) >= 2:
        code, num = target[0], " ".join(target[1:])
        if NUM_TOKEN.match(target[0].strip()) and not NUM_TOKEN.match(num.strip()):
            code, num = num, target[0]
    else:
        code, num = split_single(target[0])
    if not code or not num:
        sys.exit("Usage: article \"Code civil\" 1240   (ou: article \"article 1240 du code civil\")")
    bases = ("legi", "kali", "jorf")
    entries = resolve_textes(con, code, bases)
    entries = [e for e in entries if e[0] == "texte" or e[0] == "conteneur"]
    ids = []
    for kind, r in entries:
        if kind == "conteneur":
            ids.extend(x["texte_id"] for x in con.execute("SELECT texte_id FROM conteneur_textes WHERE conteneur_id=?", (r["id"],)))
        else:
            ids.append(r["cid"] or r["id"])
    if not ids:
        sys.exit("Texte ou code introuvable: %s. Voir la sous-commande « codes ».\n" % code)
    if len(entries) > 1 and all(k == "texte" for k, _ in entries) and len(ids) > 1:
        shown = [r for _, r in entries][:8]
        print("Plusieurs textes correspondent à « %s » :" % code)
        for r in shown:
            print("  %s  %s (%s)" % (r["id"], r["titrefull"] or r["titre"], r["etat"]))
    nn = lc.norm_num(num)
    marks = ",".join("?" * len(ids))
    sql = "SELECT * FROM articles WHERE texte_id IN (%s) AND num_norm = ?" % marks
    params = list(ids) + [nn]
    if not args.versions:
        date = valid_date(args.date) if args.date else datetime.date.today().isoformat()
        cl, cp = date_clause(date, "")
        rows = con.execute(sql + " AND " + cl + " ORDER BY texte_id, date_debut", params + cp).fetchall()
    else:
        rows = con.execute(sql + " ORDER BY texte_id, date_debut", params).fetchall()
    if not rows:
        allv = con.execute(sql + " ORDER BY date_debut", params).fetchall()
        if not allv:
            print("Aucun article « %s » trouvé dans %s." % (num, code))
            sugg = con.execute("SELECT DISTINCT num FROM articles WHERE texte_id IN (%s) AND num_norm LIKE ? LIMIT 10" % marks,
                               list(ids) + [nn + "%"]).fetchall()
            if sugg:
                print("Numéros proches : " + ", ".join(s["num"] for s in sugg))
            sys.exit(1)
        print("Aucune version en vigueur le %s. Versions connues :" % (args.date or "aujourd'hui"))
        for s in allv:
            print("  %s  %-34s %s" % (s["id"], fmt_dates(s), s["etat"]))
        return
    for r in rows:
        extra = None
        if not args.versions:
            n = con.execute("SELECT count(*) FROM articles WHERE lignee = ?", (r["lignee"],)).fetchone()[0]
            extra = "Date de lecture : %s (%d version(s) connue(s), option --versions pour les lister)" % (
                args.date or datetime.date.today().isoformat() + " (aujourd'hui)", n)
        print_article(r, extra=extra, all_liens=args.liens)
    if args.versions:
        print("\n%d version(s) listées ci-dessus." % len(rows))


def split_single(s):
    s = s.strip()
    m = re.match(r"^(?:l'?\s*)?(?:art(?:icle)?s?\.?\s+)?(.+?)\s+(?:du|de la|de l'|des|dans le|dans la|d')\s*(.+)$", s, re.I)
    if m and NUM_TOKEN.match(m.group(1).strip()):
        return m.group(2).strip(), m.group(1).strip()
    m = re.match(r"^(.+?)[\s,]+(?:art(?:icle)?\.?\s*)?((?:[LRDA]\.?\s*)?\d[\d\-\.]*(?:\s+(?:bis|ter|quater|quinquies))?)$", s, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


STOPWORDS = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "a", "au", "aux", "un", "une", "en", "que",
             "qui", "qu", "par", "pour", "sur", "dans", "ce", "ces", "se", "sa", "son", "ses", "il", "elle", "est",
             "ou", "ne", "pas", "s", "n", "y", "c", "j", "m", "t"}


def build_fts_query(q, exact=False, any_word=False):
    if exact:
        return q
    parts = re.findall(r'"[^"]+"|\S+', q)
    terms, empty = [], []
    for p in parts:
        if p.startswith('"') and p.endswith('"') and len(p) > 2:
            terms.append('"%s"' % p[1:-1].replace('"', ""))
            continue
        for w in re.findall(r"[\w]+(?:-[\w]+)*", p, re.UNICODE):
            w = w.replace('"', "")
            if not w:
                continue
            term = '"%s"*' % w if len(w) >= 5 else '"%s"' % w
            (empty if fold(w) in STOPWORDS else terms).append(term)
    terms = terms or empty
    if not terms:
        sys.exit("Requête vide.")
    return (" OR " if any_word else " AND ").join(terms)


def cmd_recherche(args):
    con = open_db(args)
    match = build_fts_query(args.q, args.exact, args.ou)
    where, params = ["articles_fts MATCH ?"], [match]
    if args.base != "tout":
        bases = [b.strip() for b in args.base.split(",")]
        where.append("a.base IN (%s)" % ",".join("?" * len(bases)))
        params += bases
    if args.code:
        entries = resolve_textes(con, args.code, ("legi", "kali", "jorf"))
        ids = []
        for kind, r in entries:
            if kind == "conteneur":
                ids.extend(x["texte_id"] for x in con.execute("SELECT texte_id FROM conteneur_textes WHERE conteneur_id=?", (r["id"],)))
            else:
                ids.append(r["cid"] or r["id"])
        if not ids:
            sys.exit("Code ou texte introuvable: %s" % args.code)
        where.append("a.texte_id IN (%s)" % ",".join("?" * len(ids)))
        params += ids
    if args.idcc:
        where.append("CAST(a.idcc AS INTEGER) = ?")
        params.append(int(args.idcc))
    if args.toutes_versions:
        label = "toutes versions"
    else:
        date = valid_date(args.date) if args.date else datetime.date.today().isoformat()
        cl, cp = date_clause(date)
        where.append(cl)
        params += cp
        label = "en vigueur au %s" % date
    sql = ("SELECT a.*, snippet(articles_fts, 0, '**', '**', ' ... ', 32) AS snip, "
           "bm25(articles_fts, 1.0, 6.0, 3.0, 3.0) AS score "
           "FROM articles_fts JOIN articles a ON a.rowid = articles_fts.rowid WHERE " + " AND ".join(where) +
           " ORDER BY score LIMIT ?")
    try:
        rows = con.execute(sql, params + [args.limit]).fetchall()
    except sqlite3.OperationalError as exc:
        sys.exit("Requête FTS invalide (%s). Requête envoyée : %s" % (exc, match))
    print("Recherche : %s   [%s ; base : %s]" % (match, label, args.base))
    if not rows:
        print("Aucun résultat. Essayez --base tout, --toutes-versions, --ou, ou moins de mots.")
        return
    for i, r in enumerate(rows, 1):
        print("\n[%d] %s - art. %s" % (i, r["texte_titre"], r["num"] or "?"))
        print("    ID : %s | %s | état : %s" % (r["id"], fmt_dates(r), r["etat"]))
        if r["chemin"]:
            print("    Chemin : %s" % r["chemin"][:200])
        print("    Lien : %s" % link_article(r))
        print("    " + " ".join((r["snip"] or "").split()))
    print("\n%d résultat(s) affichés (limite %d)." % (len(rows), args.limit))


def cmd_codes(args):
    con = open_db(args)
    rows = con.execute(
        "SELECT t.*, (SELECT count(*) FROM articles a WHERE a.texte_id = t.cid) AS n_all, "
        "(SELECT count(*) FROM articles a WHERE a.texte_id = t.cid AND (a.date_fin IS NULL) AND a.etat LIKE 'VIGUEUR%') AS n_vig "
        "FROM textes t WHERE t.base='legi' AND t.nature='CODE' ORDER BY t.etat LIKE 'VIGUEUR%' DESC, t.titrefull").fetchall()
    flt = fold(args.filtre) if args.filtre else None
    shown = 0
    for r in rows:
        name = r["titrefull"] or r["titre"]
        if flt and flt not in fold(name):
            continue
        shown += 1
        print("%s | %s | état : %s | %d articles en vigueur / %d versions | modif. %s" % (
            r["id"], name, r["etat"], r["n_vig"], r["n_all"], r["derniere_modif"] or "?"))
        print("    %s" % link_texte(r["id"], "legi", "CODE"))
    print("\n%d code(s)." % shown)


def cmd_texte(args):
    con = open_db(args)
    entries = resolve_textes(con, args.ref, ("legi", "jorf", "kali"))
    if not entries:
        sys.exit("Texte introuvable: %s" % args.ref)
    if len(entries) > 1 and not args.premier:
        print("Plusieurs correspondances (préciser l'ID, ou --premier) :")
        for kind, r in entries[:25]:
            if kind == "conteneur":
                print("  %s | IDCC %s | %s" % (r["id"], r["idcc"], r["titre"]))
            else:
                print("  %s | %s | %s | %s" % (r["id"], r["nature"], (r["titrefull"] or r["titre"] or "")[:110], r["etat"]))
        return
    kind, r = entries[0]
    if kind == "conteneur":
        print("=" * 100)
        print("IDCC %s - %s" % (r["idcc"], r["titre"]))
        print("ID Légifrance : %s | état : %s | publication : %s" % (r["id"], r["etat"], r["date_publi"]))
        print("Lien : %s/conv_coll/id/%s" % (BASE, r["id"]))
        print("-" * 100)
        lines = con.execute("SELECT ct.rubrique, ct.texte_id, ct.titre, t.nature, t.date_texte, t.etat, "
                            "(SELECT count(*) FROM articles a WHERE a.texte_id = ct.texte_id) AS n "
                            "FROM conteneur_textes ct LEFT JOIN textes t ON t.id = ct.texte_id "
                            "WHERE ct.conteneur_id = ? ORDER BY ct.rubrique, t.date_texte", (r["id"],)).fetchall()
        last = None
        for l in lines:
            if l["rubrique"] != last:
                print("\n## %s" % l["rubrique"])
                last = l["rubrique"]
            print("  %s | %s | %s | %s | %d art. | %s" % (l["texte_id"], l["nature"], l["date_texte"], l["etat"], l["n"], (l["titre"] or "")[:90]))
        print("\n%d texte(s) rattaché(s)." % len(lines))
        return
    print("=" * 100)
    print(r["titrefull"] or r["titre"])
    print("ID Légifrance : %s%s" % (r["id"], " (texte d'origine : %s)" % r["cid"] if r["cid"] != r["id"] else ""))
    for label, key in (("Nature", "nature"), ("État", "etat"), ("NOR", "nor"), ("Numéro", "num"),
                       ("Date du texte", "date_texte"), ("Publication", "date_publi"),
                       ("Origine publi.", "origine_publi"), ("En vigueur depuis", "date_debut"),
                       ("Fin de vigueur", "date_fin"), ("Dernière modif.", "derniere_modif"),
                       ("Ministère", "ministere"), ("ELI", "eli"), ("IDCC", "idcc"), ("Extension", "extension")):
        if r[key]:
            print("%-17s: %s" % (label, r[key]))
    print("Lien          : %s" % link_texte(r["id"], r["base"], r["nature"]))
    if args.visas and r["visas"]:
        print("\nVisas :\n" + wrap(r["visas"]))
    if args.visas and r["nota"]:
        print("\nNota :\n" + wrap(r["nota"]))
    tid = r["cid"] or r["id"]
    date = valid_date(args.date) if args.date else datetime.date.today().isoformat()
    cl, cp = date_clause(date, "")
    if r["base"] == "jorf":
        cl, cp = "1=1", []
    rows = con.execute("SELECT * FROM articles WHERE texte_id = ? AND " + cl, [tid] + cp).fetchall()
    rows.sort(key=lambda a: natural_key(a["num"]))
    total = con.execute("SELECT count(*) FROM articles WHERE texte_id = ?", (tid,)).fetchone()[0]
    print("\n%d article(s) applicable(s) le %s (%d versions au total dans la base)." % (
        len(rows), "date de publication" if r["base"] == "jorf" else date, total))
    if args.contenu:
        sel = rows
        if args.articles:
            wanted = {lc.norm_num(x) for x in args.articles.split(",")}
            sel = [a for a in rows if a["num_norm"] in wanted]
        for a in sel[: args.limit]:
            print_article(a)
        if len(sel) > args.limit:
            print("\n... %d articles supplémentaires (augmenter --limit)." % (len(sel) - args.limit))
        return
    depth = args.profondeur
    sections = {}
    for a in rows:
        key = " > ".join((a["chemin"] or "(sans section)").split(" > ")[:depth])
        sections.setdefault(key, []).append(a["num"])
    print("\nPlan (profondeur %d) :" % depth)
    for k in list(sections)[: args.limit * 5]:
        nums = sorted(sections[k], key=natural_key)
        rng = nums[0] if len(nums) == 1 else "%s à %s" % (nums[0], nums[-1])
        print("  - %s  [%d art. : %s]" % (k, len(nums), rng))
    print("\nPour lire les articles : texte %s --contenu [--articles L1221-1,L1221-2] [--limit N]" % r["id"])


def cmd_textes(args):
    con = open_db(args)
    where, params = [], []
    if args.q:
        where.append("textes.rowid IN (SELECT rowid FROM textes_fts WHERE textes_fts MATCH ?)")
        params.append(build_fts_query(args.q))
    if args.nature:
        where.append("upper(nature) = ?")
        params.append(args.nature.upper())
    if args.nor:
        where.append("nor = ?")
        params.append(args.nor.upper())
    if args.base != "tout":
        where.append("base = ?")
        params.append(args.base)
    if not where:
        sys.exit("Donner --q, --nature ou --nor")
    rows = con.execute("SELECT * FROM textes WHERE " + " AND ".join(where) +
                       " ORDER BY date_texte DESC LIMIT ?", params + [args.limit]).fetchall()
    for r in rows:
        print("%s | %s | %s | %s | NOR %s" % (r["id"], r["nature"], r["date_texte"] or r["date_publi"] or "?", r["etat"] or "-", r["nor"] or "-"))
        print("    %s" % (r["titrefull"] or r["titre"]))
        print("    %s" % link_texte(r["id"], r["base"], r["nature"]))
    print("\n%d texte(s)." % len(rows))


def cmd_stats(args):
    con = open_db(args)
    for b, n in con.execute("SELECT base, count(*) FROM articles GROUP BY base"):
        print("articles %-5s : %d" % (b, n))
    for b, n in con.execute("SELECT base, count(*) FROM textes GROUP BY base"):
        print("textes   %-5s : %d" % (b, n))
    print("codes LEGI       : %d" % con.execute("SELECT count(*) FROM textes WHERE base='legi' AND nature='CODE'").fetchone()[0])
    print("conventions KALI : %d conteneurs" % con.execute("SELECT count(*) FROM conteneurs").fetchone()[0])
    for k, v in con.execute("SELECT k, v FROM meta ORDER BY k"):
        print("%s = %s" % (k, v))


def main():
    ap = argparse.ArgumentParser(description="Recherche dans la base législative locale (Légifrance open data)")
    ap.add_argument("--db", help="chemin de legi.sqlite (défaut ~/droit-francais-data/legi.sqlite)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("article", help='article "Code civil" 1240 [--date YYYY-MM-DD] [--versions]')
    p.add_argument("ref", nargs="+", help='code puis numéro, ou ID LEGIARTI, ou phrase unique')
    p.add_argument("--date")
    p.add_argument("--versions", action="store_true", help="toutes les versions avec leurs dates")
    p.add_argument("--liens", action="store_true", help="afficher tous les liens (citations incluses)")
    p.set_defaults(fn=cmd_article)

    for name in ("recherche", "search"):
        p = sub.add_parser(name, help='plein texte: recherche --q "préavis démission" [--code "Code du travail"]')
        p.add_argument("--q", required=True)
        p.add_argument("--code", help="code, texte, NOR, ID ou « IDCC 1486 »")
        p.add_argument("--idcc")
        p.add_argument("--base", default="legi", help="legi (défaut), kali, jorf, ou tout")
        p.add_argument("--date", help="version en vigueur à cette date (défaut aujourd'hui)")
        p.add_argument("--toutes-versions", action="store_true")
        p.add_argument("--limit", type=int, default=10)
        p.add_argument("--ou", action="store_true", help="un seul des mots suffit")
        p.add_argument("--exact", action="store_true", help="requête FTS5 brute")
        p.set_defaults(fn=cmd_recherche)

    p = sub.add_parser("texte", help="texte <id|NOR|IDCC|nom> : fiche, plan, articles")
    p.add_argument("ref")
    p.add_argument("--date")
    p.add_argument("--contenu", action="store_true")
    p.add_argument("--articles", help="numéros séparés par des virgules (avec --contenu)")
    p.add_argument("--visas", action="store_true")
    p.add_argument("--profondeur", type=int, default=2)
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--premier", action="store_true", help="prendre la première correspondance")
    p.set_defaults(fn=cmd_texte)

    p = sub.add_parser("textes", help="trouver un texte par titre, nature ou NOR")
    p.add_argument("--q")
    p.add_argument("--nature")
    p.add_argument("--nor")
    p.add_argument("--base", default="tout")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(fn=cmd_textes)

    p = sub.add_parser("codes", help="lister les codes")
    p.add_argument("filtre", nargs="?")
    p.set_defaults(fn=cmd_codes)

    p = sub.add_parser("stats", help="comptes de la base")
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args.fn(args)


if __name__ == "__main__":
    main()
