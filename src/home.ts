// Home page: catalog of authors and works with a live search filter.
// Matching is a case-insensitive substring test over author names and work
// titles (stripAccents passes Devanagari through untouched, so both IAST
// and Devanagari queries reach the same normalized titles). "/" focuses
// the search box.
import { loadCatalog, stripAccents, type CatalogAuthor } from "./api";
import { lexiconButton } from "./lexicon";
import { themeControl } from "./theme";
import { aboutLink } from "./about";

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

export function renderHome(app: HTMLElement): void {
  app.replaceChildren();
  app.appendChild(el("h1", undefined, "Sanskrit Reader"));
  app.appendChild(
    el("p", "subtitle",
      "An interlinear reading environment for Sanskrit — every word " +
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
  app.appendChild(el("p", "starters", "Start with the Bhagavad Gītā."));

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

  // ---- catalog ----
  loadCatalog().then((catalog) => {
    const authors = [...catalog.authors].sort((a, b) =>
      a.name.localeCompare(b.name));
    for (const author of authors) app.appendChild(authorBlock(author));

    // Start-here card: FIRST work in the catalog (Bhagavadgītā today).
    // Route built from the live id — no hardcoded slugs.
    for (const author of catalog.authors) {
      const work = author.works[0];
      if (!work) continue;
      const card = el("a", "card") as HTMLAnchorElement;
      card.href = `#/${work.id}`;
      card.dataset.startCard = "1";
      card.appendChild(el("div", "title", work.title));
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

  /** One author section: heading + its work links. */
  function authorBlock(author: CatalogAuthor): HTMLElement {
    const block = el("section", "author-block");
    block.dataset.authorName = stripAccents(author.name);
    const head = el("h2", undefined, author.name);
    head.id = author.key;
    block.appendChild(head);
    const list = el("div", "work-list");
    for (const w of sortedWorks(author)) {
      const link = el("a", "work-link") as HTMLAnchorElement;
      link.href = `#/${w.id}`;
      link.dataset.title = stripAccents(w.title);
      const t = el("span", "work-title", w.title);
      link.appendChild(t);
      link.appendChild(el("span", "work-meta",
        `${w.unitCount.toLocaleString()} units`));
      link.title = w.license;
      list.appendChild(link);
    }
    block.appendChild(list);
    return block;
  }

  /** Natural sort so multi-part works read in order. */
  function sortedWorks(author: CatalogAuthor) {
    return [...author.works].sort((a, b) =>
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
      const authorHit = !q || block.dataset.authorName!.includes(q);
      let shownInBlock = 0;
      for (const link of Array.from(
        block.querySelectorAll<HTMLAnchorElement>(".work-link"),
      )) {
        const hit = authorHit || !q || link.dataset.title!.includes(q);
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
