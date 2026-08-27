# Source-Locked DCS Grammar

## Source investigation

The full `OliverHellwig/sanskrit` mirror tree is cached in `.cache-dcs/tree.json` and its CoNLL-U data in `.cache-dcs/dcs-conllu`. Its Bhagavadgita material is in `Mahābhārata/*BhaGī*.conllu`, rather than a standalone Gita directory: it has source sentence surfaces and `OccId` fields. For example, its 1.1 row has `kim` / `OccId=3607283`, and 18.72 has `śrutam` / `OccId=3618075`. The mirror contains no raw GRETIL-to-DCS original-order projection, so its token stream cannot be truthfully attached to the pre-existing reader editions.

Bhagavadgita has a source-locked local DCS/Samsaadhanii export at `.cache-corpus/analysis.json`. Each row supplies a contextual `morph_in_context`, compact English meaning, immutable source-array row, and `poem` source-order position. The reader edition `public/data/texts/tlg9000/bhagavadgita-part01.json` is generated only from those rows, ordered by `poem`, and each displayed token has exactly one occurrence shard entry keyed by `(work, ref, tokenIndex)`.

The two source families agree on the audited readings: the generated 1.1 `किम्` card carries local DCS row `4470` (accusative neuter singular, `what`); 18.72 `श्रुतम्` carries row `4329` (past participle, `heard`). The browser DOM exports record those row keys, while the mirror records its independent immutable `OccId` values above.

## Migration gate

| Work | Edition | Mapping | Inline grammar behavior |
| --- | --- | ---: | --- |
| Bhagavadgita | `dcs-source-locked` from `.cache-corpus/analysis.json` | 9,927 / 9,927 (100%) | One direct contextual DCS row per displayed token; source row is exposed as `data-dcs-row`. |
| Buddhacarita | `dcs-source-locked` from `.cache-dcs/dcs-conllu/Buddhacarita/*.conllu` | 28,638 / 28,638 (100%) | DCS source sentence edition; one direct CoNLL-U occurrence per displayed token. |
| Every other Sanskrit catalog work | Existing edition | not source-locked | `grammarStatus: unavailable-source-mismatch`; no inline grammar cards, with an explicit reader notice. |

Thirty-two editorial/unparsed source rows are excluded before display. They are not displayed tokens, so the migration gate remains exactly 100% of displayed tokens. Global `data/morph/**` remains a dictionary-candidate data source and is no longer used for reader grammar.
