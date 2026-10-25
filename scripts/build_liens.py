#!/usr/bin/env python3
"""Construit liens.sqlite : correspondances entre le droit de l'UE (eu.sqlite) et le droit français (legi.sqlite).

Deux sources :
  transposition  mesures nationales d'exécution déclarées par la France à l'Union (API Cellar) : texte ou articles
                 de code français indiqués comme transposant l'acte européen
  mention        articles français en vigueur qui citent expressément un règlement ou une directive

  build_liens.py                      construction complète
  build_liens.py --sans-mentions      seulement les mesures nationales (rapide, 9 600 lignes)
"""
import argparse
import os
import re
import sqlite3
import sys
import time
import unicodedata

_ici = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
sys.path.insert(0, _ici if os.path.exists(os.path.join(_ici, "build_eu.py")) else "/app/scripts")
import build_eu as be
import eu_common as ec

DATA_DIR = ec.DATA_DIR
LEGI = os.path.join(DATA_DIR, "legi.sqlite")
EU = ec.DB_PATH
LIENS = os.path.join(DATA_DIR, "liens.sqlite")
FRA = "<http://publications.europa.eu/resource/authority/country/FRA>"
EN_VIGUEUR = ("VIGUEUR", "VIGUEUR_ETEN", "VIGUEUR_NON_ETEN", "VIGUEUR_DIFF")

SCHEMA = """
CREATE TABLE IF NOT EXISTS liens (
  rowid INTEGER PRIMARY KEY,
  celex TEXT NOT NULL,
  source TEXT NOT NULL,
  cible_type TEXT NOT NULL,
  cible_id TEXT NOT NULL,
  texte_id TEXT,
  texte_titre TEXT,
  num TEXT,
  etat TEXT,
  detail TEXT,
  nim_celex TEXT,
  UNIQUE (celex, source, cible_id)
);
CREATE INDEX IF NOT EXISTS ix_liens_celex ON liens(celex);
CREATE INDEX IF NOT EXISTS ix_liens_cible ON liens(cible_id);
CREATE INDEX IF NOT EXISTS ix_liens_texte ON liens(texte_id, num);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def log(msg):
    print(time.strftime("%H:%M:%S"), "liens", msg, flush=True)


def plier(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def natural_key(s):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s or "")]


def mesures_nationales():
    q = be.PFX + """SELECT ?dir ?nimc ?num ?type ?date ?titre WHERE {
  ?n cdm:measure_national_implementing_implemented_by_country %s ;
     cdm:measure_national_implementing_implements_resource_legal ?d ; cdm:resource_legal_id_celex ?nimc .
  ?d cdm:resource_legal_id_celex ?dir .
  OPTIONAL { ?n cdm:resource_legal_id_local ?num } OPTIONAL { ?n cdm:measure_national_implementing_type_act ?type }
  OPTIONAL { ?n cdm:work_date_document ?date } OPTIONAL { ?n cdm:work_title ?titre } }""" % FRA
    return ec.sparql(q)


class Codes:
    def __init__(self, legi):
        self.legi = legi
        self.codes = {}
        for r in legi.execute("SELECT id, titre FROM textes WHERE base='legi' AND nature='CODE'"):
            self.codes.setdefault(plier(r["titre"]), []).append((r["id"], r["titre"]))
        self.noms = sorted(self.codes, key=len, reverse=True)
        self.cache = {}

    def trouver(self, titre):
        t = " " + plier(titre) + " "
        for nom in self.noms:
            if (" " + nom + " ") in t:
                return sorted(self.codes[nom])[0]
        return None

    def articles(self, texte_id):
        if texte_id not in self.cache:
            par_num = {}
            for r in self.legi.execute(
                    "SELECT id, num, num_norm, etat, date_debut FROM articles INDEXED BY ix_art_texte_num "
                    "WHERE texte_id=? AND base='legi'", (texte_id,)):
                par_num.setdefault(r["num_norm"], []).append(r)
            courants = {}
            for n, versions in par_num.items():
                vigueur = [v for v in versions if v["etat"] in EN_VIGUEUR]
                courants[n] = max(vigueur or versions, key=lambda v: v["date_debut"] or "")
            self.cache[texte_id] = courants
        return self.cache[texte_id]


RE_NUM = re.compile(r"(?<![\w-])([LRDA])?\s?\.?\s?(\d+(?:-\d+)*)(?![\w-])")


def lire_articles(prefixe):
    """Numéros d'articles cités avant « du code » : « L217-17 à L217-20 », « L111-1, R111-1 et R111-2 »."""
    jetons = [(m.start(), m.end(), ((m.group(1) or "") + m.group(2)).lower()) for m in RE_NUM.finditer(prefixe)]
    res = []
    i = 0
    while i < len(jetons):
        debut, fin, num = jetons[i]
        if i + 1 < len(jetons) and re.fullmatch(r"\s+à\s+", prefixe[fin:jetons[i + 1][0]]):
            res.append(("plage", num, jetons[i + 1][2]))
            i += 2
        else:
            res.append(("seul", num, num))
            i += 1
    return res


def resoudre_plage(courants, lo, hi):
    lettre = re.match(r"[lrda]?", lo).group(0)
    cles = natural_key(lo), natural_key(hi)
    out = []
    for n, row in courants.items():
        if not n.startswith(lettre) or (lettre == "" and not n[:1].isdigit()):
            continue
        if cles[0] <= natural_key(n) <= cles[1]:
            out.append(row)
    return out


def cle_titre(titre):
    return plier(titre)[:70]


def charger_textes(legi, numeros, titres):
    log("balayage des textes (%d numéros, %d titres) ..." % (len(numeros), len(titres)))
    par_num, par_titre = {}, {}
    for r in legi.execute("SELECT id, base, nature, num, titre, etat FROM textes WHERE base IN ('legi','jorf')"):
        n = (r["num"] or "").strip()
        if n not in numeros:
            m = re.search(r"n\s*[°o]\s*(\d{2,4}-\d+)", r["titre"] or "")
            n = m.group(1) if m else ""
        if n in numeros:
            par_num.setdefault(n, []).append(r)
        k = cle_titre(r["titre"])
        if k in titres:
            par_titre.setdefault(k, []).append(r)
    log("  %d numéros et %d titres retrouvés" % (len(par_num), len(par_titre)))
    return par_num, par_titre


def traiter_mesures(lien, legi, mesures, emis):
    codes = Codes(legi)
    numeros = {(m.get("num") or "").strip() for m in mesures if re.fullmatch(r"\d{2,4}-\d+", (m.get("num") or "").strip())}
    titres = {cle_titre(m.get("titre")) for m in mesures if (m.get("type") or "").strip() != "Code"}
    par_num, par_titre = charger_textes(legi, numeros, titres)
    n_article = n_texte = n_non = 0
    for i, m in enumerate(mesures):
        if i % 2000 == 0:
            log("  mesure %d/%d" % (i, len(mesures)))
        celex_ue = m["dir"]
        titre = " ".join((m.get("titre") or "").split())
        typ = (m.get("type") or "").strip()
        nim = m["nimc"]
        code = codes.trouver(titre) if re.search(r"\bcode\b", titre, re.I) else None
        pre = re.split(r"\bdu\s+code\b|\bdes?\s+la?\s+code\b|\bdu\s+livre\b", titre, flags=re.I)[0]
        if code and re.match(r"\s*articles?\b", pre, re.I):
            vus = False
            for genre, lo, hi in lire_articles(re.sub(r"^\s*articles?\s*", "", pre, flags=re.I)):
                courants = codes.articles(code[0])
                cibles = resoudre_plage(courants, lo, hi) if genre == "plage" else \
                    ([courants[lo]] if lo in courants else [])
                for a in cibles:
                    if genre == "plage" and a["etat"] not in EN_VIGUEUR and a["num_norm"] not in (lo, hi):
                        continue
                    emis((celex_ue, "transposition", "article", a["id"], code[0], code[1], a["num_norm"].upper(),
                          a["etat"], titre, nim))
                    n_article += 1
                    vus = True
            if vus:
                continue
        numero = (m.get("num") or "").strip()
        candidats = par_num.get(numero, []) or par_titre.get(cle_titre(titre), [])
        if typ:
            filtres = [t for t in candidats if plier(typ)[:4] in plier((t["nature"] or "") + " " + (t["titre"] or "")[:40])]
            candidats = filtres or candidats
        if candidats:
            t = sorted(candidats, key=lambda r: (r["base"] != "legi", r["id"]))[0]
            emis((celex_ue, "transposition", "texte", t["id"], t["id"], t["titre"], None, t["etat"], titre, nim))
            n_texte += 1
            continue
        n_non += 1
    log("mesures nationales : %d articles, %d textes, %d non résolues" % (n_article, n_texte, n_non))


RE_ACTE = re.compile(
    r"(?:directive|règlement|reglement)\s*(?:d['’]exécution\s*|délégué(?:e)?\s*)?"
    r"(?:\(\s*(?:UE|CE|CEE|Euratom)\s*\)\s*)?(?:n\s*[°o]\s*)?(\d{1,4})\s*/\s*(\d{1,4})(?:\s*/\s*(?:UE|CE|CEE|Euratom))?",
    re.I)


def mentions(lien, legi, connus, emis):
    n = 0
    tot = 0
    cur = legi.execute(
        "SELECT a.id, a.texte_id, a.texte_titre, a.num_norm, a.etat, a.contenu, '' AS nota FROM articles_fts f "
        "JOIN articles a ON a.rowid = f.rowid WHERE articles_fts MATCH ? AND a.base='legi' AND "
        "a.etat IN ('VIGUEUR','VIGUEUR_ETEN','VIGUEUR_NON_ETEN','VIGUEUR_DIFF')",
        ("contenu : (directive OR reglement) AND (ue OR ce OR cee OR euratom OR europeen OR europeenne)",))
    for r in cur:
        tot += 1
        corps = (r["contenu"] or "") + " " + (r["nota"] or "")
        vus = set()
        for m in RE_ACTE.finditer(corps):
            celex = ec.celex_de(m.group(0).replace("’", "'"))
            if not celex or celex in vus or celex not in connus:
                continue
            vus.add(celex)
            extrait = " ".join(corps[max(0, m.start() - 60):m.end() + 40].split())
            emis((celex, "mention", "article", r["id"], r["texte_id"], r["texte_titre"], (r["num_norm"] or "").upper(),
                  r["etat"], extrait, ""))
            n += 1
        if tot % 50000 == 0:
            log("  %d articles examinés, %d mentions" % (tot, n))
    log("mentions : %d citations d'actes européens dans %d articles examinés" % (n, tot))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legi", default=LEGI)
    ap.add_argument("--eu", default=EU)
    ap.add_argument("--out", default=LIENS)
    ap.add_argument("--sans-mentions", action="store_true")
    a = ap.parse_args()

    for f in (a.legi, a.eu):
        if not os.path.exists(f):
            sys.exit("Base absente : " + f)
    legi = sqlite3.connect("file:%s?mode=ro" % a.legi, uri=True)
    legi.row_factory = sqlite3.Row
    eu = sqlite3.connect("file:%s?mode=ro" % a.eu, uri=True)
    connus = {r[0] for r in eu.execute("SELECT celex FROM docs")}
    tmp = a.out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    lien = sqlite3.connect(tmp)
    lien.executescript(SCHEMA)
    tampon = []

    def emis(row):
        tampon.append(row)
        if len(tampon) >= 2000:
            vider()

    def vider():
        lien.executemany("INSERT OR IGNORE INTO liens (celex, source, cible_type, cible_id, texte_id, texte_titre, "
                         "num, etat, detail, nim_celex) VALUES (?,?,?,?,?,?,?,?,?,?)", tampon)
        lien.commit()
        tampon.clear()

    mesures = mesures_nationales()
    log("%d mesures nationales françaises récupérées" % len(mesures))
    traiter_mesures(lien, legi, mesures, emis)
    if not a.sans_mentions:
        mentions(lien, legi, connus, emis)
    vider()
    lien.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    lien.commit()
    for s, k, n in lien.execute("SELECT source, cible_type, count(*) FROM liens GROUP BY 1,2"):
        log("  %s / %s : %d" % (s, k, n))
    lien.close()
    os.replace(tmp, a.out)
    log("écrit : " + a.out)


if __name__ == "__main__":
    main()
