// About page: data sources & licenses, references, tech stack, acknowledgments.
// Built exclusively with textContent — no innerHTML anywhere.
import { exportJSON as exportVocab, importJSON as importVocab } from "./vocab";
import {
  exportJSON as exportBookmarks,
  importJSON as importBookmarks,
} from "./bookmarks";

const REPO_URL = "https://github.com/hu00yan/interlinear-sanskrit";  // verified live

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};
const h2 = (t: string): El => el("h2", undefined, t);
const p = (t: string): El => el("p", "about-p", t);
const li = (t: string): El => el("li", undefined, t);
/** Small footer navigation from the library to the About page. */
export function aboutLink(): El {
  const a = el("a", "about-link") as HTMLAnchorElement;
  a.href = "#/about";
  a.textContent = "About · sources & licenses";
  return a;
}

function libraryBackLink(): El {
  const pEl = el("p", "subtitle");
  const back = el("a") as HTMLAnchorElement;
  back.href = "#/";
  back.textContent = "← Back to the library";
  pEl.appendChild(back);
  return pEl;
}
const aLink = (href: string, text: string): El => {
  const a = el("a") as HTMLAnchorElement;
  a.href = href;
  a.textContent = text;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
};
function liWithLinks(parts: Array<string | El>): El {
  const item = el("li");
  for (const part of parts) {
    if (typeof part === "string") item.appendChild(document.createTextNode(part));
    else item.appendChild(part);
  }
  return item;
}
function licenseList(): El {
  const ul = el("ul", "about-list");
  ul.appendChild(liWithLinks([
    "Texts — ",
    aLink("https://gretil.sub.uni-goettingen.de/gretil.html", "GRETIL"),
    " (Göttingen Register of Electronic Texts in Indian Languages): source " +
    "text provenance for the Bhagavadgītā edition.",
  ]));
  ul.appendChild(liWithLinks([
    "Morphology — ",
    aLink("https://github.com/OliverHellwig/sanskrit",
      "Digital Corpus of Sanskrit"),
    " by Oliver Hellwig (CC BY 4.0): sandhi-split tokens with full " +
    "morphological and lexical analysis.",
  ]));
  ul.appendChild(liWithLinks([
    "Dictionary — Monier-Williams, A Sanskrit-English Dictionary (1899), " +
    "public domain; digitized by the ",
    aLink("https://www.sanskrit-lexicon.uni-koeln.de/",
      "Cologne Digital Sanskrit Dictionaries"),
    " project.",
  ]));
  ul.appendChild(liWithLinks([
    "Translations — K. T. Telang, The Bhagavadgîtâ (1882); E. B. Cowell, " +
    "The Buddhacarita of Asvaghosha (1894); and Dharmakṣema's Chinese " +
    "Buddhacarita. All are public domain.",
  ]));
  return ul;
}
function inspirationList(): El {
  const ul = el("ul", "about-list");
  ul.appendChild(liWithLinks([
    aLink("https://www.nodictionaries.com", "nodictionaries.com"),
    " — early interlinear word-by-word gloss model.",
  ]));
  ul.appendChild(liWithLinks([
    aLink("https://github.com/johnhboyer-sys/plato-reader",
      "johnhboyer-sys/plato-reader"),
    " — minimal static reader pairing original text with morphology.",
  ]));
  ul.appendChild(liWithLinks([
    aLink("https://scaife.perseus.org", "scaife.perseus.org"),
    " (Scaife Viewer) — canonical CTS/TEI reading environment.",
  ]));
  return ul;
}
function techList(): El {
  const ul = el("ul", "about-list");
  ul.appendChild(li("Vite + vanilla TypeScript — no runtime framework."));
  ul.appendChild(li("Static JSON shards: texts, morphology, glosses, translations."));
  ul.appendChild(li("Playwright end-to-end tests for every shipped feature."));
  ul.appendChild(li(
    "PWA offline support: the app shell and current corpus cache in the browser.",
  ));
  return ul;
}
function repoBanner(): El {
  const card = el("div", "repo-banner");
  const main = el("a", "repo-banner-main") as HTMLAnchorElement;
  main.href = REPO_URL;
  main.target = "_blank";
  main.rel = "noopener noreferrer";
  const text = el("span", "repo-banner-text");
  text.appendChild(el("strong", undefined, "Open source"));
  text.appendChild(document.createTextNode(
    " · github.com/hu00yan/interlinear-sanskrit"));
  main.appendChild(text);
  card.appendChild(main);
  return card;
}
function acknowledgments(): El {
  return p(
    "With thanks to the GRETIL maintainers at Göttingen for stewarding the " +
    "machine-readable text tradition; to Prof. Oliver Hellwig for the " +
    "Digital Corpus of Sanskrit and its painstaking tagging; to the Cologne " +
    "Digitization team for the open Sanskrit lexicons; to the legacy of " +
    "Sir Monier-Williams whose dictionary still anchors every lookup; and " +
    "to the worldwide Sanskrit reading community whose feedback shapes " +
    "this reader.",
  );
}

/** Your-data backup row: export/import the vocabulary book and bookmarks
 *  (localStorage-only data) as JSON files. Ported from greek-reader. */
function yourData(): El {
  const wrap = el("div", "about-yourdata");
  wrap.appendChild(p(
    "Your vocabulary book and bookmarks live only in this browser's " +
    "localStorage — nothing is uploaded. Export them as JSON to back up or " +
    "move to another device; importing merges without overwriting.",
  ));
  const row = el("p", "yourdata-row");

  const mkDownload = (
    label: string,
    name: string,
    dump: () => string,
  ): HTMLButtonElement => {
    const b = el("button", "yourdata-btn") as HTMLButtonElement;
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", () => {
      const blob = new Blob([dump()], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    return b;
  };

  const mkImport = (
    label: string,
    merge: (text: string) => { added: number; bad: boolean },
  ): El => {
    const wrapBtn = el("span");
    const b = el("button", "yourdata-btn") as HTMLButtonElement;
    b.type = "button";
    b.textContent = label;
    const input = document.createElement("input") as HTMLInputElement;
    input.type = "file";
    input.accept = ".json,application/json";
    input.hidden = true;
    const status = el("span", "yourdata-status");
    b.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (): void => {
        const res = merge(String(reader.result ?? ""));
        status.textContent = res.bad
          ? "Import failed: not a valid file."
          : `Imported ${res.added} new item${res.added === 1 ? "" : "s"}.`;
      };
      reader.readAsText(file);
      input.value = "";
    });
    wrapBtn.appendChild(b);
    wrapBtn.appendChild(input);
    wrapBtn.appendChild(status);
    return wrapBtn;
  };

  row.appendChild(mkDownload(
    "Export vocabulary",
    "sanskrit-reader-vocab.json",
    exportVocab,
  ));
  row.appendChild(mkImport("Import vocabulary…", importVocab));
  row.appendChild(mkDownload(
    "Export bookmarks",
    "sanskrit-reader-bookmarks.json",
    exportBookmarks,
  ));
  row.appendChild(mkImport("Import bookmarks…", importBookmarks));
  wrap.appendChild(row);
  return wrap;
}

export function renderAbout(app: HTMLElement): void {
  app.replaceChildren();
  app.appendChild(el("h1", undefined, "About Sanskrit Reader"));
  app.appendChild(p(
    "A static interlinear reader for two Sanskrit editions whose displayed " +
    "tokens are locked to contextual DCS morphology. It does not generate or " +
    "guess analyses for unknown text.",
  ));
  app.appendChild(libraryBackLink());
  app.appendChild(repoBanner());
  app.appendChild(h2("Data sources & licenses"));
  app.appendChild(licenseList());
  app.appendChild(h2("Inspiration & reference sites"));
  app.appendChild(inspirationList());
  app.appendChild(h2("Tech stack"));
  app.appendChild(techList());

  app.appendChild(h2("Your vocabulary & bookmarks"));
  app.appendChild(p(
    "Reading features: tap any word for its parse panel and “Mark known ✓” " +
    "to dim words you know, switch the toolbar Vocab toggle to highlight " +
    "what is left, star lines to bookmark them, and share ?ref= deep links " +
    "to exact verses.",
  ));
  app.appendChild(yourData());

  app.appendChild(h2("Acknowledgments"));
  app.appendChild(acknowledgments());
}
