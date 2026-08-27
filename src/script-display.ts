// Global presentation preference for generated Sanskrit and Pali text. Source
// dictionary quotations deliberately do not receive this marker or conversion.
import { iastToDev } from "./translit";

export type ScriptMode = "iast" | "deva" | "both";
const KEY = "reader-script-mode";
const modes: ScriptMode[] = ["iast", "deva", "both"];

function current(): ScriptMode {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && modes.includes(saved as ScriptMode)) return saved as ScriptMode;
  } catch { /* localStorage may be unavailable */ }
  return "iast";
}

function paint(mode = current()): void {
  document.body.dataset.scriptMode = mode;
  // The existing unit renderer owns its registry. Drive its public controls so
  // it rebuilds Sanskrit rows, while this module supplies Pali display clones.
  const wanted = { iast: mode !== "deva", deva: mode !== "iast" };
  for (const key of ["iast", "deva"] as const) {
    const input = document.querySelector<HTMLInputElement>(`#script-${key}`);
    if (input && input.checked !== wanted[key]) {
      input.checked = wanted[key];
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  decorate(document);
}

export function setScriptMode(mode: ScriptMode): void {
  try { localStorage.setItem(KEY, mode); } catch { /* persistence is optional */ }
  paint(mode);
  document.dispatchEvent(new CustomEvent("reader-script-mode", { detail: mode }));
}

export function scriptModeControl(): HTMLElement {
  const root = document.createElement("div");
  root.className = "script-mode-control";
  root.setAttribute("role", "group");
  root.setAttribute("aria-label", "Generated text script");
  const labels: Array<[ScriptMode, string]> = [
    ["iast", "IAST"], ["deva", "देवनागरी"], ["both", "Both"],
  ];
  const refresh = (): void => {
    const mode = current();
    root.querySelectorAll<HTMLButtonElement>("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
  };
  for (const [mode, label] of labels) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.mode = mode;
    button.textContent = label;
    button.addEventListener("click", () => { setScriptMode(mode); refresh(); });
    root.appendChild(button);
  }
  document.addEventListener("reader-script-mode", refresh);
  refresh();
  return root;
}

/** Mark existing generated pairs and add Pali's display-only Devanagari line. */
function decorate(root: ParentNode): void {
  if (root instanceof HTMLElement && root.matches(".unit-scripts")) markScripts(root);
  root.querySelectorAll<HTMLElement>(".unit-scripts").forEach((scripts) => {
    markScripts(scripts);
  });
  root.querySelectorAll<HTMLElement>(
    ".lemma-stack, .feat-dual, .comp-form",
  ).forEach((node) => { node.dataset.generatedScript = "analysis"; });
  root.querySelectorAll<HTMLElement>(".pcard .lemma:not(.lemma-stack), .comp-form .lemma:not(.lemma-stack)")
    .forEach((lemma) => {
      if (lemma.closest(".wl-mw, .lex-mw, .mw-entry")) return;
      const text = lemma.textContent?.trim() ?? "";
      if (!text || lemma.querySelector(".lemma-iast")) return;
      lemma.classList.add("lemma-stack");
      lemma.replaceChildren(scriptPart("lemma-iast", text, "sa-Latn"),
        scriptPart("lemma-deva", iastToDev(text), "sa"));
    });
  root.querySelectorAll<HTMLElement>(".script-generated").forEach((node) => {
    node.dataset.generatedScript = "analysis";
  });
  // MW/DPD forms are quoted source material. Do not mark, convert, or hide
  // their original spellings, even when the source happens to use Devanagari.
  root.querySelectorAll<HTMLElement>(".wl-mw [data-generated-script], .lex-mw [data-generated-script], .mw-entry [data-generated-script]")
    .forEach((node) => { delete node.dataset.generatedScript; });
}

function markScripts(scripts: HTMLElement): void {
  scripts.dataset.generatedScript = "token";
  scripts.querySelectorAll<HTMLElement>(".wcell").forEach((cell) => {
    if (cell.querySelector(".deva-line")) return;
    const iast = cell.querySelector<HTMLElement>(".iast-line");
    const raw = iast?.dataset.orig ?? iast?.textContent ?? "";
    if (!iast || !raw) return;
    const deva = iast.cloneNode(true) as HTMLElement;
    deva.classList.remove("iast-line");
    deva.classList.add("deva-line", "script-display-clone");
    deva.textContent = iastToDev(raw);
    deva.addEventListener("click", () => iast.click());
    cell.appendChild(deva);
  });
}

function scriptPart(cls: string, text: string, lang: string): HTMLElement {
  const part = document.createElement("span");
  part.className = cls;
  part.lang = lang;
  part.textContent = text;
  return part;
}

function install(): void {
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      record.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) decorate(node);
      });
    }
    document.querySelectorAll<HTMLElement>(".controls").forEach((bar) => {
      if (!bar.querySelector(".script-mode-control")) {
        const old = bar.querySelector(".script-pref-controls");
        (old ?? bar).after(scriptModeControl());
      }
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
  paint();
}

if (typeof document !== "undefined") install();
