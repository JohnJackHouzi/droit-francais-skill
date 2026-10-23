import argparse
import os
import re
import sqlite3
import sys
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from juri_common import norm_numero
import eu_common as ec
from datetime import date

DATA_DIR = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
LEGI = os.path.join(DATA_DIR, "legi.sqlite")
JURI = os.path.join(DATA_DIR, "juri.sqlite")
EU = os.path.join(DATA_DIR, "eu.sqlite")

ARTICLE_URL = "https://www.legifrance.gouv.fr/codes/article_lc/"
JURI_URL = {"CETATEXT": "https://www.legifrance.gouv.fr/ceta/id/", "CONSTEXT": "https://www.legifrance.gouv.fr/cons/id/", "CNILTEXT": "https://www.legifrance.gouv.fr/cnil/id/"}
EN_VIGUEUR = ("VIGUEUR", "VIGUEUR_DIFF", "VIGUEUR_ETEN", "VIGUEUR_NON_ETEN")
NUM_FREQUENT = 500


def connect(path):
    if not os.path.exists(path):
        sys.exit(f"Base absente : {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[‘’«»“”\"'`]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_num(num):
    s = (num or "").lower().strip()
    s = re.sub(r"^(article|art)\.?\s*", "", s)
    return s.replace(" ", "").replace(" ", "").replace(".", "").replace("º", "").replace("°", "")


def article_line(r, jour):
    periode = f"du {r['date_debut']} au {r['date_fin']}" if r["date_fin"] else f"du {r['date_debut']} à ce jour"
    lien = {"LEGIARTI": ARTICLE_URL, "JORFARTI": "https://www.legifrance.gouv.fr/loda/article_lc/",
            "KALIARTI": "https://www.legifrance.gouv.fr/conv_coll/article/"}.get(r["id"][:8], "") + r["id"]
    return (f"{r['texte_titre']}, art. {r['num']} (version {periode}, "
            f"{r['etat']}) [{r['id']}] {lien}").strip()


def find_article(con, ref, jour):
    if re.fullmatch(r"(LEGIARTI|JORFARTI|KALIARTI)\d+", ref):
        return con.execute("select * from articles where id=?", (ref,)).fetchall()
    m = re.match(r"^(.*?)[\s,]+(?:art(?:icle)?\.?\s*)?([LRDA]?\.?\s?\d[\w\-\. ]*)$", ref.strip(), re.I)
    if not m:
        return []
    code, num = m.group(1).strip(" ,"), norm_num(m.group(2))
    code = re.sub(r",?\s*art(icle)?\.?$", "", code, flags=re.I).strip()
    filtre = ("and base='legi' and texte_titre like ? and date_debut<=? and (date_fin is null or date_fin>?) "
              "order by date_debut desc")
    if con.execute("select count(*) from articles where num_norm=?", (num,)).fetchone()[0] <= NUM_FREQUENT:
        return con.execute("select * from articles indexed by ix_art_num where num_norm=? " + filtre,
                           (num, f"{code}%", jour, jour)).fetchall()
    # Numéro très fréquent (« Code civil 9 ») : passer par les textes et l'index (texte_id, num_norm),
    # sinon des dizaines de milliers d'articles sont lus et le serveur dépasse son délai.
    ids = [r[0] for r in con.execute(
        "select distinct coalesce(cid, id) from textes where base='legi' and titre like ?", (f"{code}%",))]
    if not ids:
        return []
    return con.execute(
        "select * from articles indexed by ix_art_texte_num where texte_id in (%s) and num_norm=? %s"
        % (",".join("?" * len(ids)), filtre), (*ids, num, f"{code}%", jour, jour)).fetchall()


def find_decision(con, ref):
    if re.fullmatch(r"(JURITEXT|CETATEXT|CONSTEXT|CNILTEXT)\d+", ref):
        return con.execute("select * from decisions where id=?", (ref,)).fetchall()
    if ref.upper().startswith("ECLI:"):
        return con.execute("select * from decisions where ecli=?", (ref.upper(),)).fetchall()
    ref = re.sub(r"^(?:d[ée]cision|arr[êe]t|pourvoi|requ[êe]te)?\s*(?:n[o°]\.?\s*)?", "", ref.strip(), flags=re.I) or ref
    ids = [r[0] for r in con.execute("select id from numeros where num=?", (norm_numero(ref),)).fetchall()]
    court = re.sub(r"\s+(QPC|DC|LP|LOM|L|FNR|ELEC|AN|SEN|D|I|REF|ORGA|PDR|REP)$", "", ref.strip(), flags=re.I)
    if not ids and court != ref.strip():
        ids = [r[0] for r in con.execute("select id from numeros where num=?", (norm_numero(court),)).fetchall()]
    rows = []
    for i in ids[:10]:
        rows += con.execute("select * from decisions where id=?", (i,)).fetchall()
    return rows


def decision_line(r):
    prefix = re.match(r"[A-Z]+", r["id"]).group(0)
    lien = JURI_URL.get(prefix, "https://www.legifrance.gouv.fr/juri/id/") + r["id"]
    parts = [r["juridiction"], r["formation"], r["date"], f"n° {r['numero']}" if r["numero"] else None, r["ecli"]]
    return f"{', '.join(p for p in parts if p)} [{r['id']}] {lien}"


EU_REF = re.compile(r"^(?:ECLI:EU:|[CTF]-\d+/\d{2}\b|[0-9]\d{4}[A-Z]{1,2}\d{4}|1\d{4}[A-Z]/TXT)", re.I)


def find_eu(con, ref):
    """Retourne (doc, partie, num) pour une référence UE, (None, None, None) si ce n'en est pas une."""
    r = ref.strip()
    m = re.match(r"^(.*?)[\s,]+(?:art(?:icle)?\.?\s*)(premier|\d+[a-z]?(?:\s?bis)?)$", r, re.I)
    doc_ref, num = (m.group(1).strip(" ,"), m.group(2)) if m else (r, None)
    celex = ec.celex_de(doc_ref)
    if celex and re.search(r"(r[eè]glement|directive|d[eé]cision)", doc_ref, re.I) and not re.search(
            r"\((UE|CE|CEE|Euratom|PESC)\)|/(UE|CE|CEE)\b", doc_ref, re.I):
        celex = None
    if not celex and not EU_REF.match(doc_ref):
        for c in ec.candidats_numero(doc_ref):
            if con.execute("SELECT 1 FROM docs WHERE celex=?", (c,)).fetchone():
                celex = c
                break
        else:
            return None, None, None
    d = con.execute("SELECT * FROM docs WHERE celex=? OR ecli=? OR affaire=?",
                    (celex or doc_ref.upper(), doc_ref.upper(), doc_ref.upper())).fetchone()
    if d is None:
        return "absent", None, num
    p = None
    if num:
        p = con.execute("SELECT * FROM parties WHERE celex=? AND num_norm=?", (d["celex"], ec.norm_num(num))).fetchone()
    return d, p, num


def eu_line(d, p):
    titre = " ".join((d["titre"] or d["celex"]).split())
    if len(titre) > 140:
        titre = titre[:137] + "..."
    parts = [titre]
    if p is not None:
        parts.append(p["num"] + (" (" + p["titre"] + ")" if p["titre"] else ""))
    if d["affaire"]:
        parts.append("affaire " + d["affaire"])
    if d["ecli"]:
        parts.append(d["ecli"])
    version = " version consolidée au %s," % d["date_version"] if d["date_version"] else ""
    return "%s (%s%s) [CELEX %s] %s" % (", ".join(parts), version.strip(" ,") + ", " if version else "",
                                        d["date"] or "", d["celex"], ec.lien(d["celex"]))


def check_quote(text, quote):
    return fold(quote) in fold(text)


def main():
    ap = argparse.ArgumentParser(
        description="Vérifie que chaque référence juridique citée existe dans les bases locales et imprime la citation canonique.")
    ap.add_argument("refs", nargs="+", help='"Code civil 1240", LEGIARTI..., JURITEXT..., ECLI:..., "21-21.185", "RGPD art. 17", "C-131/12"')
    ap.add_argument("--date", default=date.today().isoformat(), help="date de référence AAAA-MM-JJ (défaut : aujourd'hui)")
    ap.add_argument("--quote", action="append", default=[], help="extrait censé figurer dans la référence (vérifié mot pour mot, accents et casse ignorés)")
    args = ap.parse_args()

    legi, juri = connect(LEGI), (connect(JURI) if os.path.exists(JURI) else None)
    eu = connect(EU) if os.path.exists(EU) else None
    echec = False
    for i, ref in enumerate(args.refs):
        quote = (args.quote[i] if i < len(args.quote) else None) or None
        if eu is not None:
            d, p, num = find_eu(eu, ref)
            if d == "absent" or (d is not None and num and p is None):
                print(f"[INTROUVABLE] {ref} : absent de la base UE, ne pas citer cette référence")
                echec = True
                continue
            if d is not None:
                print(f"[OK] {eu_line(d, p)}")
                if quote is not None:
                    if p is not None:
                        texte = p["contenu"]
                    else:
                        texte = "\n".join(r[0] for r in eu.execute("SELECT contenu FROM parties WHERE celex=?", (d["celex"],)))
                    ok = check_quote(texte, quote)
                    print(f"       citation {'TROUVÉE' if ok else 'ABSENTE'}")
                    echec |= not ok
                continue
        arts = find_article(legi, ref, args.date)
        decs = [] if arts or juri is None else find_decision(juri, ref)
        if arts:
            r = arts[0]
            statut = "OK"
            if args.date == date.today().isoformat() and r["etat"] not in EN_VIGUEUR:
                statut = "ATTENTION non en vigueur aujourd'hui"
            print(f"[{statut}] {article_line(r, args.date)}")
            if len(arts) > 1:
                print(f"       {len(arts)} articles correspondent, vérifier le texte visé : {', '.join(a['texte_titre'] for a in arts[:4])}")
            if quote is not None:
                ok = check_quote(r["contenu"], quote)
                print(f"       citation {'TROUVÉE' if ok else 'ABSENTE'} dans l'article")
                echec |= not ok
        elif decs:
            r = decs[0]
            print(f"[OK] {decision_line(r)}")
            if quote is not None:
                ok = check_quote(f"{r['sommaire'] or ''} {r['contenu'] or ''}", quote)
                print(f"       citation {'TROUVÉE' if ok else 'ABSENTE'} dans la décision")
                echec |= not ok
        else:
            print(f"[INTROUVABLE] {ref} : ne pas citer cette référence")
            echec = True
    sys.exit(1 if echec else 0)


if __name__ == "__main__":
    main()
