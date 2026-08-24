# trans-wave3.md — translation acquisition wave 3

Date: 2026-08-24 · Owner: trans lane (wave-3 subagent)

| work | status | translator / source | year | units covered | alignment |
|---|---|---|---|---|---|
| kamasutra | fetched | Burton, Indrajit & Bhide (Kama Shastra Society) — Gutenberg #27827 | 1883 | 1263/1546 refs (81.7%; chapter blocks distributed sequentially over sutras) | loose |
| abhijnanasakuntala | fetched | Arthur W. Ryder — Gutenberg #16659 | 1912 | 1179/1182 (99.8%; per-act distribution; nāndī + act boundaries exact) | loose |
| caurapancasika | fetched | E. Powys Mathers, *Black Marigolds* — sacred-texts mirror (wenaus.org full text) | 1919 | 50/51 stanzas 1:1 by position (44.2 = extra stanza of 51-stanza S.-Indian recension, absent in Mathers) | loose |
| raghuvamsa | fetched (partial) | G. R. Nandargikar, ed. w/ per-verse English trans., 1897 — archive.org `TheraghuvamsaOfKalidasa` OCR | 1897 | 934/1570 verses (59.5%); remainder unrecoverable from scan OCR | loose |
| rtusamhara | fetched (partial) | Arthur W. Ryder, *The Seasons* (selected stanzas only) — Gutenberg #16659 | 1912 | 6 canto-units anchored at each canto's first ref; Ryder translated only selections (≈30 of 144 stanzas) | loose |
| tantrakhyayika | fetched | Arthur W. Ryder, *Panchatantra* (same trans as existing trans/pancatantra.json); TK = NW recension, Ryder = Southern recension → mapped per book/story | 1925 | 122/122 (per-book weighted distribution; intra-book approximate) | loose |
| kiratarjuniya | UNAVAILABLE (no PD English) | — | — | 0 | — |
| sisupalavadha | UNAVAILABLE (no PD English) | — | — | 0 | — |

## Unavailable works — searches tried
- **kiratarjuniya**: archive.org title search (`kiratarjuniya|kiratarjununiya|"arjuna's combat"`) — only Sanskrit/commentary editions (Durga Prasad 1895, Nirnaya Sagar 1903/1925), Cappeller 1912 (Harvard Indo-Iranian Series) is a GERMAN verse translation, not English; partial English school translations of cantos 2–3 are 1960+ (copyrighted). No pre-1930 complete English translation exists (first complete English: modern academic editions).
- **sisupalavadha**: web + archive.org search — Nirnaya Sagar 1888–1933 editions are Sanskrit + Mallinatha commentary only; Hultzsch/Vallabhadeva 1926 is text edition; Bhandare 1932 covers cantos 1–4 only and is post-1929 anyway; first COMPLETE English translations are Jan Marcus Zwaan (2000s) and C. Rajendran (Sahitya Akademi 2018), both copyrighted. Documented as unavailable.

## PD verification notes
- Burton 1883, Nandargikar 1897, Ryder 1912, Mathers 1919: published pre-1930 → public domain (US & generally worldwide per author death dates).
- Ryder 1925 (*Panchatantra*): US PD since 2021 (95 yr cap); already used for existing pancatantra.json in wave 2.
- sacred-texts.com was behind a Cloudflare JS challenge; Black Marigolds sourced from the wenaus.org mirror of the same PD 1919 text (PD statement verified on sacred-texts index via search cache).
- Ṛtusaṃhāra completeness check: R.S. Pandit's *Pageant of the Seasons* (1947) bills itself as the first complete English translation ("Ritusamhara has not been fully translated into English") — copyrighted, not used. Kale 1916 / Gajendragadkar 1916 scans on archive.org have unusable Devanagari-only OCR with no English rendering.

## Spot-alignment checks (≥3 per delivered work)
- **kamasutra**: 1.1.1 salutation ↔ "Salutation to Dharma, Artha and Kama" ✓; 2.1.1 kinds-of-union heading ✓; 4.2.x younger-wife passage ✓; chapter count 35/35 matches Sanskrit part/chapter layout (Part VII chs 1–2 folded onto sole 7.1 block).
- **abhijnanasakuntala**: 1.1 nāndī ↔ "Eight forms has Shiva…" EXACT ✓; 1.2 ↔ "Until the wise are satisfied…" EXACT ✓; 7.35b1 final blessing ↔ "May kingship benefit the land…" ✓.
- **caurapancasika**: stanzas 1, 15 (nail-scar/"rough love"), 50 ("hot taste of life") thematically match; late-ordering drift (stanzas ~45–49) due to recension difference, noted in file.
- **raghuvamsa**: 1.1 ↔ "For the right understanding of words and their meanings, I bow down…" EXACT ✓; 1.34 offspring-ceremony/Dilipa ✓; 14.1 sons of Dasharatha ✓ (canto starts correct).
- **rtusamhara**: SUMMER section ↔ canto 1 anchor ref 1.1; SPRING ↔ 6.x; attribution honest at canto level only.
- **tantrakhyayika**: 1.1.x frame story ↔ Ryder Book I opening ✓; 2.x crow/owl ↔ Ryder Book II ("Spot") ✓.

## Commits (this wave)
kamasutra afd8438 · shakuntala bc242b8 (+ab8a20e parent-side autostash noise none) · caurapancasika 68ccdf7 + cc8294d (note) · rtusamhara 44d3ca6 · raghuvamsa eb68fd1 · tantrakhyayika 132566f — 7 commits pushed to main.
