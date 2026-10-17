# Sources

Everything in Earworm's `docs/sources.md` applies (including its "Lessons from scaling to 650"). Additions for this corpus:

| Layer | Source | Confidence | Access (tested 17 Oct 2026) |
|---|---|---|---|
| Selection, US and UK peaks | Wikipedia artist discography pages (cite Billboard and the Official Charts Company) | sourced | Reachable |
| US weekly runs | Billboard Hot 100 weekly history (utdata/rwd-billboard-data) | sourced | Reachable (already cached in Earworm) |
| UK weekly runs | Official Charts Company weekly chart pages | sourced | Weekly pages reachable; artist pages 404. Use sparingly, at Wikipedia pace |
| Genre | Song infobox, MusicBrainz tags, Wikidata P136 | sourced / crowd | Reachable |
| Authorship | MusicBrainz work credits, Wikipedia infobox writer/producer | sourced | Reachable |
| Artist eras | Wikidata albums, MusicBrainz release groups | sourced | Reachable |
| Vocal range, key changes | Wikipedia "Composition" sections (often citing Musicnotes) | sourced | Reachable |
| Lyric themes | First-pass tags from timed lyrics and article text | first pass | n/a |
| Chords | Expert sets, Chordonomicon (Spotify ID matching; a Spotify key Shaf creates would raise coverage), Hooktheory (Shaf's login) | expert / crowd | As in Earworm |
| Cover analysis | Cover Art Archive, iTunes; brightness, saturation, palette, dark share; planned: face present, text share | computed | As in Earworm |
