// About page: data sources & licenses, references, tech stack, acknowledgments.
// Built exclusively with textContent — no innerHTML anywhere.

const REPO_URL = "https://github.com/hu00yan/interlinear-sanskrit";

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
/** Footer link back to the catalog — used by home + about. */
export function aboutLink(): El {
  const a = el("a", "about-link") as HTMLAnchorElement;
  a.href = "#/";
  a.textContent = "← Back to the library";
  return a;
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
    " (Göttingen Register of Electronic Texts in Indian Languages, " +
    "attribution license): Bhagavadgītā, the principal Upaniṣads and the " +
    "Ṛgveda are ingested today; more works planned.",
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
    "Translations — K. T. Telang, The Bhagavadgîtâ (Sacred Books of the " +
    "East vol. 8, 1882) and Sir Edwin Arnold, The Song Celestial (1885); " +
    "both public domain.",
  ]));
  ul.appendChild(liWithLinks([
    "Sandhi / FST tooling (planned) — ",
    aLink("https://github.com/samsaadhanii/scl", "Samsaadhanii"),
    " (University of Hyderabad, GPLv2). Used at build time only.",
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
  ul.appendChild(li(
    "Bring-your-own-key LLM relay planned (/api passthrough, keys stay client-side).",
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

export function renderAbout(app: HTMLElement): void {
  app.replaceChildren();
  app.appendChild(el("h1", undefined, "About Sanskrit Reader"));
  app.appendChild(p(
    "An interlinear reading environment for Sanskrit — sandhi-split tokens " +
    "with dictionary morphology and Monier-Williams glosses aligned under " +
    "every word, entirely from static JSON with no backend.",
  ));
  app.appendChild(repoBanner());
  app.appendChild(h2("Data sources & licenses"));
  app.appendChild(licenseList());
  app.appendChild(h2("Inspiration & reference sites"));
  app.appendChild(inspirationList());
  app.appendChild(h2("Tech stack"));
  app.appendChild(techList());
  app.appendChild(h2("Acknowledgments"));
  app.appendChild(acknowledgments());
}
