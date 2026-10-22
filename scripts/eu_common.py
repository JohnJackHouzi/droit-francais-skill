import html
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request

DATA_DIR = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
DB_PATH = os.path.join(DATA_DIR, "eu.sqlite")
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CELEX_URL = "https://publications.europa.eu/resource/celex/"
UA = {"User-Agent": "droit-francais-skill/1.0 (+https://github.com/JohnJackHouzi/droit-francais-skill)"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  rowid INTEGER PRIMARY KEY,
  celex TEXT NOT NULL UNIQUE,
  celex_version TEXT,
  date_version TEXT,
  type TEXT,
  titre TEXT,
  date TEXT,
  en_vigueur TEXT,
  ecli TEXT,
  affaire TEXT,
  maj TEXT
);
CREATE TABLE IF NOT EXISTS parties (
  rowid INTEGER PRIMARY KEY,
  celex TEXT NOT NULL,
  ordre INTEGER,
  num TEXT,
  num_norm TEXT,
  titre TEXT,
  contenu TEXT
);
CREATE INDEX IF NOT EXISTS ix_parties ON parties(celex, num_norm);
CREATE INDEX IF NOT EXISTS ix_docs_ecli ON docs(ecli);
CREATE INDEX IF NOT EXISTS ix_docs_affaire ON docs(affaire);
CREATE VIRTUAL TABLE IF NOT EXISTS parties_fts USING fts5(
  titre, contenu, content='parties', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TRIGGER IF NOT EXISTS parties_ai AFTER INSERT ON parties BEGIN
  INSERT INTO parties_fts(rowid, titre, contenu) VALUES (new.rowid, new.titre, new.contenu);
END;
CREATE TRIGGER IF NOT EXISTS parties_ad AFTER DELETE ON parties BEGIN
  INSERT INTO parties_fts(parties_fts, rowid, titre, contenu) VALUES ('delete', old.rowid, old.titre, old.contenu);
END;
"""

TYPES = {
    "REG": "Règlement", "DIR": "Directive", "DEC": "Décision", "REG_IMPL": "Règlement d'exécution",
    "REG_DEL": "Règlement délégué", "DIR_IMPL": "Directive d'exécution", "DIR_DEL": "Directive déléguée",
    "JUDG": "Arrêt", "ORDER": "Ordonnance", "OPIN_AG": "Conclusions de l'avocat général",
    "TREATY": "Traité", "CHARTER": "Charte",
}


def affaire(celex):
    m = re.match(r"^6(\d{4})(CJ|TJ|FJ|CO|TO|CC)(\d{4})", celex or "")
    if not m:
        return None
    lettre = {"CJ": "C", "CO": "C", "CC": "C", "TJ": "T", "TO": "T", "FJ": "F"}[m.group(2)]
    return "%s-%d/%s" % (lettre, int(m.group(3)), m.group(1)[2:])


ALIAS = {
    "rgpd": "32016R0679", "gdpr": "32016R0679", "ria": "32024R1689", "ai act": "32024R1689",
    "reglement ia": "32024R1689", "dsa": "32022R2065", "dma": "32022R1925", "data act": "32023R2854",
    "dga": "32022R0868", "tfue": "12016E/TXT", "tue": "12016M/TXT", "charte": "12016P/TXT",
    "charte des droits fondamentaux": "12016P/TXT", "eprivacy": "32002L0058",
}


def celex_de(ref):
    """Trouve le CELEX d'un acte cité : alias (RGPD, DSA), CELEX, « règlement (UE) 2016/679 », « directive 93/13/CEE »."""
    import unicodedata
    r = unicodedata.normalize("NFKD", ref or "")
    r = "".join(c for c in r if not unicodedata.combining(c)).lower().strip()
    if r in ALIAS:
        return ALIAS[r]
    m = re.match(r"^([0-9]\d{4}[a-z]{1,2}\d{4}|1\d{4}[a-z]/txt)$", r)
    if m:
        return r.upper()
    m = re.search(r"(reglement|directive|decision)\D*?(?:n[o°]\s*)?(\d{1,4})/(\d{1,4})", r)
    if not m:
        return None
    kind = {"reglement": "R", "directive": "L", "decision": "D"}[m.group(1)]
    a, b = m.group(2), m.group(3)

    def year(x):
        y = int(x)
        return y + (1900 if y >= 50 else 2000) if len(x) == 2 else y

    if kind == "R" and not (len(a) == 4 and 1958 <= int(a) <= 2100):
        y, n = year(b), int(a)
    else:
        y, n = year(a), int(b)
    return "3%d%s%04d" % (y, kind, n)


def candidats_numero(ref):
    """CELEX possibles pour un numéro d'acte nu (« 2016/679 », « 93/13 », « 1215/2012 »)."""
    m = re.fullmatch(r"\s*(?:n[o°]\s*)?(\d{1,4})/(\d{1,4})(?:/\w+)?\s*", ref or "", re.I)
    if not m:
        return []
    a, b = m.group(1), m.group(2)

    def year(x):
        y = int(x)
        return y + (1900 if y >= 50 else 2000) if len(x) == 2 else y

    ordres = [(year(a), int(b)), (year(b), int(a))]
    return ["3%d%s%04d" % (y, k, n) for y, n in ordres if 1950 <= y <= 2100 and n < 10000 for k in ("R", "L", "D")]


def lien(celex):
    return "https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:" + celex


def connect(path=None, readonly=False):
    path = path or DB_PATH
    if readonly:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        con = sqlite3.connect(path)
        con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    return con


def http(url, accept=None, tries=4, timeout=120):
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    headers["Accept-Language"] = "fra"
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (300, 404, 406):
                return exc.code, "", b""
            last = exc
        except Exception as exc:
            last = exc
        time.sleep(3 * (i + 1))
    raise RuntimeError("échec %s : %r" % (url, last))


def sparql(query):
    url = SPARQL + "?" + urllib.parse.urlencode({"query": query})
    _s, _t, body = http(url, "application/sparql-results+json", timeout=300)
    data = json.loads(body)
    return [{k: v["value"] for k, v in b.items()} for b in data["results"]["bindings"]]


_RE_DROP = re.compile(r"<(script|style|head)\b.*?</\1>", re.S | re.I)
_RE_BLOCK = re.compile(r"<(?:br|/p|/div|/tr|/li|/h\d|/table|/td|/th)\b[^>]*>", re.I)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_MARK = re.compile(r"[▼►◄▲]\s*[A-Z]\d*\b|[▼►◄▲]")


def html_to_lines(raw):
    s = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    s = _RE_DROP.sub(" ", s)
    s = re.sub(r"</t[dh]>", " | ", s, flags=re.I)
    s = _RE_BLOCK.sub("\n", s)
    s = html.unescape(_RE_TAG.sub(" ", s))
    s = _RE_MARK.sub(" ", s).replace("\xa0", " ")
    lines = []
    for line in s.split("\n"):
        line = re.sub(r"\s+", " ", line).strip(" |")
        if line:
            lines.append(line)
    return lines


ART_RE = re.compile(r"^Article (premier|\d+[a-z]?(?: (?:bis|ter|quater|quinquies))?)$", re.I)
ANNEX_RE = re.compile(r"^ANNEXE(?: [IVXLC]+[a-z]?| \d+)?$")


def norm_num(num):
    s = (num or "").lower().strip()
    s = re.sub(r"^(article|art)\.?\s*", "", s)
    if s == "premier":
        s = "1"
    return s.replace(" ", "").replace(".", "")


def split_acte(lines):
    """Découpe un acte en préambule, articles et annexes. Retourne [(num, titre, texte)]."""
    parts, cur_num, cur_titre, buf = [], "préambule", None, []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ART_RE.match(line)
        a = ANNEX_RE.match(line)
        if m or a:
            if buf:
                parts.append((cur_num, cur_titre, "\n".join(buf)))
            cur_num = ("Article " + m.group(1)) if m else "Annexe" + line[len("ANNEXE"):]
            cur_titre, buf = None, []
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt and len(nxt) < 200 and not re.match(r"^(\d+\.|\(?[a-z]\)|1\))", nxt) and not ART_RE.match(nxt):
                cur_titre = nxt
                i += 1
        else:
            buf.append(line)
        i += 1
    if buf:
        parts.append((cur_num, cur_titre, "\n".join(buf)))
    seen = {}
    out = []
    for num, titre, texte in parts:
        if num in seen:
            out[seen[num]] = (num, out[seen[num]][1] or titre, out[seen[num]][2] + "\n" + texte)
        else:
            seen[num] = len(out)
            out.append((num, titre, texte))
    return out
