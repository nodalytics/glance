// glance dashboard: a dependency-free single-page app served by glance-server.
// Every request goes through api(), which records it for the Inspector.

const $ = (sel, root = document) => root.querySelector(sel);

// h("div.cls", {attr}, ...children): tiny DOM builder; strings become text
// nodes, so server data is never parsed as HTML.
function h(tag, attrs, ...kids) {
  const [name, ...classes] = tag.split(".");
  const el = document.createElement(name || "div");
  if (classes.length) el.className = classes.join(" ");
  if (attrs && (typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs))) {
    kids.unshift(attrs);
    attrs = null;
  }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "class") el.className += (el.className ? " " : "") + v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  const add = (k) => {
    if (k === null || k === undefined || k === false) return;
    if (Array.isArray(k)) k.forEach(add);
    else el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  };
  kids.forEach(add);
  return el;
}

// append() renders false/null as text; drop them like h() does.
const put = (el, ...kids) => el.append(...kids.flat().filter((k) => k !== null && k !== undefined && k !== false));

const swap = (el, ...kids) => { el.replaceChildren(); put(el, ...kids); };

const fmtNum = (v) =>
  v === undefined || v === null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
const pct = (v) => (v === undefined || v === null ? "—" : `${(v * 100).toFixed(1)}%`);
const clock = (t) => new Date(t).toLocaleTimeString(undefined, { hour12: false });

function toast(msg, bad = false) {
  const t = h("div.toast" + (bad ? ".bad" : ""), msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), bad ? 6000 : 3200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = h("textarea", { style: { position: "fixed", opacity: "0" } });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast("Copied to clipboard");
}

// ------------------------------------------------------------------ API + log

const log = [];
let logSeq = 0;
const LOG_MAX = 150;
const logListeners = new Set();

async function api(method, path, { body, type, poll = false } = {}) {
  const entry = { id: ++logSeq, method, path, at: Date.now(), poll, status: 0, ms: 0 };
  if (body instanceof Blob) entry.request = `[${body.type || "binary"}, ${body.size.toLocaleString()} bytes]`;
  else if (body !== undefined) entry.request = body;
  entry.requestType = type;
  const t0 = performance.now();
  let res;
  try {
    res = await fetch(path, {
      method,
      body,
      headers: type ? { "Content-Type": type } : undefined,
      cache: "no-store",
    });
  } catch (e) {
    entry.ms = performance.now() - t0;
    entry.error = String(e.message || e);
    pushLog(entry);
    return { ok: false, status: 0, json: null, text: "", error: entry.error };
  }
  entry.ms = performance.now() - t0;
  entry.status = res.status;
  const ctype = res.headers.get("Content-Type") || "";
  entry.contentType = ctype;
  let json = null;
  let text = "";
  if (ctype.includes("json")) {
    text = await res.text();
    try { json = JSON.parse(text); } catch (_) { /* keep text */ }
    entry.response = json ?? text;
  } else if (ctype.startsWith("text/")) {
    text = await res.text();
    entry.response = text.length > 4000 ? text.slice(0, 4000) + "\n…" : text;
  } else {
    const blob = await res.blob();
    entry.response = `[${ctype || "binary"}, ${blob.size.toLocaleString()} bytes]`;
  }
  pushLog(entry);
  return { ok: res.ok, status: res.status, json, text };
}

function pushLog(entry) {
  log.unshift(entry);
  if (log.length > LOG_MAX) log.length = LOG_MAX;
  const visible = log.filter((e) => !e.poll).length;
  $("#inspector-count").textContent = visible ? String(visible) : "";
  logListeners.forEach((fn) => fn());
}

// JSON -> highlighted <pre>. The text is escaped before the regex wraps
// tokens in spans, so payload content can never become markup.
function jsonView(value) {
  const pre = h("pre.json");
  const src = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const esc = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  pre.innerHTML = esc.replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m, str, colon, lit, num) => {
      if (str) return colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`;
      if (lit) return `<span class="b">${lit}</span>`;
      return `<span class="n">${num}</span>`;
    },
  );
  return pre;
}

function rawBlock(label, value) {
  return h("details.raw", h("summary", label), jsonView(value),
    h("div", { style: { marginTop: "8px" } },
      h("button.btn.small", { type: "button", onclick: () => copyText(JSON.stringify(value, null, 2)) }, "Copy JSON")));
}

// ------------------------------------------------------------------ server info

let info = null;
async function loadInfo() {
  const r = await api("GET", "/info");
  if (r.ok && r.json) info = r.json;
  const b = $("#build");
  swap(b, );
  if (info) {
    b.append(
      h("div", `Version ${info.version}`),
      h("div", `Mapping ${info.mapping?.name || "unnamed"}`),
      h("div", `Control: ${info.control_backend}, OCR ${info.ocr_available ? "on" : "off"}`),
    );
  }
  return info;
}

async function heartbeat() {
  const r = await api("GET", "/health", { poll: true });
  const c = $("#conn");
  c.classList.toggle("up", r.ok);
  c.classList.toggle("down", !r.ok);
  $("#conn-text").textContent = r.ok ? "Server online" : "Server unreachable";
}

// ------------------------------------------------------------------ cards

const SUITS = { h: ["♥", "red", "hearts"], d: ["♦", "red", "diamonds"], c: ["♣", "black", "clubs"], s: ["♠", "black", "spades"] };
const SUIT_INITIAL = { hearts: "h", diamonds: "d", clubs: "c", spades: "s" };

function cardFace(id, extra = "") {
  if (!id || id === "empty") return h("div.pc.slot" + extra, { "aria-hidden": "true" });
  const low = String(id).toLowerCase();
  if (low.startsWith("cover") || low === "back") return h("div.pc.back" + extra, { title: "Covered card", role: "img", "aria-label": "covered card" });
  const suit = SUITS[low.slice(-1)];
  let rank = String(id).slice(0, -1).toUpperCase();
  if (rank === "T") rank = "10";
  if (!suit || !rank) return h("div.pc.unknown" + extra, { title: id }, h("span.r", id));
  return h("div.pc" + extra + (suit[1] === "red" ? ".red" : ""), { role: "img", "aria-label": `${rank} of ${suit[2]}`, title: id },
    h("span.r", rank), h("span.s", suit[0]));
}

// ------------------------------------------------------------------ pages

const pages = {};
let cleanup = null;

function head(title, blurb, tools) {
  return h("header.page-head", h("div", h("h1", title), blurb && h("p", blurb)), tools && h("div.head-tools", tools));
}

function emptyState(title, body) {
  return h("div.empty", h("strong", title), body);
}

function validationBlock(v) {
  if (!v) return null;
  const errs = v.errors || [];
  const warns = v.warnings || [];
  const status = v.valid
    ? (warns.length ? h("span.pill.warn", `${warns.length} warning${warns.length > 1 ? "s" : ""}`) : h("span.pill.ok", "Consistent"))
    : h("span.pill.bad", `${errs.length} error${errs.length > 1 ? "s" : ""}`);
  const item = (cls) => (i) =>
    h("li" + cls, h("div", i.message), h("div.slots", h("code", i.code), i.slots?.length ? `  in ${i.slots.join(", ")}` : ""));
  return h("section",
    h("div.row", { style: { justifyContent: "space-between", alignItems: "center", marginBottom: "10px" } }, h("h3", { style: { margin: 0 } }, "Validation"), status),
    errs.length || warns.length
      ? h("ul.issues", errs.map(item(".error")), warns.map(item("")))
      : h("p.poll-meta", { style: { margin: 0 } }, "No impossible readings in this frame."));
}

// ---- Live table

pages.table = (main) => {
  let timer = null;
  let interval = 2000;
  let auto = true;
  let first = true;
  const meta = h("span.poll-meta", "Waiting for the first read");
  const body = h("div");
  const autoBox = h("input", { type: "checkbox", checked: true, onchange: (e) => { auto = e.target.checked; schedule(); } });
  const sel = h("select.inline", { "aria-label": "Refresh interval", onchange: (e) => { interval = +e.target.value; schedule(); } },
    [1000, 2000, 5000, 10000].map((ms) => h("option", { value: ms, selected: ms === interval }, `every ${ms / 1000}s`)));

  put(main, 
    head("Live table", "What glance reads from the last captured frame, refreshed from GET /state.",
      [meta, h("label.toggle", autoBox, "Auto refresh"), sel, h("button.btn", { type: "button", onclick: () => tick(false) }, "Refresh now")]),
    body,
  );

  async function tick(poll = true) {
    const r = await api("GET", "/state", { poll });
    if (r.status === 404) {
      swap(body, h("div.panel.flat", emptyState("No table read yet",
        h("span", "Send a screenshot from ", h("a", { href: "#/capture" }, "Capture"), " and its parsed state appears here."))));
      meta.textContent = `Checked ${clock(Date.now())}`;
    } else if (!r.ok || !r.json) {
      meta.textContent = r.status ? `GET /state returned ${r.status}` : "Server unreachable";
    } else {
      renderTable(body, r.json, first);
      first = false;
      meta.textContent = `Updated ${clock(Date.now())}`;
    }
    schedule();
  }
  function schedule() {
    clearTimeout(timer);
    if (auto && !document.hidden) timer = setTimeout(tick, interval);
  }
  const onVis = () => schedule();
  document.addEventListener("visibilitychange", onVis);
  tick(false);
  return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", onVis); };
};

function renderTable(root, s, animate) {
  const seats = s.seats || [];
  const n = Math.max(s.max_players || 0, seats.length, 2);
  const felt = h("div.felt", { role: "img", "aria-label": "Table view" });
  const pos = (i, rx, ry, shift = 0) => {
    const a = Math.PI / 2 + (i * 2 * Math.PI) / n + shift;
    return { left: `${50 + rx * Math.cos(a)}%`, top: `${50 + ry * Math.sin(a)}%` };
  };

  const board = s.board || [];
  felt.append(h("div.felt-center",
    h("div.pot", s.pot !== undefined ? fmtNum(s.pot) : "—", h("small", "Pot")),
    h("div.board", [0, 1, 2, 3, 4].map((i) => cardFace(board[i]))),
    h("div.stage-name", s.stage || "No stage")));

  for (let i = 0; i < n; i++) {
    const seat = seats.find((x) => x.index === i + 1) || { index: i + 1 };
    const me = i === 0;
    const out = !me && !seat.in_hand && !(seat.cards && seat.cards.length);
    const el = h("div.seat" + (me ? ".me" : "") + (out ? ".out" : "") + (me && s.my_turn ? ".turn" : ""), { style: pos(i, 52, 56) },
      h("div.hole", (seat.cards || []).map((c) => cardFace(c))),
      h("div.seat-plate",
        h("div.who", me ? "Seat 1, you" : `Seat ${i + 1}`),
        h("div.stack", seat.stack !== undefined ? fmtNum(seat.stack) : "—")));
    felt.append(el);
    if (seat.bet !== undefined) felt.append(h("div.bet", { style: pos(i, 30, 30) }, fmtNum(seat.bet)));
    if (s.dealer === i + 1) felt.append(h("div.dealer", { style: pos(i, 40, 40, 0.32), title: `Dealer: seat ${i + 1}` }, "D"));
  }

  const turn = h("div.turn-flag" + (s.my_turn ? ".on" : ""),
    h("b", s.my_turn ? "Your turn" : "Waiting"),
    h("span.poll-meta", s.my_turn ? "An action button is visible." : "No action button visible."));
  const facts = h("dl.facts",
    h("dt", "Stage"), h("dd", s.stage || "—"),
    h("dt", "Pot"), h("dd.big", fmtNum(s.pot)),
    h("dt", "To call"), h("dd", fmtNum(s.call)),
    h("dt", "Raise"), h("dd", fmtNum(s.raise)),
    h("dt", "Dealer"), h("dd", s.dealer ? `Seat ${s.dealer}` : "—"),
    h("dt", "Your cards"), h("dd", (s.my_cards || []).join(" ") || "—"),
    h("dt", "Board"), h("dd", board.join(" ") || "—"),
    h("dt", "Seats read"), h("dd", `${seats.filter((x) => x.stack !== undefined).length} of ${n}`));

  swap(root, h("div.table-layout" + (animate ? ".page-enter" : ""),
    h("div.felt-wrap", felt),
    h("aside.panel.readout.stack", h("div", turn, facts), validationBlock(s.validation), rawBlock("Raw state", s))));
}

// ---- drop zone helper

function dropZone({ title, hint, accept = "image/*", onFile }) {
  const input = h("input", { type: "file", accept, onchange: (e) => e.target.files[0] && onFile(e.target.files[0]) });
  const zone = h("label.drop", { tabindex: "0" }, input, h("strong", title), h("span", hint));
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  });
  const onPaste = (e) => {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (item) onFile(item.getAsFile());
  };
  document.addEventListener("paste", onPaste);
  return { zone, dispose: () => document.removeEventListener("paste", onPaste) };
}

function stateSummary(s) {
  return h("dl.facts",
    h("dt", "Stage"), h("dd", s.stage || "—"),
    h("dt", "Your cards"), h("dd", (s.my_cards || []).join(" ") || "—"),
    h("dt", "Board"), h("dd", (s.board || []).join(" ") || "—"),
    h("dt", "Pot"), h("dd", fmtNum(s.pot)),
    h("dt", "Your turn"), h("dd", s.my_turn ? "Yes" : "No"));
}

// ---- Capture

pages.capture = (main) => {
  const result = h("div.panel", emptyState("Nothing sent yet", "The parse result appears here."));
  const frameBox = h("div");
  let zoom = false;

  function showFrame() {
    const img = h("img", { alt: "Last frame received by the server", src: `/frame.png?t=${Date.now()}` });
    const view = h("div.frame-view" + (zoom ? ".zoom" : ""), img);
    img.addEventListener("error", () => view.replaceWith(h("div.panel.flat", emptyState("No frame on the server", "POST a screenshot and it shows here."))));
    img.addEventListener("load", () => { dims.textContent = `${img.naturalWidth} × ${img.naturalHeight}px`; });
    const dims = h("span.poll-meta");
    swap(frameBox, 
      h("div.row", { style: { justifyContent: "space-between", alignItems: "center", marginBottom: "10px" } },
        h("h2", { style: { margin: 0 } }, "Last frame"),
        h("div.head-tools", dims,
          h("label.toggle", h("input", { type: "checkbox", checked: zoom, onchange: (e) => { zoom = e.target.checked; view.classList.toggle("zoom", zoom); } }), "Actual size"),
          h("a.btn.small", { href: "/frame.png", download: "glance-frame.png" }, "Download PNG"))),
      view);
  }

  async function send(file) {
    swap(result, h("p.poll-meta", `Sending ${file.name || "pasted image"} (${(file.size / 1024).toFixed(0)} KB)…`));
    const r = await api("POST", "/capture", { body: file, type: file.type || "application/octet-stream" });
    if (r.ok && r.json) {
      swap(result, 
        h("div.row", { style: { justifyContent: "space-between", alignItems: "center", marginBottom: "12px" } },
          h("h2", { style: { margin: 0 } }, "Table found"), h("a.btn.small", { href: "#/table" }, "Open live table")),
        stateSummary(r.json), h("div", { style: { marginTop: "14px" } }, validationBlock(r.json.validation)), rawBlock("Raw state", r.json));
      toast("Screenshot parsed");
    } else if (r.status === 422) {
      swap(result, h("h2", "Table not found"),
        h("p", { style: { margin: 0, color: "var(--muted)" } },
          "The server could not decode the image or did not find the table's anchor in it. The frame is shown below when it decoded, so you can check what was sent against the mapping's anchor template."));
    } else {
      swap(result, h("h2", "Capture failed"), h("p", r.json?.error || r.error || `HTTP ${r.status}`));
    }
    showFrame();
  }

  const dz = dropZone({ title: "Drop a screenshot here", hint: "or click to choose a PNG/JPEG, or paste an image. It is sent as-is to POST /capture.", onFile: send });
  put(main, head("Capture", "Send a full-desktop screenshot for glance to parse. The parsed state feeds the live table."),
    h("div.grid-2", dz.zone, result), h("div", { style: { marginTop: "26px" } }, frameBox));
  showFrame();
  return dz.dispose;
};

// ---- Card lab

const VERIFY = {
  not_required: ["quiet", "Not needed", "The glyph read was confident enough on its own."],
  unverified: ["quiet", "Unverified", "No OCR on this server to cross-check a low-confidence read."],
  confirmed: ["ok", "Confirmed", "OCR agreed with the glyph read."],
  changed: ["warn", "Changed by OCR", "OCR disagreed with high confidence and replaced the glyph read."],
  rejected: ["bad", "Rejected", "OCR disagreed; the rank was discarded."],
  ocr_recovered: ["ok", "Recovered by OCR", "The glyph matcher failed; OCR read the rank."],
  unrecognized: ["bad", "Unrecognized", "Neither the glyph matcher nor OCR produced a rank."],
  empty: ["quiet", "Empty slot", "The crop looks like bare table, so recognition was skipped."],
};

function meter(label, value, best = false) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  return h("div.meter" + (best ? ".best" : ""), h("span.lbl", label),
    h("span.bar", h("i", { style: { width: `${v * 100}%` } })), h("span.v", v.toFixed(3)));
}

pages.cards = (main) => {
  const slot = h("select", { id: "slot" },
    h("option", { value: "" }, "Any slot"),
    ["my1", "my2", "board1", "board2", "board3", "board4", "board5"].map((s) => h("option", { value: s }, s)));
  const result = h("div.panel", emptyState("No card read yet", "Drop one card crop to see how glance reads it."));
  let lastFile = null;
  let lastUrl = null;

  async function send(file) {
    lastFile = file;
    if (lastUrl) URL.revokeObjectURL(lastUrl);
    lastUrl = URL.createObjectURL(file);
    swap(result, h("p.poll-meta", "Reading card…"));
    const q = slot.value ? `?slot=${encodeURIComponent(slot.value)}` : "";
    const r = await api("POST", `/recognize-card${q}`, { body: file, type: file.type || "application/octet-stream" });
    if (r.status === 409) {
      swap(result, h("h2", "Card vision is off"), h("p", { style: { color: "var(--muted)" } },
        "This server's mapping has no card_vision section, so there is no recognizer to run. Add one (profile plus suit and rank template folders) and restart the server."));
      return;
    }
    if (!r.ok || !r.json) {
      swap(result, h("h2", "Could not read this file"), h("p", r.json?.error || r.error || `HTTP ${r.status}`));
      return;
    }
    renderReading(result, r.json, lastUrl);
  }

  const dz = dropZone({ title: "Drop one card crop", hint: "PNG or JPEG of a single card slot. Paste works too.", onFile: send });
  const cvInfo = info?.card_vision;
  const banner = cvInfo && !cvInfo.configured
    ? h("div.notice", h("p", h("b", "Card vision is not configured. "), "The mapping loaded by this server has no card_vision section, so every read will be refused until one is added."))
    : cvInfo
      ? h("p.poll-meta", { style: { marginTop: "-12px", marginBottom: "18px" } },
        `Profile ${cvInfo.profile}, ${cvInfo.suit_templates} suit and ${cvInfo.rank_templates} rank templates loaded.`)
      : null;

  put(main, head("Card lab", "Test the template-free card recognizer on a single crop: rank glyph, suit symbol, occupancy and OCR verification."),
    banner,
    h("div.grid-2",
      h("div.stack", dz.zone, h("div.row",
        h("label.field", "Slot (selects slot-specific suit regions)", slot),
        h("button.btn", { type: "button", onclick: () => lastFile ? send(lastFile) : toast("Choose a card crop first", true) }, "Read again"))),
      result));
  return () => { dz.dispose(); if (lastUrl) URL.revokeObjectURL(lastUrl); };
};

function renderReading(root, r, url) {
  const ver = VERIFY[r.rank_verification] || ["quiet", r.rank_verification, ""];
  const occ = r.occupancy || {};
  const suitId = SUIT_INITIAL[r.suit];
  const face = r.recognized ? cardFace(r.card, ".huge")
    : r.rank || r.suit ? cardFace(`${r.rank || "?"}${suitId || "?"}`, ".huge") : cardFace(r.skipped ? "empty" : "?", ".huge");
  const scores = Object.entries(r.suit_scores || {}).sort((a, b) => b[1] - a[1]);
  const verdict = r.recognized ? `Read as ${r.card}` : r.skipped ? "Empty slot" : "Not recognized";

  swap(root, 
    h("div.lab-result",
      h("div.lab-card", face, url && h("img", { src: url, alt: "Uploaded crop" }), h("span.poll-meta", `${r.width}×${r.height}px${r.slot ? `, ${r.slot}` : ""}`)),
      h("div.stack",
        h("div", h("p.verdict", verdict),
          h("div.row", { style: { gap: "6px" } }, h("span.pill." + ver[0], `Rank: ${ver[1]}`), h("span.pill." + (occ.state === "occupied" ? "ok" : occ.state === "empty" ? "quiet" : "warn"), `Slot ${occ.state || "unknown"}`)),
          ver[2] && h("p.poll-meta", { style: { margin: "8px 0 0" } }, ver[2])),
        h("section",
          h("h3", "Rank"),
          h("dl.facts", h("dt", "Rank"), h("dd", r.rank ?? "—"),
            r.glyph_rank !== undefined && [h("dt", "Glyph read"), h("dd", r.glyph_rank ?? "none")],
            h("dt", "Margin"), h("dd", Number(r.rank_margin || 0).toFixed(3)),
            h("dt", "Source"), h("dd", r.rank_source || "—")),
          h("div", { style: { marginTop: "10px" } }, meter("Confidence", r.rank_confidence, true))),
        h("section",
          h("h3", "Suit"),
          h("dl.facts", h("dt", "Suit"), h("dd", r.suit ?? "—"),
            h("dt", "Colour"), h("dd", r.suit_color || "—"),
            h("dt", "Margin"), h("dd", Number(r.suit_margin || 0).toFixed(3)),
            h("dt", "Source"), h("dd", r.suit_source || "—")),
          h("div", { style: { marginTop: "10px" } },
            scores.length ? scores.map(([name, v], i) => meter(name, v, i === 0)) : meter("Confidence", r.suit_confidence, true))),
        h("section",
          h("h3", "Occupancy"),
          h("p.poll-meta", { style: { margin: "0 0 8px" } }, occ.reason || ""),
          h("dl.facts",
            h("dt", "White"), h("dd", pct(occ.white_ratio)),
            h("dt", "Green felt"), h("dd", pct(occ.green_ratio)),
            h("dt", "Edges"), h("dd", pct(occ.edge_ratio)),
            h("dt", "Brightness"), h("dd", `${fmtNum(occ.mean_brightness)} ± ${fmtNum(occ.brightness_std)}`))),
        rawBlock("Raw reading", r))));
}

// ---- System

pages.system = (main) => {
  const body = h("div.grid-2");
  const meta = h("span.poll-meta");
  async function load() {
    const t0 = performance.now();
    const [hr, ir] = await Promise.all([api("GET", "/health"), api("GET", "/info")]);
    meta.textContent = `Round trip ${Math.round(performance.now() - t0)} ms at ${clock(Date.now())}`;
    if (ir.ok) info = ir.json;
    const hj = hr.json || {};
    const ij = ir.json || {};
    const win = hj.control?.window;
    const cv = ij.card_vision || {};
    swap(body, 
      h("section.panel", h("div.row", { style: { justifyContent: "space-between", alignItems: "center", marginBottom: "12px" } },
        h("h2", { style: { margin: 0 } }, "Health"), h("span.pill." + (hr.ok ? "ok" : "bad"), hr.ok ? "Online" : "Unreachable")),
        h("dl.facts",
          h("dt", "Status"), h("dd", hj.status || "—"),
          h("dt", "Control backend"), h("dd", hj.control?.backend || "—"),
          h("dt", "Input reference"), h("dd", win ? JSON.stringify(win) : "No frame captured yet")),
        rawBlock("Raw /health", hj)),
      h("section.panel", h("h2", "Build and configuration"),
        h("dl.facts",
          h("dt", "Server"), h("dd", `${ij.name || "—"} ${ij.version || ""}`),
          h("dt", "OCR"), h("dd", ij.ocr_available ? "Available (tesseract)" : "Not available, numbers are not read"),
          h("dt", "Mapping"), h("dd", ij.mapping?.name || "—"),
          h("dt", "Window title"), h("dd", ij.mapping?.window_title || "—"),
          h("dt", "Named actions"), h("dd", (ij.mapping?.actions || []).map((a) => a.name).join(", ") || "None"),
          h("dt", "Card vision"), h("dd", cv.configured ? `${cv.profile}, ${cv.suit_templates} suit and ${cv.rank_templates} rank templates` : "Not configured")),
        rawBlock("Raw /info", ij)));
  }
  put(main, head("System", "Server health and what this build was compiled and configured with.", [meta, h("button.btn", { type: "button", onclick: load }, "Refresh")]), body);
  load();
};

// ---- Inspector

pages.inspector = (main) => {
  let hidePoll = true;
  let selected = null;
  const list = h("ul.log");
  const detail = h("div");
  const pollBox = h("input", { type: "checkbox", checked: true, onchange: (e) => { hidePoll = e.target.checked; draw(); } });

  function curlFor(e) {
    const url = new URL(e.path, location.href).href;
    if (e.method === "GET") return `curl -s '${url}'`;
    if (typeof e.request === "string" && e.requestType === "application/json")
      return `curl -s -X ${e.method} '${url}' -H 'Content-Type: application/json' -d '${e.request.replace(/'/g, "'\\''")}'`;
    return `curl -s -X ${e.method} '${url}' --data-binary @image.png`;
  }

  function draw() {
    const rows = log.filter((e) => !(hidePoll && e.poll));
    if (!selected && rows[0]) selected = rows[0].id;
    swap(list, ...(rows.length ? rows.map((e) => h("li", h("button", { type: "button", "aria-current": e.id === selected ? "true" : "false", onclick: () => { selected = e.id; draw(); } },
      h("span.m", e.method), h("span.p", e.path), h("span.st" + (e.status >= 400 || !e.status ? ".bad" : ""), e.status || "ERR"),
      h("span.when", `${clock(e.at)}, ${Math.round(e.ms)} ms${e.poll ? ", polling" : ""}`)))) : [h("li", h("div.empty", "No requests recorded yet."))]));
    const e = log.find((x) => x.id === selected);
    if (!e) { swap(detail, h("div.panel.flat", emptyState("Nothing selected", "Every request the dashboard makes is recorded here."))); return; }
    let reqView = null;
    if (e.request !== undefined) {
      let parsed = e.request;
      try { parsed = JSON.parse(e.request); } catch (_) { /* not JSON */ }
      reqView = h("section", h("h3", "Request body"), jsonView(parsed));
    }
    const resText = typeof e.response === "string" ? e.response : JSON.stringify(e.response, null, 2);
    swap(detail, h("div.panel.stack",
      h("div.row", { style: { justifyContent: "space-between", alignItems: "center" } },
        h("h2", { style: { margin: 0, fontFamily: "var(--code)", fontSize: "1rem" } }, `${e.method} ${e.path}`),
        h("div.head-tools",
          h("span.pill." + (e.status && e.status < 400 ? "ok" : "bad"), e.status ? `HTTP ${e.status}` : "No response"),
          h("button.btn.small", { type: "button", onclick: () => copyText(curlFor(e)) }, "Copy as curl"),
          h("button.btn.small", { type: "button", onclick: () => copyText(resText ?? "") }, "Copy response"))),
      h("p.poll-meta", { style: { margin: 0 } }, `${new Date(e.at).toLocaleString()}, ${Math.round(e.ms)} ms${e.contentType ? `, ${e.contentType}` : ""}`),
      reqView,
      h("section", h("h3", "Response"), e.error ? h("p", e.error) : jsonView(e.response ?? ""))));
  }

  const quick = ["/state", "/health", "/info"].map((p) => h("button.btn.small", { type: "button", onclick: async () => { await api("GET", p); selected = log[0].id; draw(); } }, `GET ${p}`));
  put(main, head("Inspector", "Raw responses from the last requests this dashboard made, newest first.", [h("label.toggle", pollBox, "Hide polling"), ...quick]),
    h("div.inspector", list, detail));
  logListeners.add(draw);
  draw();
  return () => logListeners.delete(draw);
};

// ------------------------------------------------------------------ router + theme

function route() {
  const name = (location.hash.replace(/^#\/?/, "") || "table").split("?")[0];
  const page = pages[name] ? name : "table";
  if (cleanup) { try { cleanup(); } catch (_) { /* ignore */ } }
  const main = $("#main");
  swap(main, );
  document.querySelectorAll(".nav a").forEach((a) => {
    if (a.dataset.page === page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = `${$(`.nav a[data-page="${page}"]`).firstChild.textContent.trim()} | glance`;
  cleanup = pages[page](main) || null;
}

function setTheme(choice) {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  try {
    if (choice === "system") localStorage.removeItem("glance.theme");
    else localStorage.setItem("glance.theme", choice);
  } catch (_) { /* storage unavailable: theme lasts for this visit */ }
  document.querySelectorAll("[data-theme-choice]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === choice)));
}

async function boot() {
  document.querySelectorAll("[data-theme-choice]").forEach((b) => b.addEventListener("click", () => setTheme(b.dataset.themeChoice)));
  setTheme(document.documentElement.dataset.theme || "system");
  await Promise.all([loadInfo(), heartbeat()]);
  setInterval(heartbeat, 8000);
  window.addEventListener("hashchange", route);
  route();
}

boot();
