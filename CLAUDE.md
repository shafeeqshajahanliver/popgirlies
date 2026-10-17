# Popgirlies

Private research corpus of 600 hits by women in pop (solo artists and girl groups, US and UK), owned by Shafeeq Shajahan (Shaf). Sister project to Earworm (`shafeeqshajahanliver/earworm`), whose tools in `tools/` were copied here and carry all its matching fixes. `docs/selection.md` holds the inclusion rules; `docs/genres.md` the genre taxonomy; `docs/sources.md` which source is trusted for what. Earworm's `docs/schema.md` and `docs/sources.md` ("Lessons from scaling to 650") apply unless this repo says otherwise.

## Working rules

- Shaf is non-technical. Explain in plain English, lead with what the data shows, keep code out of the conversation unless he asks.
- Never sign in with Shaf's credentials or use his API keys. If a step needs a login (Genius, Hooktheory, Discogs, Spotify), he runs it himself. Never read `.env`.
- Never work around a site that blocks automated access. Record it as a gap. SecondHandSongs: stop at the first 403 and resume next day.
- Keep the repo private. Never commit audio or video; previews live in `_cache/`. Git LFS for images.
- Never edit source files to fix data. Use `songs/<id>/corrections.json`.
- Every fact carries source, retrieval date and confidence: `expert`, `sourced`, `crowd`, `computed`, `claude-knowledge`, `first pass` (interpretive tags such as lyric themes, until Shaf reviews them).
- Inclusion follows `docs/selection.md` exactly. Edge cases are logged in `reference/selection-log.csv` with the rule that decided them, never argued case by case.
- Genre is recorded per song, from its own Wikipedia infobox first, and normalised with `docs/genres.md`. Keep the raw labels.
- Match the charting recording (single version, not remixes or album edits); a charting remix may match its own remix name.
- Requests stay slow: Wikipedia 1 per 3 s, MusicBrainz 1 per second, iTunes 1 per 3 s, with the identifying User-Agent in `tools/common.py`.
- Run scripts from the repo root with `PYTHONPATH=tools`. Regenerate `reports/coverage.md` and `reports/data-audit.md` after any data change.
