"""Genre layer (docs/genres.md): raw labels from the song's Wikipedia infobox (sourced), Wikidata
P136 (sourced) and MusicBrainz genres/tags (crowd), normalised into style families.
Writes songs/<id>/genre.json and the `styles` column of songs.csv."""
import csv, os, re, sys
from common import *

FAMILIES = [  # (family, pattern) — first match per label wins; a song can have several families
    ("girl-group and early pop", r"girl group|doo-?wop|brill building|motown|wall of sound|bubblegum(?! pop)|merseybeat|beat music|traditional pop|vocal pop"),
    ("disco and dance", r"disco|hi-?nrg|eurodance|dance-?pop|dance|house|edm|club|garage|eurodisco|freestyle"),
    ("synth and electronic", r"synth|electro|hyperpop|bitpop|electronic|techno|trance"),
    ("teen and bubblegum", r"teen pop|bubblegum pop"),
    ("R&B-pop", r"r&b|rhythm and blues|soul|new jack swing|funk|hip[- ]hop|rap|trap|quiet storm|gospel"),
    ("rock-pop", r"pop rock|power pop|pop[- ]punk|new wave|rock|grunge|punk"),
    ("country-pop", r"country"),
    ("singer-songwriter and ballad", r"soft rock|adult contemporary|ballad|folk|acoustic|singer-songwriter|easy listening"),
    ("art and baroque", r"art pop|baroque|chamber pop|dream pop|indie|alternative|alt-pop|experimental|psychedelic"),
    ("Latin and global", r"latin|reggaeton|k-pop|j-pop|europop|afro|reggae|dancehall|bossa"),
    ("other pop", r"\bpop\b"),
]


def families(labels):
    out = []
    for lab in labels:
        l = lab.lower()
        for fam, pat in FAMILIES:
            if re.search(pat, l):
                if fam not in out:
                    out.append(fam)
                break
    return out


def main():
    songs = load_songs()
    for s in songs:
        sid = s["id"]
        w = read_json(os.path.join(SONGS, sid, "wikipedia.json"))
        f = read_json(os.path.join(SONGS, sid, "facts.json"))
        if not w and not f:
            continue
        ib = (w or {}).get("infobox") or {}
        raw_ib = [x.strip(" *") for x in re.split(r"\n|,|\|", re.sub(r"\{\{[^}]*?\|", "", ib.get("genre") or "")) if x.strip(" *{}")]
        wd = [c.get("label") for c in ((f or {}).get("wikidata") or {}).get("claims", {}).get("genre", []) if isinstance(c, dict) and c.get("label")]
        mb = (f or {}).get("musicbrainz") or {}
        mbg = mb.get("genres") or []
        primary = raw_ib or wd or mbg
        basis = "wikipedia infobox" if raw_ib else "wikidata" if wd else "musicbrainz" if mbg else None
        fams = families(primary)
        all_fams = families(raw_ib + wd + mbg)
        out = {"labels": {"wikipedia_infobox": {"values": raw_ib, "confidence": "sourced"},
                          "wikidata": {"values": wd, "confidence": "sourced"},
                          "musicbrainz": {"values": mbg, "tags": mb.get("tags", []), "confidence": "crowd"}},
               "families": fams, "families_basis": basis, "families_any_source": all_fams,
               "method": "first matching family per label, docs/genres.md; families from the best available source "
                         "(infobox, else Wikidata, else MusicBrainz)", "retrieved": TODAY, "confidence": "computed"}
        write_json(os.path.join(SONGS, sid, "genre.json"), out)
        s["styles"] = "; ".join(fams)
    with open(os.path.join(ROOT, "songs.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(songs[0])); wr.writeheader(); wr.writerows(songs)


if __name__ == "__main__":
    main()
