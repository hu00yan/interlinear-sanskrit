// Translation is deliberately a separate reading layer: it only ever appears
// in this resizable right sidebar, never between source text and word cards.
import { type CatalogWork, type Unit } from "./api";
import { loadTranslationUnits } from "./translation";
import { loadZhMap, translationZhOf } from "./zh-layer";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const MIN_W = 240;
const clampWidth = (px: number): number => Math.max(MIN_W, Math.min(innerWidth * .5, px));

export interface SidebarHandle {
  refresh(): Promise<void>;
  destroy(): void;
}
let activeTeardown: (() => void) | null = null;

export function setupSidebar(work: CatalogWork, opts: {
  controls: El; getUnits: () => Unit[];
}): SidebarHandle | null {
  const enFiles = ((work as { translation?: { files?: unknown } }).translation?.files ?? [])
    .filter((f): f is string => typeof f === "string");
  const zhMeta = translationZhOf(work);
  const zhFiles = (zhMeta?.files ?? []).filter((f): f is string => typeof f === "string");
  if (!enFiles.length && !zhFiles.length) return null;

  let open = false;
  let layer: "en" | "zh" = enFiles.length ? "en" : "zh";
  let width = Math.min(400, innerWidth * .38);
  let aside: El | null = null;
  let divider: El | null = null;
  let body: El | null = null;
  let enTexts: Promise<Array<{ ref: string; text: string }>> | null = null;
  let zhMap: Promise<Map<string, string> | null> | null = null;

  const trigger = el("button", "translation-sidebar-btn", "Translation") as HTMLButtonElement;
  trigger.type = "button";
  trigger.setAttribute("aria-expanded", "false");
  trigger.addEventListener("click", () => void setOpen(!open));
  opts.controls.appendChild(trigger);

  const applyWidth = (value: number): void => {
    width = clampWidth(value);
    document.documentElement.style.setProperty("--sb-w", `${Math.round(width)}px`);
  };
  const ensureDom = (): void => {
    if (aside?.isConnected) return;
    aside = el("aside", "tr-sidebar hidden");
    aside.setAttribute("aria-label", "Translation sidebar");
    const head = el("div", "tr-sidebar-head");
    head.appendChild(el("h2", undefined, "Translation"));
    if (enFiles.length && zhFiles.length) {
      const layers = el("span", "theme-ctl tl-ctl");
      for (const [key, label] of [["en", "English"], ["zh", "Chinese"]] as const) {
        const button = el("button", undefined, label) as HTMLButtonElement;
        button.type = "button";
        button.setAttribute("aria-pressed", String(layer === key));
        button.addEventListener("click", () => {
          layer = key;
          layers.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
          void paint();
        });
        layers.appendChild(button);
      }
      head.appendChild(layers);
    }
    const close = el("button", "close-btn sb-close", "x") as HTMLButtonElement;
    close.type = "button";
    close.setAttribute("aria-label", "Close translation sidebar");
    close.addEventListener("click", () => void setOpen(false));
    head.appendChild(close);
    aside.appendChild(head);
    body = el("div", "tr-sidebar-body");
    aside.appendChild(body);
    document.body.appendChild(aside);
    divider = el("div", "sb-divider hidden");
    divider.setAttribute("role", "separator");
    divider.setAttribute("aria-label", "Drag to resize the sidebar");
    divider.addEventListener("pointerdown", (event) => {
      divider!.setPointerCapture(event.pointerId);
      const move = (e: PointerEvent): void => applyWidth(innerWidth - e.clientX);
      const up = (): void => { divider?.removeEventListener("pointermove", move); divider?.removeEventListener("pointerup", up); };
      divider!.addEventListener("pointermove", move);
      divider!.addEventListener("pointerup", up);
    });
    document.body.appendChild(divider);
    applyWidth(width);
  };

  async function paint(): Promise<void> {
    if (!open) return;
    ensureDom();
    const box = body!;
    const units = opts.getUnits();
    const [ens, zhs] = await Promise.all([
      layer === "en" ? (enTexts ??= loadTranslationUnits(enFiles).catch(() => [])) : Promise.resolve([]),
      layer === "zh" ? (zhMap ??= loadZhMap(zhFiles)) : Promise.resolve(null),
    ]);
    if (!open || !box.isConnected) return;
    box.replaceChildren();
    units.forEach((unit, i) => {
      const row = el("div", "tr-unit sb-row");
      if (unit.ref) row.appendChild(el("span", "tr-ref", unit.ref));
      const text = layer === "zh" ? zhs?.get(unit.ref) : ens.find((t) => t.ref === unit.ref)?.text ?? ens[i]?.text;
      row.appendChild(el("div", "tr-text", text || "—"));
      box.appendChild(row);
    });
  }
  async function setOpen(next: boolean): Promise<void> {
    open = next;
    trigger.setAttribute("aria-expanded", String(open));
    trigger.textContent = open ? "Close translation" : "Translation";
    ensureDom();
    document.body.classList.toggle("sidebar-view", open);
    aside!.classList.toggle("hidden", !open);
    divider!.classList.toggle("hidden", !open);
    if (open) await paint();
  }
  function destroy(): void {
    if (activeTeardown === destroy) activeTeardown = null;
    aside?.remove(); divider?.remove();
    document.body.classList.remove("sidebar-view");
  }
  activeTeardown = destroy;
  return { refresh: paint, destroy };
}

export function teardownSidebar(): void { activeTeardown?.(); activeTeardown = null; }
