"""Build the Popgirlies corpus (docs/selection.md).

1. For each act in reference/roster.csv, read its Wikipedia discography (or, failing that, its
   artist article) and collect every song row with a US Billboard Hot 100 and UK Singles peak.
2. Keep rows where the act holds the lead credit and the song reached US top 40 or UK top 20.
3. Genre test: the song's own Wikipedia infobox genre must include a pop style (docs/genres.md).
4. Cap 20 songs per act (best peak first), dedupe duets, assign generations, balance to targets.
Writes songs.csv, reference/candidates.csv (every candidate and its fate) and
reference/selection-log.csv (edge cases and the rule that decided them).
"""
import csv, io, os, re, sys, urllib.parse, warnings
import pandas as pd
from common import ROOT, TODAY, fetch, wiki_raw, slug, norm, write_json

warnings.filterwarnings("ignore")
WIKI = "https://en.wikipedia.org/w/index.php?title=%s&action=render"
GENERATIONS = [("prologue", 1960, 1982, 90), ("mtv", 1983, 1992, 102), ("cd", 1993, 2001, 102),
               ("idol", 2002, 2009, 102), ("streaming", 2010, 2017, 102), ("tiktok", 2018, 2025, 102)]
CAP = 20
POP = re.compile(r"\bpop\b|dance-pop|synth-?pop|electropop|teen pop|bubblegum|disco|hi-nrg|eurodance|"
                 r"girl group|brill building|new jack swing|new wave|power pop|pop[- ]punk|hyperpop|"
                 r"europop|k-pop|j-pop|motown|doo-?wop|baroque|chamber pop|art pop|dream pop|indie pop|"
                 r"electroclash|house|eurodisco|r&b|soul|soft rock|adult contemporary|country pop|"
                 r"latin pop|reggaeton|trap", re.I)
# strictly pop-family labels (the rest above are accepted only alongside one of these, or alone for
# the prologue era where infoboxes say "soul" or "R&B" for girl-group and Motown pop)
CORE_POP = re.compile(r"pop|disco|hi-nrg|eurodance|girl group|brill building|bubblegum|new wave|"
                      r"motown|doo-?wop|new jack swing|house", re.I)


def page_html(title, depth=0):
    h = fetch(WIKI % urllib.parse.quote(title.replace(" ", "_")))
    m = re.search(r'class="redirectMsg".*?href="[^"]*/wiki/([^"#]+)', h or "", re.S)
    if m and depth < 2:
        return page_html(urllib.parse.unquote(m.group(1)).replace("_", " "), depth + 1)
    return h


def find_pages(artist):
    """Discography page first, then the artist article (with common disambiguations)."""
    tried = []
    for t in (artist + " discography", artist + " singles discography", artist,
              artist + " (singer)", artist + " (band)", artist + " (group)", artist + " (musician)"):
        h = page_html(t)
        tried.append(t)
        if h and re.search(r"chart positions|peak positions|chart peaks", h, re.I):
            yield t, h
            if "discography" in t:
                return


def col_name(c):
    return " | ".join(map(str, c)) if isinstance(c, tuple) else str(c)


def chart_col(cols, code):
    pat = re.compile(r"(^|\| )%s( Hot 100| Singles)?(\s*\[[^\]]*\])*$" % code)
    for i, c in enumerate(cols):
        if pat.search(c.strip()):
            return i
    return None


def peak(v):
    t = v[0] if isinstance(v, tuple) else v
    m = re.match(r"\s*(\d{1,3})", str(t))
    return int(m.group(1)) if m else None


def song_rows(artist, html):
    html = re.sub(r'(rowspan|colspan)\s*=\s*["\']?(\d+)[^\s>]*', r'\1="\2"', html)  # malformed spans
    try:
        tables = pd.read_html(io.StringIO(html), extract_links="body")
    except ValueError:
        return
    for t in tables:
        cols = [col_name(c) for c in t.columns]
        if not any(re.search(r"\bYear\b", c) for c in cols):
            continue
        us, uk = chart_col(cols, "US"), chart_col(cols, "UK")
        if us is None and uk is None:
            continue
        ti = next(i for i, c in enumerate(cols) if "Title" in c or "Single" in c or "Song" in c) \
            if any(("Title" in c or "Single" in c or "Song" in c) for c in cols) else 0
        yi = next(i for i, c in enumerate(cols) if re.search(r"\bYear\b", c))
        for _, r in t.iterrows():
            cell = r.iloc[ti]
            text, href = (cell if isinstance(cell, tuple) else (str(cell), None))
            text = re.sub(r"\[\w+\]", "", text or "").strip()
            if not text.startswith('"'):
                continue
            ym = re.search(r"(19|20)\d\d", str(r.iloc[yi][0] if isinstance(r.iloc[yi], tuple) else r.iloc[yi]))
            yield {"title_cell": text, "href": href, "year": int(ym.group(0)) if ym else None,
                   "us": peak(r.iloc[us]) if us is not None else None,
                   "uk": peak(r.iloc[uk]) if uk is not None else None}


def lead_credit(title_cell, artist):
    """'"Song" (X featuring Artist)' means the act is featured, not lead."""
    paren = re.findall(r"\((.*?)\)", title_cell.split('"')[-1] if '"' in title_cell else "")
    for p in paren:
        low = p.lower()
        # charity and ensemble records: Band Aid, Artists for Grenfell, X Factor finalists, USA for Africa
        if low.startswith(("as part of", "amongst", "among ", "as a member of", "as one of", "credited to")):
            return False
        if low.startswith(("featuring", "feat.", "with ", "and ", "vs")):
            continue
        if re.search(r"\b(featuring|feat\.|with|and|&|x)\b", low) and norm(artist)[:6] in norm(p):
            if not norm(p).startswith(norm(artist)[:6]):
                return False
    return True


def song_title(title_cell):
    m = re.match(r'"(.+?)"', title_cell)
    return m.group(1) if m else title_cell.strip('"')


def article_from_href(href):
    if not href or "/wiki/" not in href or "redlink" in href:
        return None
    return urllib.parse.unquote(href.split("/wiki/")[-1].split("#")[0]).replace("_", " ")


def infobox_genres(article, artist=""):
    t = wiki_raw(article) or ""
    for _ in range(2):
        m = re.match(r"\s*#REDIRECT\s*\[\[([^\]#|]+)", t, re.I)
        if not m:
            break
        article = m.group(1); t = wiki_raw(article) or ""
    boxes = re.findall(r"\{\{\s*Infobox (?:song|single)(.*?)\n\}\}", t, re.S | re.I)
    a = norm(artist)[:6]
    mine = [b for b in boxes if a and a in norm(re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1",
                                                    (re.search(r"\|\s*artist\s*=([^\n]*)", b) or [None, ""])[1]))]
    out = []
    for b in (mine or boxes)[:1]:
        g = re.search(r"\n\s*\|\s*genre\s*=(.*?)(?=\n\s*\|)", b, re.S)
        if g:
            raw = re.sub(r"<ref.*?(</ref>|/>)|<!--.*?-->", "", g.group(1), flags=re.S)
            raw = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", raw)
            raw = re.sub(r"\{\{(?:hlist|flatlist|ubl|unbulleted list|nowrap)\|", "", raw, flags=re.I)
            out = [x.strip(" *{}|\n") for x in re.split(r"\||\n|,|\*", raw) if x.strip(" *{}|\n")]
    return article, out


def qualifies(genres, year):
    if not genres:  # the roster is the pop filter of last resort; genre layer fills these later
        return True, "no infobox genre: kept as a roster act, flagged"
    joined = "; ".join(genres)
    if CORE_POP.search(joined):
        return True, "pop style in infobox"
    if year and year <= 1982 and re.search(r"soul|r&b|rhythm and blues", joined, re.I):
        return True, "prologue: soul/R&B girl-group or Motown pop"
    if POP.search(joined):
        return True, "pop-adjacent style in infobox"
    return False, "no pop style in infobox (%s)" % joined[:60]


def generation(year):
    for name, a, b, _ in GENERATIONS:
        if year and a <= year <= b:
            return name
    return None


def main():
    roster = list(csv.DictReader(open(os.path.join(ROOT, "reference", "roster.csv"))))
    cands, log = [], []
    for act in roster:
        artist = act["artist"]
        pages = list(find_pages(artist))
        if not pages:
            log.append({"artist": artist, "song": "", "decision": "no page with chart table", "rule": "source"})
            print("NO PAGE", artist, flush=True); continue
        seen = set()
        for page, html in pages:
            for r in song_rows(artist, html):
                key = norm(song_title(r["title_cell"]))
                if key in seen:
                    continue
                seen.add(key)
                r.update(artist=artist, act_type=act["act_type"], page=page)
                cands.append(r)
        print(artist, len(seen), "rows", "from", [p for p, _ in pages], flush=True)
    # chart + lead filters
    pool = []
    for c in cands:
        c["title"] = song_title(c["title_cell"])
        c["lead"] = lead_credit(c["title_cell"], c["artist"])
        c["charted"] = (c["us"] is not None and c["us"] <= 40) or (c["uk"] is not None and c["uk"] <= 20)
        c["in_window"] = bool(c["year"] and 1960 <= c["year"] <= 2025)
        if c["charted"] and c["lead"] and c["in_window"]:
            pool.append(c)
        elif c["charted"] and not c["lead"]:
            log.append({"artist": c["artist"], "song": c["title"], "decision": "excluded", "rule": "not lead credit"})
    # dedupe true duets: the same song article in the same year, where one act's row names the other.
    # Different acts' recordings of one song (covers: Cilla Black and Dionne Warwick) are kept apart.
    kept = []
    for c in pool:
        c["article"] = article_from_href(c["href"])
        dup = next((k for k in kept if c["article"] and k["article"] == c["article"] and k["year"] == c["year"]
                    and (norm(k["artist"])[:6] in norm(c["title_cell"]) or norm(c["artist"])[:6] in norm(k["title_cell"]))), None)
        if dup:
            log.append({"artist": c["artist"], "song": c["title"], "decision": "duplicate", "rule": "duet counted once, under %s" % dup["artist"]})
            continue
        kept.append(c)
    pool = kept
    # genre test, best peak first per act, until the cap is reached
    def best(c):
        return min(x for x in (c["us"], c["uk"]) if x is not None)
    acts = {}
    for c in pool:
        acts.setdefault(c["artist"], []).append(c)
    chosen = []
    for artist, songs in acts.items():
        songs.sort(key=lambda c: (best(c), c["us"] or 999, c["uk"] or 999, c["year"]))
        n = 0
        for c in songs:
            if n >= CAP:
                c["fate"] = "over cap"; continue
            if not c["article"]:
                c["fate"] = "no song article"; log.append({"artist": artist, "song": c["title"], "decision": "excluded", "rule": "no Wikipedia article for genre test"}); continue
            c["article"], c["genres"] = infobox_genres(c["article"], artist)
            ok, why = qualifies(c["genres"], c["year"])
            c["genre_rule"] = why
            if ok:
                c["fate"] = "eligible"; chosen.append(c); n += 1
            else:
                c["fate"] = "genre"; log.append({"artist": artist, "song": c["title"], "decision": "excluded", "rule": why})
        print(artist, n, "eligible", flush=True)
    # balance per generation: best-charting first
    final = []
    for name, a, b, target in GENERATIONS:
        g = sorted([c for c in chosen if a <= c["year"] <= b], key=lambda c: (best(c), c["us"] or 999, c["uk"] or 999, c["year"]))
        for c in g[target:]:
            c["fate"] = "beyond generation target"
        final += g[:target]
        print(name, len(g), "eligible ->", min(len(g), target), flush=True)
    final.sort(key=lambda c: (c["year"], best(c)))
    ids = set()
    rows = []
    for c in final:
        c["fate"] = "selected"
        sid = "%d-%s" % (c["year"], slug(c["title"]))
        if sid in ids:
            sid += "-" + slug(c["artist"])
        ids.add(sid); c["id"] = sid
        rows.append({"id": sid, "title": c["title"], "artist": c["artist"], "act_type": c["act_type"],
                     "chart_year": c["year"], "generation": generation(c["year"]), "us_peak": c["us"] or "",
                     "uk_peak": c["uk"] or "", "genres_raw": "; ".join(c["genres"]), "styles": "",
                     "country": "", "region": "", "selection": c["genre_rule"], "pilot": "no",
                     "wikidata": "", "musicbrainz": "", "status": "listed"})
    with open(os.path.join(ROOT, "songs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(ROOT, "reference", "candidates.csv"), "w", newline="") as f:
        keys = ["artist", "title", "year", "us", "uk", "lead", "charted", "article", "fate", "genre_rule", "page"]
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader()
        w.writerows(sorted(cands, key=lambda c: (c["artist"], c.get("year") or 0)))
    with open(os.path.join(ROOT, "reference", "selection-log.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["artist", "song", "decision", "rule"]); w.writeheader(); w.writerows(log)
    write_json(os.path.join(ROOT, "reference", "selection.json"),
               [{"id": c["id"], "year": c["year"], "title": c["title"], "artist": c["artist"], "article": c["article"],
                 "us_peak": c["us"], "uk_peak": c["uk"], "genres_raw": c["genres"], "source": "https://en.wikipedia.org/wiki/" + c["page"].replace(" ", "_"),
                 "retrieved": TODAY, "confidence": "sourced"} for c in final])
    print(len(rows), "songs selected")


if __name__ == "__main__":
    main()
