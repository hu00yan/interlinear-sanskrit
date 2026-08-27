# interlinear-sanskrit

A static interlinear reader for two Sanskrit works whose displayed editions
are locked to their contextual Digital Corpus of Sanskrit analyses:

- **Bhagavadgītā** — Sanskrit, occurrence-level morphology, and K. T. Telang's
  1882 English translation
- **Buddhacarita** — Sanskrit, occurrence-level morphology, E. B. Cowell's
  1894 English translation, and Dharmakṣema's Chinese translation

The reader deliberately does not guess analyses for other editions or unknown
text. Each displayed grammar row is addressed by work, passage reference, and
token index and carries its immutable DCS source identifier.

## Run

```bash
npm install
npm run dev
```

Then open the URL printed by Vite.

## Verify

```bash
npm run build
node tests/occurrence-dcs-verify.mjs
npx playwright test tests/source-locked-dcs.spec.ts
```

## Data

- Morphology: Digital Corpus of Sanskrit / Oliver Hellwig, CC BY 4.0
- Bhagavadgītā contextual analysis: Samsaadhanii/SCL export, GPL-2.0
- English translations: public domain
- Buddhacarita Chinese translation: public domain
- Dictionary: Monier-Williams (1899), public domain, Cologne digitization

See `qa-report/source-locked-dcs.md` for the source-lock boundary.
