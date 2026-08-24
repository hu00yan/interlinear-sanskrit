# MOVED TO `public/data/trans/`

`arnold.json` (still present in this directory) is **not grammar data**. Its own
`"type": "translation"` field and warning say so: it contains only Sir Edwin
Arnold's 1885 English rendering of the Bhagavad Gita, *The Song Celestial*
(PD-old; Arnold d. 1904) — no § sections, no sandhi/declension content.

**Recategorization:** it has been re-homed as translation data at
[`public/data/trans/bhagavadgita-arnold.json`](../trans/bhagavadgita-arnold.json)
(`workId: bhagavadgita`, 18 chapters → cantos `C1–C18`, stanzas → pseudo-verse
units `C<c>.S<s>`, `alignment: loose-poetic`).

**Action requested of the collector:** delete `grammar/arnold.json` and stop
emitting it into any grammar catalog/index. If a replacement grammar scrape
(e.g. Monier-Williams or *A Sanskrit Manual*) lands here under a different
name, no further action is needed.
