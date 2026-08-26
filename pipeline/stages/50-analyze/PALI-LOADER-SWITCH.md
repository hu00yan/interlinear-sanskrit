# Pali reader integration — minimal loader switch (DO NOT edit src yet)

`pali_dpd.py` emits `public/data/morph-pali/**` as a SECOND shard dir,
schema-identical to `public/data/morph/**`. `src/api.ts loadMorph()` is
hardcoded to `data/morph/…`, and its roman-script path cannot resolve Pali
tokens today anyway. Three minimal changes make Pali parse cards render
with ZERO shard edits:

## Why nothing renders today (roman/Pali path audit)

For non-Devanagari forms `surfaceKeyCandidates()` (api.ts) returns
`[stripAccents(form)]`:

* `"bhāsati,"` → `"bhasati,"` — trailing punctuation kept →
  `surfaceKeyTrusted` fails (canonicalKeysFor strips punctuation) → no
  card. Punctuated tokens (~30% of Pali corpus tokens) can never match.
* Bare `"bhāsati"` → `"bhasati"`, but the honesty gate compares against
  `canonicalKeysFor` = `{slp1KeyFor(form)}` = `"basati"` (SLP1 folds ā→a).
  Mismatch → no card. Only ASCII-short-vowel words could ever pass.
* Shard keys themselves are lowercase-SLP1 (house convention), so the
  accent-stripped spelling could not hit them even without the gate.

## Minimal switch (≈3 files, no schema change)

1. **translit.ts** — add the niggahīta fold to the roman branch of
   `canonicalKeysFor` (our texts write ṁ U+1E41, DPD/shards key on ṃ):
   ```ts
   } else {
     const folded = form.replace(/\u1e41/g, "\u1e43");
     add(slp1KeyFor(folded)); // ṁ-folded SLP1 flavor == morph-pali keys
   }
   ```
2. **api.ts** — thread a base dir through loadMorph/loadShardMap:
   ```ts
   export async function loadMorph(forms: string[], scope?: string,
       dir = "data/morph"): Promise<Map<string, Parse[]>> {
   ```
   and in the roman branch of `surfaceKeyCandidates` return the canonical
   key directly (it already passes surfaceKeyTrusted):
   ```ts
   if (!isDevanagari(form)) {
     const k = [...canonicalKeysFor(form)][0] ?? "";
     return k ? [k] : [];
   }
   ```
   (letter-shard fetch becomes `${dir}/${l}.json`; `_surface` slices stay
   Devanagari-only — morph-pali/_surface/** ships for exactness/future
   use, the canonical-key path above does not need it.)
3. **main.ts** — pass the dir for Pali works where `scope` is currently
   forced undefined:
   ```ts
   const pi = catalogLang(state.work, state.author) === "pi";
   const freshCtx = await prepare(batch, pi ? undefined : state.work.id,
                                  pi ? "data/morph-pali" : undefined);
   ```
   (prepare/render.ts thread the same optional arg to loadMorph.)

## Honest-miss semantics preserved

Unresolved forms simply miss (no entry) → empty parse column, exactly the
current Sanskrit behavior; the existing `<0.5 coverage` morph-empty-note
fires per work until Pass B widens feats.
