"""Authorship layer: who wrote and produced each song, and whether the star (or, for a girl group,
any member) is among them. Writers from the MusicBrainz work (composer/lyricist/writer) and the
Wikipedia infobox; producers from MusicBrainz recording credits, Wikidata and the infobox.
Group members come from MusicBrainz 'member of band' relations.
Writes songs/<id>/authorship.json."""
import os, re, urllib.parse
from common import *

MB = "https://musicbrainz.org/ws/2/"


def split_names(v):
    v = re.sub(r"\{\{[^|}]*\|", "", v or "")
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    parts = [p.strip(" *}{") for p in re.split(r"\n|,|\||\band\b|&|\{\{|\}\}|<br\s*/?>", v)]
    return [p for p in parts if len(p) > 2 and not re.match(r"(?i)^(hlist|flatlist|ubl|plainlist|unbulleted list)$", p)]


def members(mbid):
    if not mbid:
        return []
    a = fetch_json(MB + "artist/%s?inc=artist-rels&fmt=json" % mbid) or {}
    return sorted({(r["artist"]["name"], r["artist"]["id"]) for r in a.get("relations", [])
                   if r.get("type") == "member of band" and r.get("direction") == "backward"})


def same(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or (len(a) > 5 and (a in b or b in a)))


def main():
    for s in load_songs():
        sid = s["id"]
        f = read_json(os.path.join(SONGS, sid, "facts.json"))
        w = read_json(os.path.join(SONGS, sid, "wikipedia.json")) or {}
        if not f:
            continue
        mb = f.get("musicbrainz") or {}
        ib = w.get("infobox") or {}
        writers = {c["name"] for c in (mb.get("work") or {}).get("credits", []) if c["role"] in ("composer", "lyricist", "writer")}
        ib_writers = split_names(ib.get("writer") or ib.get("writers") or ib.get("songwriter"))
        # Wikipedia mixes stage names and legal names (Frank Dukes / Adam Feeney), so counting both
        # double-counts people. Count MusicBrainz's legal-name credits when it has them, else Wikipedia's.
        if not writers:
            writers = set(ib_writers)
        producers = {c["name"] for c in mb.get("recording_credits", []) if c["role"] == "producer"}
        producers |= {c.get("label") for c in ((f.get("wikidata") or {}).get("claims") or {}).get("producer", []) if isinstance(c, dict) and c.get("label")}
        for n in split_names(ib.get("producer")):
            if not any(same(n, p_) for p_ in producers if p_):
                producers.add(n)
        star = [a["name"] for a in mb.get("artists", [])[:1]] or [s["artist"]]
        main_mbid = (mb.get("artists") or [{}])[0].get("mbid")
        crew = members(main_mbid) if s.get("act_type") == "group" else []
        people = star + [n for n, _ in crew]
        ids = {main_mbid} | {i for _, i in crew}
        # MusicBrainz credits point at artist entities, so stage names match by ID (Lady Gaga / Stefani Germanotta)
        id_writers = {c["name"] for c in (mb.get("work") or {}).get("credits", []) if c.get("mbid") in ids and c["role"] in ("composer", "lyricist", "writer")}
        id_producers = {c["name"] for c in mb.get("recording_credits", []) if c.get("mbid") in ids and c["role"] == "producer"}
        star_writes = sorted(id_writers | {p for p in people for w_ in writers if same(p, w_)})
        star_produces = sorted(id_producers | {p for p in people for p_ in producers if same(p, p_)})
        write_json(os.path.join(SONGS, sid, "authorship.json"), {
            "writers": sorted(writers), "producers": sorted(p for p in producers if p),
            "n_writers": len(writers), "n_producers": len([p for p in producers if p]),
            "act": star[0], "group_members": [n for n, _ in crew],
            "star_is_writer": bool(star_writes), "star_writer_names": star_writes,
            "star_is_producer": bool(star_produces), "star_producer_names": star_produces,
            "source": "MusicBrainz work and recording credits (CC0), Wikidata, Wikipedia infobox",
            "retrieved": TODAY, "confidence": "sourced",
            "note": "Name matching is loose (stage names, initials); check star_writer_names when it matters."})
        print(sid, len(writers), "writers;", "star writes" if star_writes else "", flush=True)


if __name__ == "__main__":
    main()
