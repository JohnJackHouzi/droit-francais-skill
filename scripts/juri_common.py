import html
import os
import re
import sqlite3

DATA_DIR = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
DB_PATH = os.path.join(DATA_DIR, "juri.sqlite")
BASES = ("jade", "cass", "capp", "inca", "constit", "cnil")

COLUMNS = (
    "id", "base", "juridiction", "formation", "numero", "numero_arret", "date",
    "ecli", "solution", "publication", "nature", "titre", "sommaire", "contenu",
    "textes_cites",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    base TEXT NOT NULL,
    juridiction TEXT,
    formation TEXT,
    numero TEXT,
    numero_arret TEXT,
    date TEXT,
    ecli TEXT,
    solution TEXT,
    publication TEXT,
    nature TEXT,
    titre TEXT,
    sommaire TEXT,
    contenu TEXT,
    textes_cites TEXT
);
CREATE TABLE IF NOT EXISTS numeros (
    num TEXT NOT NULL,
    id TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    titre, sommaire, contenu,
    content='decisions', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_dec_base ON decisions(base);
CREATE INDEX IF NOT EXISTS idx_dec_date ON decisions(date);
CREATE INDEX IF NOT EXISTS idx_dec_ecli ON decisions(ecli);
CREATE INDEX IF NOT EXISTS idx_dec_juri ON decisions(juridiction);
CREATE INDEX IF NOT EXISTS idx_num_num ON numeros(num);
CREATE INDEX IF NOT EXISTS idx_num_id ON numeros(id);
"""

LIBELLES_RECUEIL = {
    "A": "Publié au recueil Lebon",
    "B": "Mentionné aux tables du recueil Lebon",
    "C": "Inédit au recueil Lebon",
}

LEGIFRANCE_PATH = {
    "jade": "ceta", "cass": "juri", "capp": "juri", "inca": "juri",
    "constit": "cons", "cnil": "cnil",
}


def lien_legifrance(base, ident):
    return "https://www.legifrance.gouv.fr/%s/id/%s" % (LEGIFRANCE_PATH.get(base, "juri"), ident)


def open_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def norm_numero(valeur):
    return re.sub(r"[^0-9a-z]", "", valeur.lower())


_RE_TAG = re.compile(r"<[^>]+>")
_RE_BREAKS = re.compile(r"<br\s*/?>|</p>|</tr>|</li>|</div>|</h\d>|</table>|</ul>|</ol>", re.I)
_RE_CELL = re.compile(r"</t[dh]>", re.I)
_RE_SPACES = re.compile(r"[ \t\r\f\v ]+")
_RE_NL = re.compile(r"\n\s*\n+")


def nettoyer(fragment):
    if not fragment:
        return ""
    t = _RE_BREAKS.sub("\n", fragment)
    t = _RE_CELL.sub(" | ", t)
    t = _RE_TAG.sub("", t)
    t = html.unescape(t)
    t = _RE_SPACES.sub(" ", t)
    t = "\n".join(ligne.strip() for ligne in t.split("\n"))
    t = _RE_NL.sub("\n\n", t)
    return t.strip()


def balise(s, nom):
    m = re.search(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (nom, nom), s, re.S)
    return nettoyer(m.group(1)) if m else ""


def toutes_balises(s, nom):
    return [nettoyer(x) for x in re.findall(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (nom, nom), s, re.S)]


def attribut(s, nom, attr):
    m = re.search(r"<%s\s[^>]*?%s=\"([^\"]*)\"" % (nom, attr), s)
    return html.unescape(m.group(1)) if m else ""


def pourvoi_pointe(valeur):
    m = re.fullmatch(r"(\d{2})-(\d{2,})", valeur)
    if not m or len(m.group(2)) <= 3:
        return valeur
    n = m.group(2)
    return "%s-%s.%s" % (m.group(1), n[:-3], n[-3:])


def parse_decision(raw, base):
    m = re.search(r"<ID>([^<]+)</ID>", raw)
    if not m:
        return None
    ident = m.group(1).strip()
    if base == "cnil":
        meta = raw.split("<BLOC_TEXTUEL>", 1)[0]
        titre = balise(meta, "TITRE")
        titrefull = balise(meta, "TITREFULL")
        contenu_brut = re.search(r"<BLOC_TEXTUEL>\s*<CONTENU>(.*?)</CONTENU>", raw, re.S)
        numero = balise(meta, "NUMERO")
        return {
            "id": ident, "base": base, "juridiction": "CNIL",
            "formation": "", "numero": numero, "numero_arret": "",
            "date": balise(meta, "DATE_TEXTE"), "ecli": "",
            "solution": balise(meta, "NATURE_DELIB"),
            "publication": balise(meta, "ETAT_JURIDIQUE"),
            "nature": balise(meta, "NATURE"),
            "titre": titre, "sommaire": titrefull,
            "contenu": nettoyer(contenu_brut.group(1)) if contenu_brut else "",
            "textes_cites": "\n".join(x for x in toutes_balises(raw, "LIEN") if x),
            "_numeros": [numero] if numero else [],
        }

    tete, _, corps = raw.partition("<TEXTE>")
    contenu_brut = re.search(r"<BLOC_TEXTUEL>\s*<CONTENU>(.*?)</CONTENU>", corps, re.S)
    sommaire_brut = re.search(r"<SOMMAIRE>(.*?)</SOMMAIRE>", corps, re.S)
    sommaire = ""
    if sommaire_brut:
        parts = [x for x in toutes_balises(sommaire_brut.group(1), "SCT") if x]
        parts += [x for x in toutes_balises(sommaire_brut.group(1), "ANA") if x]
        sommaire = "\n".join(parts)

    cites = []
    for bloc in re.findall(r"<CITATION_JP>(.*?)</CITATION_JP>", corps, re.S):
        c = balise(bloc, "CONTENU")
        if c:
            cites.append(c)
    cites += [x for x in toutes_balises(raw.split("</TEXTE>", 1)[-1], "LIEN") if x]
    cites += [x for x in toutes_balises(tete, "LOI_DEF") if x]

    meta_juri = balise_brute(tete, "META_JURI")
    nature = balise(tete, "NATURE")
    publication = ""
    pb = re.search(r"<PUBLI_BULL\s+publie=\"([^\"]*)\"\s*(?:/>|>(.*?)</PUBLI_BULL>)", tete, re.S)
    if pb:
        publication = "oui" if pb.group(1) == "oui" else "non"
        if pb.group(2):
            publication += " : " + nettoyer(pb.group(2))
    recueil = balise(tete, "PUBLI_RECUEIL")
    if recueil:
        publication = LIBELLES_RECUEIL.get(recueil, recueil)

    affaires = [x for x in toutes_balises(tete, "NUMERO_AFFAIRE") if x]
    numero_arret = balise(meta_juri, "NUMERO")
    numeros_bruts = affaires[:]
    if base in ("cass", "inca"):
        affaires = [pourvoi_pointe(x) for x in affaires]
    if not affaires and numero_arret:
        affaires = [numero_arret]
    numeros_idx = set(numeros_bruts + affaires + ([numero_arret] if numero_arret else []))

    numero_arret_stocke = "" if numero_arret in affaires else numero_arret

    return {
        "id": ident, "base": base,
        "juridiction": balise(meta_juri, "JURIDICTION"),
        "formation": balise(tete, "FORMATION") or balise(tete, "FORMATION_JUGEMENT"),
        "numero": " ; ".join(affaires), "numero_arret": numero_arret_stocke,
        "date": balise(meta_juri, "DATE_DEC"),
        "ecli": balise(tete, "ECLI"),
        "solution": balise(meta_juri, "SOLUTION"),
        "publication": publication, "nature": nature,
        "titre": balise(meta_juri, "TITRE"), "sommaire": sommaire,
        "contenu": nettoyer(contenu_brut.group(1)) if contenu_brut else "",
        "textes_cites": "\n".join(cites),
        "_numeros": sorted(numeros_idx),
    }


def balise_brute(s, nom):
    m = re.search(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (nom, nom), s, re.S)
    return m.group(1) if m else ""


def ligne_sql(d):
    return tuple(d[c] for c in COLUMNS)


INSERT_SQL = "INSERT OR REPLACE INTO decisions (%s) VALUES (%s)" % (
    ",".join(COLUMNS), ",".join("?" * len(COLUMNS)))
