import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const root = new URL("..", import.meta.url).pathname;
const report = JSON.parse(readFileSync(`${root}qa-report/occurrence-dcs.json`, "utf8"));
for (const work of report) {
  if (work.alignment_pct >= 99.5) {
    const indexPath = `${root}public/data/morph-occurrence/by-work/${work.workId}/index.json`;
    assert(existsSync(indexPath), `${work.workId}: missing occurrence index`);
    const index = JSON.parse(readFileSync(indexPath, "utf8"));
    assert.equal(index.source, "dcs");
  } else {
    assert(work.excluded, `${work.workId}: low alignment must be excluded`);
  }
}
console.log("occurrence DCS verification passed");
