import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

DATA_DIR = os.path.expanduser(os.environ.get("DROIT_DATA", "~/droit-francais-data"))
DB_PATH = os.path.expanduser(os.environ.get("LEGI_DB", os.path.join(DATA_DIR, "legi.sqlite")))

FILE_RE = re.compile(r"^(LEGI|JORF|KALI)(ARTI|TEXT|CONT)(\d{12})\.xml$")
FAR_FUTURE = "2999-01-01"

SCHEMA = """
CREATE TABLE IF NOT EXISTS textes (
  id TEXT PRIMARY KEY,
  cid TEXT,
  base TEXT NOT NULL,
  nature TEXT,
  titre TEXT,
  titrefull TEXT,
  nor TEXT,
  num TEXT,
  etat TEXT,
  date_texte TEXT,
  date_publi TEXT,
  date_debut TEXT,
  date_fin TEXT,
  derniere_modif TEXT,
  origine_publi TEXT,
  ministere TEXT,
  eli TEXT,
  idcc TEXT,
  extension TEXT,
  visas TEXT,
  nota TEXT
);
CREATE TABLE IF NOT EXISTS articles (
  rowid INTEGER PRIMARY KEY,
  id TEXT NOT NULL UNIQUE,
  base TEXT NOT NULL,
  texte_id TEXT,
  texte_titre TEXT,
  texte_nature TEXT,
  num TEXT,
  num_norm TEXT,
  titre_art TEXT,
  contenu TEXT,
  nota TEXT,
  date_debut TEXT,
  date_fin TEXT,
  etat TEXT,
  chemin TEXT,
  type TEXT,
  lignee TEXT,
  idcc TEXT,
  liens TEXT
);
CREATE TABLE IF NOT EXISTS conteneurs (
  id TEXT PRIMARY KEY,
  base TEXT,
  idcc TEXT,
  titre TEXT,
  etat TEXT,
  date_publi TEXT
);
CREATE TABLE IF NOT EXISTS conteneur_textes (
  conteneur_id TEXT,
  texte_id TEXT,
  rubrique TEXT,
  titre TEXT,
  PRIMARY KEY (conteneur_id, texte_id)
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS ix_art_texte_num ON articles(texte_id, num_norm);
CREATE INDEX IF NOT EXISTS ix_art_num ON articles(num_norm);
CREATE INDEX IF NOT EXISTS ix_art_lignee ON articles(lignee);
CREATE INDEX IF NOT EXISTS ix_art_base ON articles(base);
CREATE INDEX IF NOT EXISTS ix_art_idcc ON articles(idcc);
CREATE INDEX IF NOT EXISTS ix_txt_cid ON textes(cid);
CREATE INDEX IF NOT EXISTS ix_txt_nature ON textes(base, nature);
CREATE INDEX IF NOT EXISTS ix_txt_nor ON textes(nor);
CREATE INDEX IF NOT EXISTS ix_txt_num ON textes(num);
CREATE INDEX IF NOT EXISTS ix_txt_idcc ON textes(idcc);
CREATE INDEX IF NOT EXISTS ix_cont_idcc ON conteneurs(idcc);
CREATE INDEX IF NOT EXISTS ix_ct_texte ON conteneur_textes(texte_id);
"""

FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
  contenu, num, texte_titre, titre_art,
  content='articles', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE IF NOT EXISTS textes_fts USING fts5(
  titre, titrefull, nor, num,
  content='textes', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
"""

TRIGGERS = """
DROP TRIGGER IF EXISTS articles_ai;
DROP TRIGGER IF EXISTS articles_ad;
DROP TRIGGER IF EXISTS articles_au;
DROP TRIGGER IF EXISTS textes_ai;
DROP TRIGGER IF EXISTS textes_ad;
DROP TRIGGER IF EXISTS textes_au;
CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
  INSERT INTO articles_fts(rowid, contenu, num, texte_titre, titre_art)
  VALUES (new.rowid, new.contenu, new.num, new.texte_titre, new.titre_art);
END;
CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
  INSERT INTO articles_fts(articles_fts, rowid, contenu, num, texte_titre, titre_art)
  VALUES ('delete', old.rowid, old.contenu, old.num, old.texte_titre, old.titre_art);
END;
CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
  INSERT INTO articles_fts(articles_fts, rowid, contenu, num, texte_titre, titre_art)
  VALUES ('delete', old.rowid, old.contenu, old.num, old.texte_titre, old.titre_art);
  INSERT INTO articles_fts(rowid, contenu, num, texte_titre, titre_art)
  VALUES (new.rowid, new.contenu, new.num, new.texte_titre, new.titre_art);
END;
CREATE TRIGGER textes_ai AFTER INSERT ON textes BEGIN
  INSERT INTO textes_fts(rowid, titre, titrefull, nor, num)
  VALUES (new.rowid, new.titre, new.titrefull, new.nor, new.num);
END;
CREATE TRIGGER textes_ad AFTER DELETE ON textes BEGIN
  INSERT INTO textes_fts(textes_fts, rowid, titre, titrefull, nor, num)
  VALUES ('delete', old.rowid, old.titre, old.titrefull, old.nor, old.num);
END;
CREATE TRIGGER textes_au AFTER UPDATE ON textes BEGIN
  INSERT INTO textes_fts(textes_fts, rowid, titre, titrefull, nor, num)
  VALUES ('delete', old.rowid, old.titre, old.titrefull, old.nor, old.num);
  INSERT INTO textes_fts(rowid, titre, titrefull, nor, num)
  VALUES (new.rowid, new.titre, new.titrefull, new.nor, new.num);
END;
"""

BLOCK_TAGS = {"p", "div", "br", "tr", "li", "ul", "ol", "table", "tbody", "thead",
              "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "center", "pre"}
CELL_TAGS = {"td", "th"}

ARTICLE_COLS = ("id", "base", "texte_id", "texte_titre", "texte_nature", "num", "num_norm",
                "titre_art", "contenu", "nota", "date_debut", "date_fin", "etat", "chemin",
                "type", "lignee", "idcc", "liens")
TEXTE_COLS = ("id", "cid", "base", "nature", "titre", "titrefull", "nor", "num", "etat",
              "date_texte", "date_publi", "date_debut", "date_fin", "derniere_modif",
              "origine_publi", "ministere", "eli", "idcc", "extension", "visas", "nota")


def connect(path=None, readonly=False):
    path = path or DB_PATH
    if readonly:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    else:
        con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def norm_num(num):
    if not num:
        return ""
    s = num.lower().strip()
    s = re.sub(r"^(article|art)\.?\s*", "", s)
    s = s.replace(" ", "").replace(" ", "").replace(".", "")
    s = s.replace("º", "").replace("°", "")
    return s


def clean_date(value):
    if not value:
        return None
    value = value.strip()
    if not value or value.startswith("2999") or value.startswith("2222"):
        return None
    return value


def _walk_text(elem, out):
    tag = elem.tag.lower() if isinstance(elem.tag, str) else ""
    if tag == "tr":
        cells = []
        for c in elem:
            if isinstance(c.tag, str) and c.tag.lower() in CELL_TAGS:
                cells.append(" ".join("".join(c.itertext()).split()))
        out.append("\n" + " | ".join(cells) + "\n")
        if elem.tail:
            out.append(elem.tail)
        return
    if tag == "br":
        out.append("\n")
        if elem.tail:
            out.append(elem.tail)
        return
    block = tag in BLOCK_TAGS
    if block:
        out.append("\n")
    if elem.text:
        out.append(elem.text)
    for child in elem:
        _walk_text(child, out)
    if block:
        out.append("\n")
    if elem.tail:
        out.append(elem.tail)


def to_text(elem):
    if elem is None:
        return ""
    out = []
    if elem.text:
        out.append(elem.text)
    for child in elem:
        _walk_text(child, out)
    raw = "".join(out).replace(" ", " ")
    lines = []
    for line in raw.split("\n"):
        line = re.sub(r"[ \t\r]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def txt(root, path):
    e = root.find(path)
    if e is None or e.text is None:
        return None
    v = e.text.strip()
    return v or None


def parse_article(root, base):
    aid = txt(root, "META/META_COMMUN/ID")
    meta = root.find("META/META_SPEC/META_ARTICLE")
    if aid is None or meta is None:
        return None
    num = txt(meta, "NUM")
    etat = txt(meta, "ETAT")
    date_debut = clean_date(txt(meta, "DATE_DEBUT"))
    date_fin = clean_date(txt(meta, "DATE_FIN"))
    typ = txt(meta, "TYPE")
    titre_art = txt(meta, "TITRE")

    ctx = root.find("CONTEXTE")
    texte_id = texte_titre = texte_nature = None
    chemin = None
    idcc = None
    cont_titre = None
    texte_date_publi = None
    if ctx is not None:
        t = ctx.find("TEXTE")
        if t is not None:
            texte_id = t.get("cid")
            texte_nature = t.get("nature")
            texte_date_publi = clean_date(t.get("date_publi"))
            titres = t.findall("TITRE_TXT")
            chosen = None
            for tt in titres:
                if tt.get("id_txt") == texte_id:
                    chosen = tt
                    break
            if chosen is None and titres:
                chosen = titres[-1]
            if chosen is not None:
                texte_titre = " ".join("".join(chosen.itertext()).split()) or chosen.get("c_titre_court")
            parts = []
            node = t.find("TM")
            while node is not None:
                tm = node.find("TITRE_TM")
                if tm is not None and tm.text:
                    parts.append(" ".join(tm.text.split()))
                node = node.find("TM")
            chemin = " > ".join(parts) or None
        c = ctx.find("CONTENEUR")
        if c is not None:
            idcc = c.get("num")
            cont_titre = " ".join((c.get("titre") or "").split())
    if base == "kali" and cont_titre:
        texte_titre = "IDCC %s - %s%s" % (idcc, cont_titre,
                                         "" if not texte_titre or texte_titre == cont_titre else " / " + texte_titre)

    if base == "jorf" and date_debut is None:
        date_debut = texte_date_publi

    versions = [l.get("id") for l in root.findall("VERSIONS/VERSION/LIEN_ART") if l.get("id")]
    lignee = min(versions) if versions else aid

    contenu = to_text(root.find("BLOC_TEXTUEL/CONTENU"))
    nota = to_text(root.find("NOTA/CONTENU")) or None

    liens = []
    for l in root.findall("LIENS/LIEN"):
        liens.append([l.get("typelien"), l.get("sens"), l.get("id"), l.get("cidtexte"),
                      " ".join((l.text or "").split())])
    return (aid, base, texte_id, texte_titre, texte_nature, num, norm_num(num), titre_art,
            contenu, nota, date_debut, date_fin, etat, chemin, typ, lignee, idcc,
            json.dumps(liens, ensure_ascii=False, separators=(",", ":")) if liens else None)


def parse_texte(root, base):
    tid = txt(root, "META/META_COMMUN/ID")
    if tid is None:
        return None
    mc = root.find("META/META_SPEC/META_TEXTE_CHRONICLE")
    mv = root.find("META/META_SPEC/META_TEXTE_VERSION")
    if mc is None:
        mc = ET.Element("x")
    if mv is None:
        mv = ET.Element("x")
    visas = to_text(root.find("VISAS/CONTENU")) or None
    nota = to_text(root.find("NOTA/CONTENU")) or None
    return (tid, txt(mc, "CID") or tid, base, txt(root, "META/META_COMMUN/NATURE"),
            txt(mv, "TITRE"), txt(mv, "TITREFULL"), txt(mc, "NOR"), txt(mc, "NUM"),
            txt(mv, "ETAT"), clean_date(txt(mc, "DATE_TEXTE")), clean_date(txt(mc, "DATE_PUBLI")),
            clean_date(txt(mv, "DATE_DEBUT")), clean_date(txt(mv, "DATE_FIN")),
            clean_date(txt(mc, "DERNIERE_MODIFICATION")), txt(mc, "ORIGINE_PUBLI"),
            txt(mv, "MINISTERE"), txt(root, "META/META_COMMUN/ID_ELI"), None,
            txt(mv, "LIBELLE_EXTENSION"), visas, nota)


def parse_conteneur(root, base):
    cid = txt(root, "META/META_COMMUN/ID")
    if cid is None:
        return None
    mc = root.find("META/META_SPEC/META_CONTENEUR")
    if mc is None:
        return None
    head = (cid, base, txt(mc, "NUM"), " ".join((txt(mc, "TITRE") or "").split()),
            txt(mc, "ETAT"), clean_date(txt(mc, "DATE_PUBLI")))
    links = []

    def rec(node, rubrique):
        for child in node:
            if child.tag == "TM":
                tm = child.find("TITRE_TM")
                label = " ".join((tm.text or "").split()) if tm is not None else rubrique
                rec(child, label if rubrique is None else rubrique + " > " + label)
            elif child.tag == "LIEN_TXT":
                links.append((cid, child.get("idtxt"), rubrique,
                              " ".join((child.get("titretxt") or "").split())))

    st = root.find("STRUCTURE_TXT")
    if st is not None and base == "kali":
        rec(st, None)
    return head, links


def classify(path):
    name = os.path.basename(path)
    m = FILE_RE.match(name)
    if not m:
        return None
    base, kind = m.group(1).lower(), m.group(2)
    if kind == "TEXT" and "/texte/version/" not in path:
        return None
    if kind == "CONT" and base != "kali":
        return None
    return base, kind


def parse_file(path):
    c = classify(path)
    if c is None:
        return None
    base, kind = c
    try:
        with open(path, "rb") as fh:
            root = ET.fromstring(fh.read())
        if kind == "ARTI":
            r = parse_article(root, base)
        elif kind == "TEXT":
            r = parse_texte(root, base)
        else:
            r = parse_conteneur(root, base)
    except Exception as exc:
        return ("E", path, repr(exc))
    if r is None:
        return ("E", path, "structure inattendue")
    return ({"ARTI": "A", "TEXT": "T", "CONT": "C"}[kind], r)


def parse_files(paths):
    out = []
    for p in paths:
        r = parse_file(p)
        if r is not None:
            out.append(r)
    return out


def store(con, results):
    ins_a = "INSERT OR REPLACE INTO articles (%s) VALUES (%s)" % (
        ",".join(ARTICLE_COLS), ",".join("?" * len(ARTICLE_COLS)))
    ins_t = "INSERT OR REPLACE INTO textes (%s) VALUES (%s)" % (
        ",".join(TEXTE_COLS), ",".join("?" * len(TEXTE_COLS)))
    arts, txts, conts, links, errs = [], [], [], [], []
    for r in results:
        k = r[0]
        if k == "A":
            arts.append(r[1])
        elif k == "T":
            txts.append(r[1])
        elif k == "C":
            conts.append(r[1][0])
            links.extend(r[1][1])
        else:
            errs.append(r)
    if arts:
        con.executemany(ins_a, arts)
    if txts:
        con.executemany(ins_t, txts)
    if conts:
        con.executemany("INSERT OR REPLACE INTO conteneurs VALUES (?,?,?,?,?,?)", conts)
    if links:
        con.executemany("INSERT OR REPLACE INTO conteneur_textes VALUES (?,?,?,?)", links)
    return len(arts), len(txts), len(conts), errs


def init_db(con):
    con.executescript(SCHEMA)


def finalize(con, rebuild_fts=True):
    con.executescript(INDEXES)
    con.execute("UPDATE textes SET idcc = (SELECT c.idcc FROM conteneur_textes ct JOIN conteneurs c "
                "ON c.id = ct.conteneur_id WHERE ct.texte_id = textes.id LIMIT 1) "
                "WHERE base = 'kali' AND idcc IS NULL")
    con.executescript(FTS)
    if rebuild_fts:
        con.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        con.execute("INSERT INTO textes_fts(textes_fts) VALUES('rebuild')")
    con.executescript(TRIGGERS)
    con.commit()


def _upsert_sql(table, cols, key="id", keep=()):
    sets = []
    for c in cols:
        if c == key:
            continue
        if c in keep:
            sets.append("%s=COALESCE(excluded.%s, %s.%s)" % (c, c, table, c))
        else:
            sets.append("%s=excluded.%s" % (c, c))
    return "INSERT INTO %s (%s) VALUES (%s) ON CONFLICT(%s) DO UPDATE SET %s" % (
        table, ",".join(cols), ",".join("?" * len(cols)), key, ",".join(sets))


def store_upsert(con, results):
    arts, txts, conts, links, errs = [], [], [], [], []
    for r in results:
        k = r[0]
        if k == "A":
            arts.append(r[1])
        elif k == "T":
            txts.append(r[1])
        elif k == "C":
            conts.append(r[1][0])
            links.extend(r[1][1])
        else:
            errs.append(r)
    if arts:
        con.executemany(_upsert_sql("articles", ARTICLE_COLS), arts)
    if txts:
        con.executemany(_upsert_sql("textes", TEXTE_COLS, keep=("idcc",)), txts)
    if conts:
        con.executemany("DELETE FROM conteneur_textes WHERE conteneur_id = ?", [(c[0],) for c in conts])
        con.executemany("INSERT OR REPLACE INTO conteneurs VALUES (?,?,?,?,?,?)", conts)
    if links:
        con.executemany("INSERT OR REPLACE INTO conteneur_textes VALUES (?,?,?,?)", links)
    return len(arts), len(txts), len(conts), errs
