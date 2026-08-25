// Home page: catalog of authors and works with a live search filter.
// Matching is a case-insensitive substring test over author names and work
// titles (stripAccents passes Devanagari through untouched, so both IAST
// and Devanagari queries reach the same normalized titles). "/" focuses
// the search box.
// Two sections share this view: Sanskrit (root) and Pali (#/pali/). A
// compact संस्कृत | पालि toggle next to the title switches between them;
// each section lists only its own language's works.
import {
  catalogLang, isUntranslated, loadCatalog, stripAccents, workRoute,
  zhNameOf, zhTitleOf,
  type CatalogAuthor, type CatalogWork,
} from "./api";
import { wordLookupWidget } from "./lookup";
import { lexiconButton } from "./lexicon";
import { themeControl } from "./theme";
import { aboutLink } from "./about";

export type HomeSection = "sa" | "pi";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

/** Compact bilingual संस्कृत/Sanskrit ⇄ पालि/Pāli switch beside the site
 *  title: Devanagari primary with a small Latin sublabel beneath — each
 *  segment readable in either script, still compact on phones. */
function langToggle(paliActive: boolean): HTMLElement {
  const nav = el("nav", "lang-toggle");
  nav.setAttribute("aria-label", "Language section");
  const mk = (
    href: string,
    deva: string,
    latin: string,
    active: boolean,
  ) => {
    const a = el("a", active ? "lang-btn active" : "lang-btn") as HTMLAnchorElement;
    a.href = href;
    const d = el("span", "lang-btn-deva", deva);
    const l = el("span", "lang-btn-latin", latin);
    l.lang = "en";
    a.append(d, l);
    if (active) a.setAttribute("aria-current", "page");
    return a;
  };
  nav.appendChild(mk("#/", "संस्कृत", "Sanskrit", !paliActive));
  nav.appendChild(mk("#/pali/", "पालि", "Pāli", paliActive));
  return nav;
}

/** Bilingual title pair for a work link / card: titleZh (when the catalog
 *  ships it) is primary — larger, lang="zh" — with the original small and
 *  muted beneath; without titleZh the original renders alone. Only truly
 *  untranslated works (no EN and no zh) carry a subtle 「无译文」 badge
 *  beside the title. All writes are textContent-only. */
function workTitles(w: CatalogWork): HTMLElement {
  const zh = zhTitleOf(w);
  const titles = el("span", "work-titles");
  if (!zh) titles.appendChild(el("span", "work-title", w.title));
  else {
    const zhEl = el("span", "work-title-zh", zh);
    zhEl.lang = "zh";
    titles.appendChild(zhEl);
    titles.appendChild(el("span", "work-title-orig", w.title));
  }
  // 「无译文」 badge ONLY for truly untranslated works (no EN and no zh);
  // zh-only works default to the 汉译 layer in the reader instead.
  if (isUntranslated(w)) {
    const badge = el("span", "no-trans-badge", "无译文");
    badge.lang = "zh";
    badge.title = "No translation available for this work yet";
    titles.appendChild(badge);
  }
  return titles;
}

/** Author-group heading: nameZh preferred (zh span, exempt from the h2's
 *  uppercase transform) with the original beside; original alone when no
 *  nameZh ships. */
function authorHeading(author: CatalogAuthor): HTMLElement {
  const head = el("h2");
  head.id = author.key;
  const zh = zhNameOf(author);
  if (zh) {
    const zhEl = el("span", "author-name-zh", zh);
    zhEl.lang = "zh";
    head.appendChild(zhEl);
    head.appendChild(el("span", "author-name-orig", author.name));
  } else {
    head.textContent = author.name;
  }
  return head;
}

export function renderHome(app: HTMLElement, section: HomeSection = "sa"): void {
  const isPali = section === "pi";
  app.replaceChildren();

  // ---- header row: site title + language toggle ----
  const head = el("div", "home-head");
  head.appendChild(el("h1", undefined, isPali ? "Pali Reader" : "Sanskrit Reader"));
  head.appendChild(langToggle(isPali));
  app.appendChild(head);
  app.appendChild(
    el("p", "subtitle", isPali
      ? "An interlinear reading environment for the Pali Canon — " +
        "Roman-script Pali with Sujato's English translation, " +
        "segment-aligned, all static JSON."
      : "An interlinear reading environment for Sanskrit — every word " +
        "carries its grammatical analysis and an English gloss, all " +
        "static JSON."),
  );

  // ---- prominent search box + header controls ----
  // Both scripts accepted: IAST transliteration or Devanagari.
  // (Full-text search integration arrives later; placeholder only.)
  const searchWrap = el("div", "home-search");
  const input = el("input") as HTMLInputElement;
  input.type = "search";
  input.placeholder = "Search in IAST or Devanagari";
  input.setAttribute("aria-label", "Filter catalog by author or work");
  input.autocomplete = "off";
  input.spellcheck = false;
  searchWrap.appendChild(input);
  searchWrap.appendChild(themeControl());
  searchWrap.appendChild(lexiconButton());
  // no visible "/" button here — the shortcut lives in the document
  // keydown listener below; a chip invited pointless clicking.
  app.appendChild(searchWrap);

  // ---- muted start-here line (linked to its work once the catalog loads;
  // main.ts inserts the "Continue reading" section before .starters) ----
  const starters = el("p", "starters",
    isPali ? "Start with the Dhammapada." : "Start with the Bhagavad Gītā.");
  app.appendChild(starters);

  // "/" focuses search (until the home view is torn down)
  const onKey = (e: KeyboardEvent): void => {
    if (!input.isConnected) {
      document.removeEventListener("keydown", onKey);
      return;
    }
    if (e.key !== "/") return;
    const t = e.target as HTMLElement | null;
    const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" ||
      t.isContentEditable);
    if (!typing) {
      e.preventDefault();
      input.focus();
      input.select();
    }
  };
  document.addEventListener("keydown", onKey);

  // ---- result count ----
  const count = el("p", "search-count");
  count.setAttribute("aria-live", "polite");
  app.appendChild(count);

  // ---- word-lookup box (the slot above the footer) ----
  // Ported from greek-reader, where this spot held the parser entry card.
  // The old static start-here work card (rendered "薄伽梵歌"/Bhagavadgītā)
  // ceded its place: type any Sanskrit/Pali word — Devanagari or IAST — and
  // morph parse cards + Monier-Williams entries appear right here, no
  // navigation. The start-here suggestion stays available as a link in the
  // .starters line (wired to the catalog below).
  const cards = el("div", "cards");
  cards.appendChild(wordLookupWidget());
  app.appendChild(cards);

  // footer: about / sources & licenses
  const footer = el("p", "about-footer");
  footer.appendChild(aboutLink());
  app.appendChild(footer);

  // ---- catalog: only this section's language reaches the page ----
  loadCatalog().then((catalog) => {
    const inSection = (w: CatalogWork, a: CatalogAuthor): boolean =>
      isPali ? catalogLang(w, a) === "pi" : catalogLang(w, a) !== "pi";
    const authors = [...catalog.authors]
      .map((a) => ({
        author: a,
        works: a.works.filter((w) => inSection(w, a)),
      }))
      .filter((e) => e.works.length > 0)
      .sort((a, b) => a.author.name.localeCompare(b.author.name));
    for (const { author, works } of authors) {
      app.appendChild(authorBlock(author, works));
    }

    // Start-here line becomes a real link (first in-section work following
    // catalog order — Bhagavadgītā on the Sanskrit home, Dhammapada under
    // #/pali/). Route built from the live id — no hardcoded slugs.
    for (const a of catalog.authors) {
      const work = a.works.find((w) => inSection(w, a));
      if (!work || !starters.isConnected) continue;
      const link = el("a", "starter-link", work.title) as HTMLAnchorElement;
      link.href = workRoute(work, a);
      starters.replaceChildren("Start with the ", link, ".");
      break;
    }
    applyFilter();
  }).catch((e: Error) => {
    app.appendChild(el("p", "unparsed-note",
      `Could not load catalog.json: ${e.message}`));
  });

  /** One author section: heading + its (already section-filtered) works. */
  function authorBlock(
    author: CatalogAuthor,
    works: CatalogWork[],
  ): HTMLElement {
    const block = el("section", "author-block");
    block.dataset.authorName = stripAccents(author.name);
    const nameZh = zhNameOf(author);
    if (nameZh) block.dataset.authorNameZh = nameZh; // raw zh — search target
    block.appendChild(authorHeading(author));
    const list = el("div", "work-list");
    for (const w of sortedWorks(works)) {
      const link = el("a", "work-link") as HTMLAnchorElement;
      link.href = workRoute(w, author);
      link.dataset.title = stripAccents(w.title);
      const zh = zhTitleOf(w);
      if (zh) link.dataset.titleZh = zh; // raw zh — search filter target
      link.appendChild(workTitles(w));
      link.appendChild(el("span", "work-meta",
        `${w.unitCount.toLocaleString()} units`));
      link.title = w.license;
      list.appendChild(link);
    }
    block.appendChild(list);
    return block;
  }

  /** Natural sort so multi-part works read in order. */
  function sortedWorks(works: CatalogWork[]) {
    return [...works].sort((a, b) =>
      a.title.localeCompare(b.title, undefined, { numeric: true }));
  }

  /** Live filter: substring match on author name OR work title. */
  function applyFilter(): void {
    const q = stripAccents(input.value.trim());
    let nAuthors = 0;
    let nWorks = 0;
    for (const block of Array.from(
      app.querySelectorAll<HTMLElement>(".author-block"),
    )) {
      const authorHit = !q || block.dataset.authorName!.includes(q) ||
        (!!block.dataset.authorNameZh &&
          block.dataset.authorNameZh.includes(q));
      let shownInBlock = 0;
      for (const link of Array.from(
        block.querySelectorAll<HTMLAnchorElement>(".work-link"),
      )) {
        // match original title AND Chinese title (plain substring; zh needs
        // no accent folding — stripAccents already lowercased the query)
        const hit = authorHit || !q ||
          link.dataset.title!.includes(q) ||
          (!!link.dataset.titleZh && link.dataset.titleZh.includes(q));
        link.hidden = !hit;
        if (hit) shownInBlock += 1;
      }
      block.hidden = shownInBlock === 0;
      if (!block.hidden) {
        nAuthors += 1;
        nWorks += shownInBlock;
      }
    }
    count.textContent = q
      ? `${nAuthors} author${nAuthors === 1 ? "" : "s"} · ` +
        `${nWorks} work${nWorks === 1 ? "" : "s"} matching “${input.value.trim()}”`
      : `${nAuthors} authors · ${nWorks} works`;
  }

  let debounce = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(debounce);
    debounce = window.setTimeout(applyFilter, 60);
  });
}
