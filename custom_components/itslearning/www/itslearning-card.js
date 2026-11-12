/*
 * itslearning-card – Lovelace card for the itslearning integration.
 *
 *   type: custom:itslearning-card
 *   view: day            # day | today | tomorrow | homework | week | next_week | news | next | chips | overview
 *   preset: glass        # default | glass | neon | minimal | solid | notebook | sunset | ocean | midnight
 *
 * Every style option can be set in the visual editor or in YAML; see README.
 */
const CARD_VERSION = "0.4.0";

/* ------------------------------------------------------------------ presets */
const PRESETS = {
  default: {},
  glass: {
    background_color: [255, 255, 255], background_opacity: 10, blur: 16,
    border_width: 1, border_color: [255, 255, 255], border_opacity: 28, border_radius: 22,
    shadow: 30, item_style: "tinted", item_background_opacity: 7,
  },
  neon: {
    background_color: [9, 12, 28], background_opacity: 88, text_color: [226, 244, 255],
    secondary_text_color: [140, 170, 200], accent_color: [0, 229, 255],
    border_width: 1, border_color: [0, 229, 255], border_opacity: 70, border_radius: 14,
    glow: true, glow_color: [0, 229, 255], glow_size: 18, glow_intensity: 55, glow_animation: "pulse",
    item_style: "tinted", item_background_opacity: 6,
    today_color: [255, 64, 129], tomorrow_color: [255, 171, 64], soon_color: [255, 238, 88], later_color: [128, 216, 255],
    overdue_color: [255, 110, 110],
  },
  minimal: {
    background_opacity: 0, border_width: 0, shadow: 0, show_header: true, item_style: "plain", padding: 8,
  },
  solid: {
    background_color: [33, 98, 180], background_opacity: 100, text_color: [255, 255, 255],
    secondary_text_color: [214, 228, 248], border_width: 0, border_radius: 18, shadow: 40,
    item_style: "tinted", item_background_opacity: 10,
    today_color: [255, 214, 102], tomorrow_color: [255, 255, 255], soon_color: [214, 228, 248], later_color: [214, 228, 248],
    overdue_color: [255, 205, 210],
  },
  notebook: {
    background_color: [253, 251, 243], background_opacity: 100, text_color: [40, 44, 52],
    secondary_text_color: [110, 112, 120], accent_color: [52, 101, 164],
    border_width: 1, border_color: [208, 200, 178], border_opacity: 100, border_radius: 6, shadow: 18,
    ruled: true, item_style: "plain",
    today_color: [196, 52, 52], tomorrow_color: [205, 120, 30], soon_color: [52, 101, 164], later_color: [110, 112, 120],
  },
  sunset: {
    background_color: [238, 90, 111], gradient: true, gradient_color: [255, 177, 92], gradient_angle: 135,
    background_opacity: 100, text_color: [255, 255, 255], secondary_text_color: [255, 236, 224],
    border_width: 0, border_radius: 24, shadow: 35, item_style: "tinted", item_background_opacity: 14,
    today_color: [255, 255, 255], tomorrow_color: [255, 244, 214], soon_color: [255, 236, 224], later_color: [255, 236, 224],
    overdue_color: [255, 205, 210],
  },
  ocean: {
    background_color: [20, 92, 158], gradient: true, gradient_color: [56, 189, 200], gradient_angle: 160,
    background_opacity: 100, text_color: [255, 255, 255], secondary_text_color: [214, 240, 248],
    border_width: 0, border_radius: 24, shadow: 35, item_style: "tinted", item_background_opacity: 12,
    today_color: [255, 221, 120], tomorrow_color: [255, 255, 255], soon_color: [214, 240, 248], later_color: [214, 240, 248],
    overdue_color: [255, 205, 210],
  },
  midnight: {
    background_color: [24, 26, 46], gradient: true, gradient_color: [58, 36, 92], gradient_angle: 145,
    background_opacity: 96, text_color: [236, 232, 255], secondary_text_color: [168, 160, 204],
    accent_color: [170, 140, 255], border_width: 1, border_color: [170, 140, 255], border_opacity: 30,
    border_radius: 20, glow: true, glow_color: [140, 100, 255], glow_size: 26, glow_intensity: 35, glow_animation: "breathe",
    item_style: "tinted", item_background_opacity: 6,
    today_color: [255, 128, 171], tomorrow_color: [255, 202, 128], soon_color: [200, 190, 255], later_color: [168, 160, 204],
    overdue_color: [255, 110, 110],
  },
};

const DEFAULTS = {
  view: "day",
  preset: "default",
  title: "",
  show_header: true,
  show_count: true,
  entity_suffix: "",
  max_items: 8,
  days_ahead: 14,
  show_events: true,
  show_tasks: true,
  show_plans: true,
  show_overdue: true,
  show_no_deadline: true,
  show_description: true,
  description_lines: 2,
  show_subject_color: true,
  show_icons: true,
  group_by_day: true,
  link_items: true,
  icon_style: "mdi",              // mdi | emoji
  empty_text: "",
  // look
  font_scale: 100,
  padding: 16,
  item_spacing: 8,
  item_style: "plain",            // plain | tinted | outlined | bar
  item_background_opacity: 8,
  item_radius: 10,
  subject_bar_width: 3,
  background_opacity: 100,
  blur: 0,
  gradient: false,
  gradient_angle: 135,
  border_width: null,             // null = theme
  border_style: "solid",
  border_opacity: 100,
  border_radius: null,
  shadow: null,
  glow: false,
  glow_size: 16,
  glow_intensity: 45,
  glow_animation: "none",         // none | pulse | breathe | rainbow
  ruled: false,
  // urgency colours
  overdue_color: [229, 57, 53],
  today_color: [229, 57, 53],
  tomorrow_color: [245, 124, 0],
  soon_color: [214, 158, 0],
  later_color: null,              // null = secondary text
};

const VIEW_TITLES = {
  day: "Skolan", today: "Idag", tomorrow: "I morgon", homework: "Läxor och prov",
  week: "Planering den här veckan", next_week: "Planering nästa vecka", news: "Från lärarna",
  next: "", chips: "", overview: "Skolan",
};

const VIEW_ICONS = {
  day: "mdi:school-outline", today: "mdi:calendar-today", tomorrow: "mdi:calendar-arrow-right",
  homework: "mdi:book-open-variant", week: "mdi:notebook-outline", next_week: "mdi:notebook-outline",
  news: "mdi:newspaper-variant-outline", overview: "mdi:school-outline",
};

const WEEKDAYS_SHORT = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"];
const WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"];

/* ------------------------------------------------------------------ helpers */
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function color(c, alpha = 100) {
  // Accepts [r,g,b], "#hex", "rgb(...)", "var(--x)" or a named colour.
  if (c === null || c === undefined || c === "") return null;
  let base;
  if (Array.isArray(c)) base = `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  else base = String(c);
  if (alpha >= 100) return base;
  return `color-mix(in srgb, ${base} ${Math.max(0, alpha)}%, transparent)`;
}

function cap(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function localDate(iso) {
  const d = new Date(iso);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function daysFromToday(iso) {
  const t = new Date();
  const today = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  return Math.round((localDate(iso) - today) / 86400000);
}

function dayLabel(iso, long = false) {
  const n = daysFromToday(iso);
  if (n === 0) return "Idag";
  if (n === 1) return "I morgon";
  if (n === -1) return "I går";
  const d = localDate(iso);
  const wd = (d.getDay() + 6) % 7;
  if (n > 1 && n < 7) return cap(long ? WEEKDAYS[wd] : WEEKDAYS_SHORT[wd]);
  return `${cap(WEEKDAYS_SHORT[wd])} ${d.getDate()}/${d.getMonth() + 1}`;
}

function hhmm(iso) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/* ===================================================================== card */
class ItslearningCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("itslearning-card-editor");
  }

  static getStubConfig() {
    return { view: "day", preset: "glass" };
  }

  setConfig(config) {
    if (!config) throw new Error("Ogiltig konfiguration");
    this._userConfig = { ...config };
    const preset = PRESETS[config.preset] || {};
    this._config = { ...DEFAULTS, ...preset, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    if (!old || this._changed(old, hass)) this._render();
  }

  _changed(old, hass) {
    return this._entityIds().some((id) => old.states[id] !== hass.states[id]);
  }

  _entityIds() {
    const s = this._config?.entity_suffix || "";
    return [
      "today", "tomorrow", "upcoming_events", "upcoming_tasks", "overdue_tasks", "tasks_without_deadline",
      "plans_this_week", "plans_next_week", "news", "unread_notifications", "due_tomorrow",
    ].map((k) => `sensor.itslearning_${k}${s}`);
  }

  _state(key) {
    return this._hass?.states[`sensor.itslearning_${key}${this._config.entity_suffix || ""}`];
  }

  _attr(key, attr) {
    return this._state(key)?.attributes?.[attr] ?? [];
  }

  getCardSize() {
    const v = this._config?.view;
    if (v === "chips" || v === "next") return 1;
    return 2 + Math.min(this._config?.max_items || 8, 8);
  }

  getGridOptions() {
    const v = this._config?.view;
    if (v === "chips" || v === "next") return { columns: 12, min_columns: 4, rows: "auto" };
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  /* ------------------------------------------------------------ data model */
  // Every row: {kind, date(iso for grouping), sort, subject, title, time, description, url, color, urgency}
  _rowsDay(key) {
    const c = this._config;
    const b = this._state(key)?.attributes || {};
    const rows = [];
    if (c.show_events) for (const e of b.events || []) rows.push(this._eventRow(e));
    if (c.show_tasks) for (const t of b.tasks || []) rows.push(this._taskRow(t));
    if (c.show_plans) for (const p of b.plans || []) rows.push(this._planRow(p));
    return rows.sort((a, z) => a.sort - z.sort);
  }

  _eventRow(e) {
    return {
      kind: "event", icon: "mdi:clipboard-text-clock-outline", emoji: "📝",
      date: e.start, sort: new Date(e.start).getTime() + (e.all_day ? 0 : 1),
      subject: e.subject || e.course, title: e.title,
      time: e.all_day ? "" : `${hhmm(e.start)}–${hhmm(e.end)}`,
      description: e.description, url: e.url, color: e.color, days: daysFromToday(e.start),
    };
  }

  _taskRow(t, overdue = false) {
    return {
      kind: overdue ? "overdue" : "task", icon: overdue ? "mdi:alert-circle-outline" : "mdi:book-clock-outline",
      emoji: overdue ? "⚠️" : "📚", date: t.deadline, sort: t.deadline ? new Date(t.deadline).getTime() + 2 : Infinity,
      subject: t.subject || t.course, title: t.title,
      time: t.deadline ? `lämnas ${hhmm(t.deadline)}` : "",
      description: "", url: t.url, color: t.color, days: t.deadline ? daysFromToday(t.deadline) : null,
    };
  }

  _planRow(p) {
    return {
      kind: "plan", icon: "mdi:notebook-outline", emoji: "📖",
      date: p.start, sort: new Date(p.start).getTime() + 3,
      subject: p.subject || p.course, title: p.name, time: "",
      description: p.description, url: p.url, color: p.color, days: daysFromToday(p.start),
    };
  }

  _rowsHomework() {
    const c = this._config;
    const rows = [];
    if (c.show_events)
      for (const e of this._attr("upcoming_events", "events"))
        if (daysFromToday(e.start) <= c.days_ahead && daysFromToday(e.end) >= 0) rows.push(this._eventRow(e));
    if (c.show_tasks)
      for (const t of this._attr("upcoming_tasks", "tasks"))
        if (daysFromToday(t.deadline) <= c.days_ahead) rows.push(this._taskRow(t));
    return rows.sort((a, z) => a.sort - z.sort);
  }

  _rowsWeek(key) {
    return this._attr(key, "plans").map((p) => this._planRow(p)).sort((a, z) => a.sort - z.sort);
  }

  /* --------------------------------------------------------------- styling */
  _urgencyColor(days, kind) {
    const c = this._config;
    if (kind === "overdue" || (days !== null && days < 0 && kind !== "plan")) return color(c.overdue_color);
    if (days === 0) return color(c.today_color);
    if (days === 1) return color(c.tomorrow_color);
    if (days !== null && days <= 3) return color(c.soon_color);
    return color(c.later_color) || "var(--itsl-secondary)";
  }

  _css() {
    const c = this._config;
    const fs = (c.font_scale || 100) / 100;
    const bg = c.background_color ?? null;
    const bgA = c.background_opacity ?? 100;
    let background = "";
    if (bg !== null || bgA < 100) {
      const base = bg !== null ? color(bg, bgA) : color("var(--ha-card-background, var(--card-background-color))", bgA);
      background = c.gradient && c.gradient_color
        ? `linear-gradient(${c.gradient_angle}deg, ${base}, ${color(c.gradient_color, bgA)})`
        : base;
    }
    const borderW = c.border_width;
    const border = borderW === null || borderW === undefined
      ? ""
      : borderW === 0
        ? "border: none;"
        : `border: ${borderW}px ${c.border_style} ${color(c.border_color ?? "var(--divider-color)", c.border_opacity)};`;
    const radius = c.border_radius === null || c.border_radius === undefined ? "" : `border-radius: ${c.border_radius}px;`;
    const shadow = c.shadow === null || c.shadow === undefined
      ? ""
      : c.shadow === 0
        ? "box-shadow: none;"
        : `box-shadow: 0 ${Math.round(c.shadow / 6)}px ${c.shadow}px rgba(0,0,0,${Math.min(0.55, c.shadow / 100)});`;
    const blur = c.blur ? `backdrop-filter: blur(${c.blur}px) saturate(140%); -webkit-backdrop-filter: blur(${c.blur}px) saturate(140%);` : "";
    const glowCol = color(c.glow_color ?? c.accent_color ?? "var(--primary-color)", c.glow_intensity);
    const glow = c.glow
      ? `0 0 ${c.glow_size}px ${glowCol}, 0 0 ${Math.round(c.glow_size / 3)}px ${glowCol}`
      : "none";
    const anim = { pulse: "itsl-pulse 2.6s ease-in-out infinite", breathe: "itsl-breathe 5s ease-in-out infinite", rainbow: "itsl-rainbow 8s linear infinite" }[c.glow_animation] || "none";
    const text = color(c.text_color) || "var(--primary-text-color)";
    const secondary = color(c.secondary_text_color) || "var(--secondary-text-color)";
    const accent = color(c.accent_color) || "var(--primary-color)";
    const itemBg = {
      plain: "transparent",
      tinted: `color-mix(in srgb, ${text} ${c.item_background_opacity}%, transparent)`,
      outlined: "transparent",
      bar: `color-mix(in srgb, ${text} ${c.item_background_opacity}%, transparent)`,
    }[c.item_style] || "transparent";
    const itemBorder = c.item_style === "outlined" ? `1px solid color-mix(in srgb, ${text} 18%, transparent)` : "none";
    // Notebook: a red margin line down the left side (rows get rules underneath, see .row).
    const ruled = c.ruled
      ? `background-image: linear-gradient(to right, transparent ${Math.max(4, c.padding - 7)}px, color-mix(in srgb, ${color(c.today_color)} 45%, transparent) ${Math.max(4, c.padding - 7)}px, color-mix(in srgb, ${color(c.today_color)} 45%, transparent) ${Math.max(5, c.padding - 6)}px, transparent ${Math.max(5, c.padding - 6)}px);`
      : "";

    return `
      :host { display: block; --itsl-text: ${text}; --itsl-secondary: ${secondary}; --itsl-accent: ${accent}; }
      ha-card {
        position: relative; overflow: visible; color: var(--itsl-text);
        ${background ? `background: ${background};` : ""} ${border} ${radius} ${shadow} ${blur}
        font-size: ${fs}rem;
      }
      ha-card::before {
        content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
        box-shadow: ${glow}; animation: ${c.glow ? anim : "none"};
      }
      .wrap { position: relative; padding: ${c.padding}px; ${ruled} border-radius: inherit; }
      .head { display: flex; align-items: center; gap: 10px; margin-bottom: ${Math.max(6, c.item_spacing + 2)}px; }
      .head ha-icon { --mdc-icon-size: ${Math.round(22 * fs)}px; color: var(--itsl-accent); }
      .head .t { flex: 1; font-size: 1.12em; font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
      .head .n { font-size: 0.85em; color: var(--itsl-secondary); font-variant-numeric: tabular-nums; }
      .block + .block { margin-top: ${c.padding}px; }
      .bt { font-size: 0.82em; font-weight: 600; color: var(--itsl-secondary); margin: 0 0 6px; }
      .list { display: flex; flex-direction: column; gap: ${c.item_spacing}px; }
      .group { display: grid; grid-template-columns: 4.6em 1fr; column-gap: 10px; align-items: start; }
      .group.nodate { grid-template-columns: 1fr; }
      .day { font-size: 0.82em; font-weight: 600; padding-top: 0.55em; line-height: 1.15; font-variant-numeric: tabular-nums; }
      .items { display: flex; flex-direction: column; gap: ${Math.max(2, Math.round(c.item_spacing * 0.6))}px; min-width: 0; }
      .row {
        position: relative; display: flex; gap: 10px; align-items: flex-start; min-width: 0;
        padding: 0.45em 0.6em 0.45em ${c.show_subject_color ? `calc(0.6em + ${c.subject_bar_width}px)` : "0.6em"};
        background: ${itemBg}; border: ${itemBorder}; border-radius: ${c.item_radius}px;
        color: inherit; text-decoration: none;
      }
      .row.s-plain { padding-top: 0.35em; padding-bottom: 0.35em; }
      ${c.ruled ? `.row { border-radius: 0; border-bottom: 1px solid color-mix(in srgb, ${accent} 22%, transparent); }` : ""}
      a.row:hover { background: color-mix(in srgb, var(--itsl-text) ${Math.max(6, c.item_background_opacity + 6)}%, transparent); }
      a.row:focus-visible { outline: 2px solid var(--itsl-accent); outline-offset: 2px; }
      .sb { position: absolute; left: 0; top: 0.45em; bottom: 0.45em; width: ${c.subject_bar_width}px; border-radius: ${c.subject_bar_width}px; }
      .ic { flex: none; line-height: 1.35; width: 1.25em; text-align: center; color: var(--itsl-secondary); }
      .ic ha-icon { --mdc-icon-size: 1.15em; }
      .body { min-width: 0; flex: 1; }
      .line { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; line-height: 1.35; }
      .subj { color: var(--itsl-secondary); font-size: 0.9em; }
      .ttl { font-weight: 500; overflow-wrap: anywhere; }
      .tm { margin-left: auto; font-size: 0.82em; color: var(--itsl-secondary); white-space: nowrap; font-variant-numeric: tabular-nums; }
      .desc {
        margin-top: 2px; font-size: 0.86em; color: var(--itsl-secondary); line-height: 1.4;
        display: -webkit-box; -webkit-line-clamp: ${c.description_lines}; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-line;
      }
      .empty { color: var(--itsl-secondary); font-size: 0.92em; padding: 0.3em 0; }
      details { margin-top: ${c.item_spacing}px; }
      summary { cursor: pointer; color: var(--itsl-secondary); font-size: 0.88em; padding: 0.3em 0; list-style-position: inside; }
      summary:focus-visible { outline: 2px solid var(--itsl-accent); border-radius: 4px; }
      details .list { margin-top: 6px; }
      /* next */
      .next { display: flex; align-items: center; gap: 12px; padding: ${Math.round(c.padding * 0.75)}px ${c.padding}px; }
      .next .day { padding: 0; font-size: 0.95em; white-space: nowrap; }
      .next .body .ttl { font-size: 1.02em; }
      /* chips */
      .chips { display: flex; flex-wrap: wrap; gap: 8px; padding: ${Math.round(c.padding * 0.6)}px; }
      .chip {
        display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
        background: color-mix(in srgb, var(--itsl-text) ${Math.max(6, c.item_background_opacity)}%, transparent);
        border: none; color: inherit; font: inherit; font-size: 0.9em;
      }
      .chip b { font-variant-numeric: tabular-nums; }
      .chip ha-icon { --mdc-icon-size: 1.1em; }
      .chip:focus-visible { outline: 2px solid var(--itsl-accent); outline-offset: 2px; }
      .warn { padding: 12px 16px; color: var(--itsl-secondary); }
      @keyframes itsl-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
      @keyframes itsl-breathe { 0%, 100% { opacity: 0.35; transform: scale(0.995); } 50% { opacity: 1; transform: scale(1.005); } }
      @keyframes itsl-rainbow { from { filter: hue-rotate(0deg); } to { filter: hue-rotate(360deg); } }
      @media (prefers-reduced-motion: reduce) { ha-card::before { animation: none !important; } }
    `;
  }

  /* ------------------------------------------------------------- rendering */
  _rowHtml(r) {
    const c = this._config;
    const tag = c.link_items && r.url ? "a" : "div";
    const href = tag === "a" ? ` href="${esc(r.url)}" target="_blank" rel="noopener"` : "";
    const bar = c.show_subject_color
      ? `<span class="sb" style="background:${esc(r.color || "var(--itsl-accent)")}"></span>`
      : "";
    const icon = c.show_icons
      ? `<span class="ic" aria-hidden="true">${c.icon_style === "emoji" ? r.emoji : `<ha-icon icon="${r.icon}"></ha-icon>`}</span>`
      : "";
    const desc = c.show_description && r.description ? `<div class="desc">${esc(r.description)}</div>` : "";
    const subj = r.subject && r.subject.toLowerCase() !== String(r.title).toLowerCase()
      ? `<span class="subj">${esc(r.subject)}</span>` : "";
    const tm = r.time ? `<span class="tm">${esc(r.time)}</span>` : "";
    const tint = c.item_style === "bar" && r.color
      ? ` style="background:color-mix(in srgb, ${esc(r.color)} ${Math.max(8, c.item_background_opacity + 6)}%, transparent)"` : "";
    return `<${tag} class="row s-${esc(c.item_style)}"${href}${tint}>${bar}${icon}<div class="body"><div class="line">${subj}<span class="ttl">${esc(r.title)}</span>${tm}</div>${desc}</div></${tag}>`;
  }

  _listHtml(rows, { group = this._config.group_by_day, empty = "" } = {}) {
    const c = this._config;
    rows = rows.slice(0, c.max_items);
    if (!rows.length) return `<div class="empty">${esc(c.empty_text || empty)}</div>`;
    if (!group) return `<div class="list">${rows.map((r) => this._rowHtml(r)).join("")}</div>`;
    const groups = [];
    for (const r of rows) {
      const key = r.date ? localDate(r.date).getTime() : "none";
      const last = groups[groups.length - 1];
      if (last && last.key === key) last.rows.push(r);
      else groups.push({ key, rows: [r], date: r.date, days: r.days, kind: r.kind });
    }
    return `<div class="list">${groups
      .map((g) => {
        if (g.key === "none") return `<div class="group nodate"><div class="items">${g.rows.map((r) => this._rowHtml(r)).join("")}</div></div>`;
        const col = this._urgencyColor(g.days, g.rows.every((r) => r.kind === "plan") ? "plan" : g.kind);
        return `<div class="group"><div class="day" style="color:${col}">${esc(dayLabel(g.date))}</div><div class="items">${g.rows
          .map((r) => this._rowHtml(r))
          .join("")}</div></div>`;
      })
      .join("")}</div>`;
  }

  _header(title, count) {
    const c = this._config;
    if (!c.show_header) return "";
    const t = c.title || title;
    if (!t) return "";
    const icon = c.icon ?? VIEW_ICONS[c.view];
    const n = c.show_count && count !== undefined && count !== null ? `<span class="n">${count}</span>` : "";
    return `<div class="head">${icon ? `<ha-icon icon="${esc(icon)}"></ha-icon>` : ""}<span class="t">${esc(t)}</span>${n}</div>`;
  }

  _dayBlock(key, label, empty) {
    const rows = this._rowsDay(key);
    return `<div class="block"><div class="bt">${label}</div>${this._listHtml(rows, { group: false, empty })}</div>`;
  }

  _homeworkHtml() {
    const c = this._config;
    const rows = this._rowsHomework();
    let html = this._listHtml(rows, { empty: `Inga läxförhör, prov eller deadlines de närmaste ${c.days_ahead} dagarna` });
    if (c.show_overdue) {
      const over = this._attr("overdue_tasks", "tasks").map((t) => this._taskRow(t, true));
      if (over.length)
        html += `<div class="block"><div class="bt" style="color:${color(c.overdue_color)}">Försenade</div>${this._listHtml(over, { group: false })}</div>`;
    }
    if (c.show_no_deadline) {
      const nd = this._attr("tasks_without_deadline", "tasks").map((t) => this._taskRow(t));
      if (nd.length)
        html += `<details><summary>Utan deadline (${nd.length})</summary>${this._listHtml(nd, { group: false })}</details>`;
    }
    return html;
  }

  _weekHtml(key, empty) {
    const rows = this._rowsWeek(key);
    // Week view groups by weekday name, not "Idag/I morgon"
    return this._listHtml(rows, { empty });
  }

  _newsHtml() {
    const c = this._config;
    const news = this._attr("news", "news").slice(0, c.max_items);
    if (!news.length) return `<div class="empty">${esc(c.empty_text || "Inga nyheter")}</div>`;
    const rows = news.map((n) => ({
      kind: "news", icon: "mdi:bullhorn-outline", emoji: "📣", date: n.published, sort: 0,
      subject: n.subject || n.course, title: n.text, time: n.published ? dayLabel(n.published) : "",
      description: n.author || "", url: n.url, color: n.color, days: null,
    }));
    return this._listHtml(rows, { group: false });
  }

  _nextHtml() {
    const c = this._config;
    const rows = this._rowsHomework().filter((r) => r.days !== null && r.days >= 0);
    const r = rows[0];
    if (!r) return `<div class="next"><span class="empty">${esc(c.empty_text || "Inga läxor eller prov på gång")}</span></div>`;
    const col = this._urgencyColor(r.days, r.kind);
    const tag = c.link_items && r.url ? "a" : "div";
    const href = tag === "a" ? ` href="${esc(r.url)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none"` : "";
    const more = rows.length > 1 ? `<span class="tm">+${rows.length - 1}</span>` : "";
    return `<${tag} class="next"${href}>
      <span class="day" style="color:${col}">${esc(dayLabel(r.date))}${r.time ? `<br><span class="tm" style="margin:0">${esc(r.time)}</span>` : ""}</span>
      ${c.show_subject_color ? `<span style="align-self:stretch;width:${c.subject_bar_width}px;border-radius:3px;background:${esc(r.color || "var(--itsl-accent)")}"></span>` : ""}
      <div class="body"><div class="line">${r.subject ? `<span class="subj">${esc(r.subject)}</span>` : ""}${more}</div><div class="ttl">${esc(r.title)}</div>
      ${c.show_description && r.description ? `<div class="desc" style="-webkit-line-clamp:1">${esc(r.description)}</div>` : ""}</div></${tag}>`;
  }

  _chipsHtml() {
    const c = this._config;
    const s = c.entity_suffix || "";
    const defs = [
      ["tomorrow", "mdi:calendar-arrow-right", "I morgon", c.tomorrow_color],
      ["upcoming_events", "mdi:clipboard-text-clock-outline", "Prov och läxförhör", c.soon_color],
      ["overdue_tasks", "mdi:alert-circle-outline", "Försenade", c.overdue_color],
      ["news", "mdi:newspaper-variant-outline", "Nyheter", null],
      ["unread_notifications", "mdi:bell-outline", "Olästa", null],
    ];
    const chips = (c.chips || defs.map((d) => d[0]))
      .map((k) => defs.find((d) => d[0] === k))
      .filter(Boolean)
      .map(([k, icon, label, col]) => {
        const st = this._hass?.states[`sensor.itslearning_${k}${s}`];
        const n = st ? st.state : "–";
        const hot = Number(n) > 0 && col;
        return `<button class="chip" data-entity="sensor.itslearning_${k}${s}" style="${hot ? `color:${color(col)}` : ""}">
          <ha-icon icon="${icon}"></ha-icon><span>${label}</span><b>${esc(n)}</b></button>`;
      });
    return `<div class="chips">${chips.join("")}</div>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card><div class="warn">Laddar …</div></ha-card>`;
      return;
    }
    if (!this._state("today") && !this._state("upcoming_tasks")) {
      this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card><div class="warn">Hittar inga itslearning-sensorer${c.entity_suffix ? ` med ändelsen ${esc(c.entity_suffix)}` : ""}. Är integrationen installerad?</div></ha-card>`;
      return;
    }
    let body = "";
    const title = VIEW_TITLES[c.view] ?? "";
    switch (c.view) {
      case "today": {
        const rows = this._rowsDay("today");
        body = this._header(title, rows.length) + this._listHtml(rows, { group: false, empty: "Inget inlagt idag" });
        break;
      }
      case "tomorrow": {
        const rows = this._rowsDay("tomorrow");
        body = this._header(title, rows.length) + this._listHtml(rows, { group: false, empty: "Inget inlagt i morgon" });
        break;
      }
      case "homework":
        body = this._header(title, this._rowsHomework().length) + this._homeworkHtml();
        break;
      case "week":
        body = this._header(`${title} (v. ${this._state("plans_this_week")?.attributes?.week ?? ""})`, this._rowsWeek("plans_this_week").length)
          + this._weekHtml("plans_this_week", "Ingen planering inlagd för veckan");
        break;
      case "next_week":
        body = this._header(`${title} (v. ${this._state("plans_next_week")?.attributes?.week ?? ""})`, this._rowsWeek("plans_next_week").length)
          + this._weekHtml("plans_next_week", "Ingen planering inlagd för nästa vecka");
        break;
      case "news":
        body = this._header(title, this._state("news")?.state) + this._newsHtml();
        break;
      case "next":
        body = this._nextHtml();
        break;
      case "chips":
        body = this._chipsHtml();
        break;
      case "overview":
        body = this._header(title)
          + this._dayBlock("today", "Idag", "Inget inlagt idag")
          + this._dayBlock("tomorrow", "I morgon", "Inget inlagt i morgon")
          + `<div class="block"><div class="bt">Läxor och prov</div>${this._homeworkHtml()}</div>`
          + `<div class="block"><div class="bt">Planering den här veckan</div>${this._weekHtml("plans_this_week", "Ingen planering inlagd")}</div>`
          + `<div class="block"><div class="bt">Från lärarna</div>${this._newsHtml()}</div>`;
        break;
      case "day":
      default:
        body = this._header(title)
          + this._dayBlock("today", "Idag", "Inget inlagt idag")
          + this._dayBlock("tomorrow", "I morgon", "Inget inlagt i morgon");
    }
    const wrapped = c.view === "next" || c.view === "chips" ? body : `<div class="wrap">${body}</div>`;
    this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card>${wrapped}</ha-card>`;
    this.shadowRoot.querySelectorAll(".chip").forEach((el) =>
      el.addEventListener("click", () => {
        const ev = new Event("hass-more-info", { bubbles: true, composed: true });
        ev.detail = { entityId: el.dataset.entity };
        this.dispatchEvent(ev);
      })
    );
  }
}

/* =================================================================== editor */
const opt = (pairs) => pairs.map(([value, label]) => ({ value, label }));

const EDITOR_SCHEMA = [
  {
    name: "view", selector: { select: { mode: "dropdown", options: opt([
      ["day", "Idag och i morgon"], ["today", "Idag"], ["tomorrow", "I morgon"], ["homework", "Läxor och prov"],
      ["week", "Planering den här veckan"], ["next_week", "Planering nästa vecka"], ["news", "Nyheter från lärarna"],
      ["next", "Nästa sak (en rad)"], ["chips", "Snabbsiffror (chips)"], ["overview", "Allt i ett kort"],
    ]) } },
  },
  {
    name: "preset", selector: { select: { mode: "dropdown", options: opt([
      ["default", "Följ temat"], ["glass", "Glas"], ["neon", "Neon"], ["minimal", "Minimal"], ["solid", "Solid blå"],
      ["notebook", "Skrivhäfte"], ["sunset", "Solnedgång"], ["ocean", "Hav"], ["midnight", "Midnatt"],
    ]) } },
  },
  {
    type: "expandable", title: "Innehåll", icon: "mdi:format-list-bulleted", schema: [
      { name: "title", selector: { text: {} } },
      { name: "icon", selector: { icon: {} } },
      { type: "grid", schema: [
        { name: "show_header", selector: { boolean: {} } },
        { name: "show_count", selector: { boolean: {} } },
        { name: "show_events", selector: { boolean: {} } },
        { name: "show_tasks", selector: { boolean: {} } },
        { name: "show_plans", selector: { boolean: {} } },
        { name: "show_overdue", selector: { boolean: {} } },
        { name: "show_no_deadline", selector: { boolean: {} } },
        { name: "show_description", selector: { boolean: {} } },
        { name: "show_subject_color", selector: { boolean: {} } },
        { name: "show_icons", selector: { boolean: {} } },
        { name: "group_by_day", selector: { boolean: {} } },
        { name: "link_items", selector: { boolean: {} } },
      ] },
      { name: "icon_style", selector: { select: { mode: "dropdown", options: opt([["mdi", "Ikoner"], ["emoji", "Emoji"]]) } } },
      { type: "grid", schema: [
        { name: "max_items", selector: { number: { min: 1, max: 30, mode: "box" } } },
        { name: "days_ahead", selector: { number: { min: 1, max: 28, mode: "box" } } },
        { name: "description_lines", selector: { number: { min: 1, max: 8, mode: "box" } } },
      ] },
      { name: "empty_text", selector: { text: {} } },
      { name: "entity_suffix", selector: { text: {} } },
    ],
  },
  {
    type: "expandable", title: "Bakgrund och text", icon: "mdi:palette-outline", schema: [
      { name: "background_color", selector: { color_rgb: {} } },
      { name: "background_opacity", selector: { number: { min: 0, max: 100, step: 1, mode: "slider", unit_of_measurement: "%" } } },
      { name: "blur", selector: { number: { min: 0, max: 40, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "gradient", selector: { boolean: {} } },
      { name: "gradient_color", selector: { color_rgb: {} } },
      { name: "gradient_angle", selector: { number: { min: 0, max: 360, step: 5, mode: "slider", unit_of_measurement: "°" } } },
      { name: "ruled", selector: { boolean: {} } },
      { name: "text_color", selector: { color_rgb: {} } },
      { name: "secondary_text_color", selector: { color_rgb: {} } },
      { name: "accent_color", selector: { color_rgb: {} } },
      { name: "font_scale", selector: { number: { min: 70, max: 150, step: 5, mode: "slider", unit_of_measurement: "%" } } },
    ],
  },
  {
    type: "expandable", title: "Kant och skugga", icon: "mdi:border-outside", schema: [
      { name: "border_width", selector: { number: { min: 0, max: 8, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "border_style", selector: { select: { mode: "dropdown", options: opt([["solid", "Heldragen"], ["dashed", "Streckad"], ["dotted", "Prickad"], ["double", "Dubbel"]]) } } },
      { name: "border_color", selector: { color_rgb: {} } },
      { name: "border_opacity", selector: { number: { min: 0, max: 100, step: 1, mode: "slider", unit_of_measurement: "%" } } },
      { name: "border_radius", selector: { number: { min: 0, max: 40, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "shadow", selector: { number: { min: 0, max: 80, step: 1, mode: "slider" } } },
    ],
  },
  {
    type: "expandable", title: "Glöd", icon: "mdi:creation-outline", schema: [
      { name: "glow", selector: { boolean: {} } },
      { name: "glow_color", selector: { color_rgb: {} } },
      { name: "glow_size", selector: { number: { min: 0, max: 80, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "glow_intensity", selector: { number: { min: 0, max: 100, step: 1, mode: "slider", unit_of_measurement: "%" } } },
      { name: "glow_animation", selector: { select: { mode: "dropdown", options: opt([["none", "Ingen"], ["pulse", "Puls"], ["breathe", "Andning"], ["rainbow", "Regnbåge"]]) } } },
    ],
  },
  {
    type: "expandable", title: "Rader", icon: "mdi:view-list-outline", schema: [
      { name: "item_style", selector: { select: { mode: "dropdown", options: opt([["plain", "Ren"], ["tinted", "Tonad bakgrund"], ["outlined", "Kantlinje"], ["bar", "Tonad med ämnesfärg"]]) } } },
      { name: "item_background_opacity", selector: { number: { min: 0, max: 40, step: 1, mode: "slider", unit_of_measurement: "%" } } },
      { name: "item_radius", selector: { number: { min: 0, max: 24, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "subject_bar_width", selector: { number: { min: 0, max: 10, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "item_spacing", selector: { number: { min: 0, max: 24, step: 1, mode: "slider", unit_of_measurement: "px" } } },
      { name: "padding", selector: { number: { min: 0, max: 40, step: 1, mode: "slider", unit_of_measurement: "px" } } },
    ],
  },
  {
    type: "expandable", title: "Färger för hur bråttom det är", icon: "mdi:clock-alert-outline", schema: [
      { name: "today_color", selector: { color_rgb: {} } },
      { name: "tomorrow_color", selector: { color_rgb: {} } },
      { name: "soon_color", selector: { color_rgb: {} } },
      { name: "later_color", selector: { color_rgb: {} } },
      { name: "overdue_color", selector: { color_rgb: {} } },
    ],
  },
];

const LABELS = {
  view: "Vad kortet visar", preset: "Stil", title: "Rubrik (tomt = standard)", icon: "Ikon",
  show_header: "Visa rubrik", show_count: "Visa antal", show_events: "Läxförhör och prov", show_tasks: "Uppgifter med deadline",
  show_plans: "Planering", show_overdue: "Försenade", show_no_deadline: "Utan deadline", show_description: "Beskrivningar",
  show_subject_color: "Ämnesfärg", show_icons: "Ikoner", group_by_day: "Gruppera per dag", link_items: "Länka till itslearning",
  icon_style: "Ikontyp", max_items: "Max antal rader", days_ahead: "Dagar framåt", description_lines: "Rader beskrivning",
  empty_text: "Text när det är tomt", entity_suffix: "Ändelse för andra barnet (t.ex. _2)",
  background_color: "Bakgrundsfärg", background_opacity: "Bakgrundens täckning", blur: "Oskärpa bakom (glas)",
  gradient: "Gradient", gradient_color: "Gradientens andra färg", gradient_angle: "Gradientens vinkel", ruled: "Linjerat papper",
  text_color: "Textfärg", secondary_text_color: "Sekundär textfärg", accent_color: "Accentfärg", font_scale: "Textstorlek",
  border_width: "Kantlinjens bredd", border_style: "Kantlinjens stil", border_color: "Kantlinjens färg",
  border_opacity: "Kantlinjens täckning", border_radius: "Rundade hörn", shadow: "Skugga",
  glow: "Glöd", glow_color: "Glödens färg", glow_size: "Glödens storlek", glow_intensity: "Glödens styrka", glow_animation: "Animation",
  item_style: "Radstil", item_background_opacity: "Radbakgrundens täckning", item_radius: "Radernas hörn",
  subject_bar_width: "Ämneslinjens bredd", item_spacing: "Avstånd mellan rader", padding: "Inre marginal",
  today_color: "Idag", tomorrow_color: "I morgon", soon_color: "Inom 3 dagar", later_color: "Senare", overdue_color: "Försenat",
};

class ItslearningCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  async connectedCallback() {
    if (!customElements.get("ha-form")) {
      // Make sure HA has loaded ha-form (it is lazy-loaded).
      try {
        const helpers = await window.loadCardHelpers?.();
        const card = await helpers?.createCardElement({ type: "entities", entities: [] });
        await card?.constructor?.getConfigElement?.();
      } catch (e) { /* ignore */ }
    }
    this._render();
  }

  _render() {
    if (!this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => LABELS[s.name] ?? s.name;
      this._form.addEventListener("value-changed", (ev) => {
        const value = ev.detail.value || {};
        // Save only what differs from defaults + the chosen preset, so presets keep working.
        const base = { ...DEFAULTS, ...(PRESETS[value.preset] || {}) };
        const out = { type: this._config.type || "custom:itslearning-card" };
        const presetChanged = value.preset !== this._config.preset;
        for (const [k, v] of Object.entries(value)) {
          if (k === "type" || v === undefined || v === "" || v === null) continue;
          if (presetChanged && STYLE_KEYS.has(k)) continue; // new preset: start from its look
          if (!(k in DEFAULTS) && k !== "preset" && k !== "icon" && k !== "chips") { out[k] = v; continue; }
          if (JSON.stringify(v) !== JSON.stringify(base[k])) out[k] = v;
        }
        if (value.preset && value.preset !== "default") out.preset = value.preset;
        out.view = value.view || "day";
        this._config = out;
        this._render();
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: out }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    const preset = PRESETS[this._config.preset] || {};
    // Show effective values (defaults + preset) so sliders start where the card is.
    this._form.data = { ...DEFAULTS, ...preset, ...this._config };
  }
}

const STYLE_KEYS = new Set([
  "font_scale", "padding", "item_spacing", "item_radius", "subject_bar_width",
  "background_color", "background_opacity", "blur", "gradient", "gradient_color", "gradient_angle", "ruled",
  "text_color", "secondary_text_color", "accent_color", "border_width", "border_style", "border_color", "border_opacity",
  "border_radius", "shadow", "glow", "glow_color", "glow_size", "glow_intensity", "glow_animation", "item_style",
  "item_background_opacity", "today_color", "tomorrow_color", "soon_color", "later_color", "overdue_color",
]);

if (!customElements.get("itslearning-card")) customElements.define("itslearning-card", ItslearningCard);
if (!customElements.get("itslearning-card-editor")) customElements.define("itslearning-card-editor", ItslearningCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "itslearning-card")) {
  window.customCards.push({
    type: "itslearning-card",
    name: "itslearning",
    description: "Läxor, prov, planering och nyheter från itslearning, med många stilval.",
    preview: true,
    documentationURL: "https://github.com/kakelakel/ITSlearning-Nassj-",
  });
}
console.info(`%c itslearning-card %c ${CARD_VERSION} `, "background:#3465a4;color:#fff;border-radius:3px 0 0 3px;padding:1px 4px", "background:#ddd;color:#333;border-radius:0 3px 3px 0;padding:1px 4px");
