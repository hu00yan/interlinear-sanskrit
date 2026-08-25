// Home page: catalog of authors and works with a live search filter.
// Matching is a case-insensitive substring test over author names and work
// titles (stripAccents passes Devanagari through untouched, so both IAST
// and Devanagari queries reach the same normalized titles). "/" focuses
// the search box.
// Two sections share this view: Sanskrit (root) and Pali (#/pali/). A
// compact संस्कृत | पालि toggle next to the title switches between them;
// each section lists only its own language's works.
import {
  catalogLang, loadCatalog, stripAccents, workRoute,
  zhNameOf, zhTitleOf,
  type CatalogAuthor, type CatalogWork,
} from "./api";
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

/** Compact संस्कृत ⇄ पालि switch shown beside the site title. */
function langToggle(paliActive: boolean): HTMLElement {
  const nav = el("nav", "lang-toggle");
  nav.setAttribute("aria-label", "Language section");
  const mk = (href: string, label: string, active: boolean) => {
    const a = el("a", active ? "lang-btn active" : "lang-btn",
      label) as HTMLAnchorElement;
    a.href = href;
    if (active) a.setAttribute("aria-current", "page");
    return a;
  };
  nav.appendChild(mk("#/", "संस्कृत", !paliActive));
  nav.appendChild(mk("#/pali/", "पालि", paliActive));
  return nav;
}

/** Bilingual title pair for a work link / card: titleZh (when the catalog
 *  ships it) is primary — larger, lang="zh" — with the original small and
 *  muted beneath; without titleZh the original renders alone. All writes
 *  are textContent-only. */
function workTitles(w: CatalogWork): HTMLElement {
  const zh = zhTitleOf(w);
  if (!zh) return el("span", "work-title", w.title);
  const titles = el("span", "work-titles");
  const zhEl = el("span", "work-title-zh", zh);
  zhEl.lang = "zh";
  titles.appendChild(zhEl);
  titles.appendChild(el("span", "work-title-orig", w.title));
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

  // ---- muted start-here line (class kept: main.ts inserts the
  // "Continue reading" section before .starters) ----
  app.appendChild(el("p", "starters",
    isPali ? "Start with the Dhammapada." : "Start with the Bhagavad Gītā."));

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

  // ---- cards: start-here work (from catalog at runtime) ----
  const cards = el("div", "cards");
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

    // Start-here card: FIRST work in this section following catalog order
    // (Bhagavadgītā on the Sanskrit home, Dhammapada under #/pali/).
    // Route built from the live id — no hardcoded slugs. Bilingual like the
    // work links: titleZh primary, original beneath; original only when
    // titleZh is absent.
    for (const a of catalog.authors) {
      const work = a.works.find((w) => inSection(w, a));
      if (!work) continue;
      const card = el("a", "card") as HTMLAnchorElement;
      card.href = workRoute(work, a);
      card.dataset.startCard = "1";
      card.appendChild(el("div", "title"));
      (card.querySelector(".title") as HTMLElement).appendChild(
        workTitles(work),
      );
      card.appendChild(
        el("div", "meta",
          `${work.unitCount.toLocaleString()} verses · word-by-word ` +
          `analysis & gloss`),
      );
      cards.prepend(card);
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
