"""Promoter normalization for the Pollstar US analysis.

classify(promoter_string) -> (parent_name, segment)
  segment in {"Major", "Non-music", "In-House", "Independent"}

Method (confirmed with client):
  - US scope, gross USD primary metric.
  - Co-promotions: "major leads" -- if a Live Nation or AEG brand appears
    anywhere in the string, the whole show is credited to that major.
  - Non-music content owners (sports, family/arena shows) are a separate bucket.
  - Pure venue self-promotion -> "Venue / In-House".
  - Everything else is an independent, canonicalized to merge spelling variants.

All brand groupings are based on documented industry ownership. Borderline or
minority-stake names (Insomniac, Emporium, AC Entertainment, NS2, Marshall Arts,
Madison House, 313 Presents) are deliberately LEFT INDEPENDENT to avoid
overstating the majors; this is noted in the workbook README.
"""
import re

# --- Tier 1 majors: wholly/majority-owned brands, conservative list ---
LN_BRANDS = [
    "live nation", "house of blues", "c3 presents",
    "frank productions", "fpc live",
]
AEG_BRANDS = [
    "aeg presents", "aeg live", "goldenvoice", "concerts west",
    "messina touring group", "the bowery presents", "promowest",
]

# --- Non-music content owners (sports + family/arena touring shows) ---
# (pattern, canonical name)
NONMUSIC = [
    ("feld entertainment", "Feld Entertainment"),
    ("disney on ice", "Feld Entertainment"),
    ("ringling", "Feld Entertainment"),
    ("monster jam", "Feld Entertainment"),
    ("cirque du soleil", "Cirque du Soleil"),
    ("world wrestling", "WWE / UFC (TKO)"),
    ("wwe", "WWE / UFC (TKO)"),
    ("zuffa", "WWE / UFC (TKO)"),
    ("tko productions", "WWE / UFC (TKO)"),
    (" ufc", "WWE / UFC (TKO)"),
    ("ultimate fighting", "WWE / UFC (TKO)"),
    ("professional bull riders", "Professional Bull Riders"),
    ("harlem globetrotters", "Harlem Globetrotters"),
    ("matchroom boxing", "Matchroom Boxing"),
    ("vstar entertainment", "VStar Entertainment"),
    ("u.s. soccer", "Sports (NBA/NHL/ESPN/Soccer)"),
    ("nba", "Sports (NBA/NHL/ESPN/Soccer)"),
    ("nhl", "Sports (NBA/NHL/ESPN/Soccer)"),
    ("espn", "Sports (NBA/NHL/ESPN/Soccer)"),
    ("fort worth stock show", "Rodeo / Stock Show"),
]

# --- Independent canonicalization: merge spelling/location variants ---
# (regex pattern, canonical name). First match wins, so order matters.
INDIE_CANON = [
    (r"\bmsg (entertainment|live)\b", "MSG Entertainment"),
    (r"another planet", "Another Planet Entertainment"),
    (r"\bi\.?m\.?p\.?\b", "I.M.P."),
    (r"first avenue", "First Avenue Productions"),
    (r"knitting factory", "Knitting Factory"),
    (r"crossroads presents", "Crossroads Presents"),
    (r"jam productions", "Jam Productions"),
    (r"monqui", "Monqui Presents"),
    (r"outback (presents|concerts)", "Outback Presents"),
    (r"bill blumenreich", "Bill Blumenreich Presents"),
    (r"awakening events", "Awakening Events"),
    (r"\bdsp shows", "DSP Shows"),
    (r"mike thrasher", "Mike Thrasher Presents"),
    (r"nederlander", "Nederlander Concerts"),
    (r"seattle theatre group", "Seattle Theatre Group"),
    (r"rams head", "Rams Head Promotions"),
    (r"premier productions", "Premier Productions"),
    (r"c[aá]rdenas marketing", "Cardenas Marketing Network (CMN)"),
    (r"beaver productions", "Beaver Productions"),
    (r"danny wimmer", "Danny Wimmer Presents"),
    (r"\bmammoth\b", "Mammoth"),
    (r"red mountain entertainment", "Red Mountain Entertainment"),
    (r"\bac entertainment\b", "AC Entertainment"),
    (r"\binsomniac\b", "Insomniac"),
    (r"emporium presents", "Emporium Presents"),
    (r"marshall arts", "Marshall Arts"),
    (r"madison house", "Madison House Presents"),
    (r"black promoters collective", "Black Promoters Collective"),
    (r"g-squared", "G-Squared Events"),
    (r"\bns2\b", "NS2"),
    (r"loud and live", "Loud and Live"),
    (r"move concerts", "Move Concerts"),
    (r"rimas entertainment", "Rimas Entertainment"),
    (r"zamora live", "Zamora Live"),
    (r"broadway across america", "Broadway Across America"),
    (r"broadway (across|in) ", "Broadway Across America"),
    (r"ruth eckerd", "Ruth Eckerd Hall Presents"),
    (r"varnell", "Varnell Enterprises"),
    (r"\bliveco\b", "LiveCo"),
    (r"icon concerts", "ICON Concerts"),
    (r"\bg[ée]lb\b|gelb promotions", "Gelb Promotions"),
    (r"transparent productions", "Transparent Productions"),
    (r"police productions", "Police Productions"),
    (r"thrill hill", "Thrill Hill Productions"),
    (r"bill silva|andrew hewitt", "Bill Silva / Andrew Hewitt"),
    (r"larry magid", "Larry Magid Entertainment"),
    (r"bobby dee", "Bobby Dee Presents"),
    (r"pepper entertainment", "Pepper Entertainment"),
    (r"music vip", "Music VIP Entertainment"),
    (r"huka", "HUKA Entertainment Group"),
    (r"a\.?c\.? entertainment", "AC Entertainment"),
    (r"sbs entertainment", "SBS Entertainment"),
    (r"hennepin", "Hennepin Theatre Trust"),
    (r"omaha performing arts", "Omaha Performing Arts"),
    (r"\bdcf concerts", "DCF Concerts"),
    (r"tate entertainment", "Tate Entertainment"),
    (r"tgb promotions", "TGB Promotions"),
    (r"relevant entertainment", "Relevant Entertainment"),
    (r"emc presents", "EMC Presents"),
    (r"lucky man", "Lucky Man Concerts"),
    (r"plastered touring", "Plastered Touring"),
    (r"rush concerts", "Rush Concerts"),
]
_INDIE_RE = [(re.compile(p), n) for p, n in INDIE_CANON]

_INHOUSE_RE = re.compile(r"\(in-house[^)]*\)(\s*/\s*[^,]+)?", re.I)


def _clean(s):
    return s.replace("&amp;", "&").strip(" ,.-")


def classify(promoter):
    s = (promoter or "").strip()
    if not s or s == "(none)":
        return ("Venue / In-House", "In-House")
    sl = s.lower()

    # 1) Tier 1 majors lead any co-promotion
    for b in LN_BRANDS:
        if b in sl:
            return ("Live Nation", "Major")
    for b in AEG_BRANDS:
        if b in sl:
            return ("AEG Presents", "Major")

    # 2) non-music content owners
    for pat, name in NONMUSIC:
        if pat in sl:
            return (name, "Non-music")

    # 3) known independents (canonical)
    for rx, name in _INDIE_RE:
        if rx.search(sl):
            return (name, "Independent")

    # 4) strip in-house tokens; if nothing real remains -> In-House bucket
    rest = _INHOUSE_RE.sub("", s).strip(" ,")
    if not rest:
        return ("Venue / In-House", "In-House")

    # 5) fallback: primary = first promoter token, keeping trailing LLC/Inc.
    parts = re.split(r",\s*(?!(?:llc|inc\.?|ltd\.?|l\.l\.c\.?)\b)", rest, flags=re.I)
    primary = _clean(parts[0]) if parts else _clean(rest)
    return (primary or "Other Independent", "Independent")
