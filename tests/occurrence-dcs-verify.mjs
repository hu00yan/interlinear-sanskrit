import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const root = new URL("..", import.meta.url).pathname;
const report = JSON.parse(readFileSync(`${root}qa-report/occurrence-dcs.json`, "utf8"));
for (const work of report) {
  if (work.alignment_pct === 100) {
    const indexPath = `${root}public/data/morph-occurrence/by-work/${work.workId}/index.json`;
    assert(existsSync(indexPath), `${work.workId}: missing occurrence index`);
    const index = JSON.parse(readFileSync(indexPath, "utf8"));
    assert.equal(index.source, "dcs");
    assert.equal(index.edition, "dcs-source-locked");
  } else {
    assert(work.excluded, `${work.workId}: non-100% mapping must be excluded`);
  }
}

const bhg = JSON.parse(readFileSync(
  `${root}public/data/morph-occurrence/by-work/bhagavadgita/0000.json`, "utf8",
));
assert.equal(bhg["1.1"]["9"][0].r, 4470, "BhG 1.1 kim must retain its DCS row");
assert.equal(bhg["1.1"]["9"][0].confidence, 1);
assert.equal(bhg["18.72"]["6"][0].r, 4329, "BhG 18.72 śrutam must retain its DCS row");
assert.equal(bhg["18.72"]["6"][0].confidence, 1);
console.log("occurrence DCS verification passed");
