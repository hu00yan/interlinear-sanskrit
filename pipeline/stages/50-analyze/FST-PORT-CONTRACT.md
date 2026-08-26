# FST-PORT adapter contract — stage 50-analyze (RESERVED slot)

The user is optimizing a Samsaadhanii port externally. This document fixes
the I/O contract so **their binary drops into `stages/50-analyze/` without
any pipeline rework**: implement `analyze(work_id, cfg, inp, out)` with the
semantics below (mirror `pipeline/stages/adapters/bhagavata.py` for the
module skeleton) and register `"fst-port"` in `stage.py:ADAPTERS`.

## Input (`--in`, produced by 30-tokenize / upstream lane)

One JSON object; the analysis stream for one work:

```json
{
  "workId": "bhagavata",
  "tokens": [
    { "ref": "1.1.1",      // owning unit ref
      "i": 0,              // token index within the unit (words[i])
      "deva": "धर्मक्षेत्रे",// surface form, exactly as in texts words[]
      "slp1": "DarmakSetre", // SLP1 proper-case (see below)
      "key": "darmaksetre"   // canonical shard key = sanscript.slp1_key(deva)
    }
  ]
}
```

`slp1` = SLP1 **preserving case semantics** (long vowels etc. uppercase:
`saMskRtam`-style); `key` = the LOWERCASE shard key the reader resolves by
(`pipeline/sanscript.slp1_key()`). Both are provided so the FST sees
proper-case input while results file straight into shard keys.

## Output (`--out`)

Per-token analyses array — **one entry per input token, same order**:

```json
{ "workId": "bhagavata",
  "analyses": [
    { "ref": "1.1.1", "i": 0,
      "key": "darmaksetre",
      "parses": [
        { "l": "धर्म", "p": "noun",          // EXACT public/data/morph
          "f": "7;एक",                       // shard value schema:
          "x": "",                           // {l,p,f,x,g?} — l lemma
          "g": "dharma (optional)" },        // Unicode, p POS vocab of
        { "l": "क्षेत्र", "p": "noun",       // build_morph.py, f features
          "f": "7;एक", "x": "" }             // 'digit;sambodhana-style'
      ],
      "source": "fst-port",                  // MANDATORY provenance
      "confidence": 0.93                     // MANDATORY, 0..1 float
    },
    { "ref": "1.1.1", "i": 3, "key": "ezAm",
      "parses": null,                        // UNKNOWN FORM: explicit null
      "source": "fst-port", "confidence": 0.0 }
  ]
}
```

## Hard rules

1. **Schema-exact parses.** Each element of `parses[]` must be byte-shape
   compatible with `public/data/morph/{a-z}.json` values (`src/api.ts`
   `Parse`: `l`,`p`,`f`,`x`,`g?`). Same tag vocabulary (Devanagari feature
   tags like `prA...`; POS ∈ noun/verb/part/indecl as mapped by
   build_morph.py). No extra keys inside a parse.
2. **No silent absence.** Unknown/unanalysable forms get an entry with
   `"parses": null` (never an omitted index, never an empty array pretending
   success). Downstream turns explicit nulls into honest no-parse cards.
3. **Provenance mandatory.** Every entry carries `source:"fst-port"` and a
   numeric `confidence`. Entries lacking either are rejected by QA.
4. **Determinism & idempotence.** Same input → byte-identical output; no
   wall-clock or ordering nondeterminism.
5. **Failure mode:** binary missing/crashing ⇒ stage exits ≠0 (worker's
   abort policy applies). Never emit partial output on crash.
6. **Emission path:** downstream 70-emit merges these analyses into
   `public/data/morph` shards keyed by `key`; provenance/confidence are
   stripped from shipped shards but retained in run artifacts + logs.
