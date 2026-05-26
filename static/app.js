const state = {
  mode: "calendar",
  selectedDates: new Set(),
  calendarYear: new Date().getFullYear(),
  calendarMonth: new Date().getMonth(),
  resolvedDates: [],
  generatedEntries: [],
  defaultDescriptionWords: 80,
  hoursMode: "constant",
  rangeFrom: "",
  rangeTill: "",
  hasGenerated: false,
  /** After entries exist: "pick" (Select for AI) | "edit" */
  calMode: "pick",
  activeEditDate: null,
  activeEditIsNew: false,
  submittedEntries: [],
  /** @type {{ id: string, filename: string, kind: string, text: string, char_count: number }[]} */
  referenceDocuments: [],
};

const WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const DOW_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

let rangeDebounceTimer = null;

function $(id) {
  return document.getElementById(id);
}

function showStatus(msg, type = "ok") {
  const el = $("status");
  el.textContent = msg;
  const variant = type === "error" ? "error" : type === "info" ? "info" : "ok";
  el.className = `toast show ${variant} toast-compact`;
}

function clearStatus() {
  const el = $("status");
  el.className = "toast toast-compact";
  el.textContent = "";
}

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle("loading", loading);
}

const API_TIMEOUT_MS = 20000;
const API_GENERATE_TIMEOUT_MS = 180000; // Gemini can take 1–3 minutes
const API_BOT_TIMEOUT_MS = 1800000; // Playwright: one entry ≈ 1–3 min; many dates need longer

async function api(path, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
      signal: options.signal || controller.signal,
    });
  } catch (e) {
    if (e.name === "AbortError") {
      const mins = Math.round(timeoutMs / 60000);
      const hint =
        timeoutMs >= API_BOT_TIMEOUT_MS
          ? "Automation can take many minutes per entry — wait and try again only if the browser closed."
          : timeoutMs >= API_GENERATE_TIMEOUT_MS
            ? "AI generation is still running or the server is slow — wait a moment and refresh."
            : "Check that VTU AIDS is running and try again.";
      throw new Error(
        mins >= 1
          ? `Request timed out after ${mins} min. ${hint}`
          : `Request timed out. ${hint}`
      );
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let detail = data.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
    } else if (detail && typeof detail === "object") {
      detail = JSON.stringify(detail);
    }
    throw new Error(detail || res.statusText || "Request failed");
  }
  return data;
}

function applyConfigToForm(cfg) {
  $("cfg-username").value = cfg.username || "";
  const model = cfg.gemini_model || "gemini-2.5-flash";
  const sel = $("cfg-gemini-model");
  if ([...sel.options].some((o) => o.value === model)) sel.value = model;
  else sel.value = "gemini-2.5-flash";
  $("cfg-default-internship").value = cfg.default_internship || "";
  $("cfg-description-words").value = cfg.default_description_words ?? 80;
  state.defaultDescriptionWords = cfg.default_description_words ?? 80;
  setHoursMode(cfg.hours_mode || "constant");
  $("hours-constant").value = cfg.hours_constant ?? cfg.default_hours ?? 6;
  $("hours-min").value = cfg.hours_min ?? 5;
  $("hours-max").value = cfg.hours_max ?? 8;
  $("internship").value = cfg.default_internship || "";
  $("description-words").value = state.defaultDescriptionWords;
  $("cfg-password").value = "";
  $("cfg-gemini-key").value = "";
  $("cfg-password").placeholder = cfg.has_password ? "(saved — leave blank to keep)" : "";
  $("cfg-gemini-key").placeholder = cfg.has_gemini_api_key
    ? "(saved — leave blank to keep)"
    : "";
}

async function loadConfig() {
  const cfg = await api("/api/config");
  applyConfigToForm(cfg);
}

async function saveConfig() {
  const keyInput = $("cfg-gemini-key").value.trim();
  const body = {
    username: $("cfg-username").value.trim(),
    password: $("cfg-password").value,
    gemini_model: $("cfg-gemini-model").value.trim(),
    default_internship: $("cfg-default-internship").value.trim(),
    default_description_words: parseInt($("cfg-description-words").value, 10) || 80,
    hours_mode: state.hoursMode,
    hours_constant: parseFloat($("hours-constant").value) || 6,
    hours_min: parseFloat($("hours-min").value) || 5,
    hours_max: parseFloat($("hours-max").value) || 8,
  };
  if (keyInput) body.gemini_api_key = keyInput.replace(/\s+/g, "");
  const cfg = await api("/api/config", { method: "POST", body: JSON.stringify(body) });
  applyConfigToForm(cfg);
}

function renderDateChips(dates) {
  const el = $("date-chips");
  const badge = $("date-count");
  el.innerHTML = "";
  if (!dates.length) {
    el.innerHTML = '<span class="chip empty">No dates selected</span>';
    badge.textContent = "0 dates";
    badge.classList.remove("has-dates");
    return;
  }
  dates.forEach((d) => {
    const span = document.createElement("span");
    span.className = "chip";
    span.textContent = d;
    el.appendChild(span);
  });
  badge.textContent = dates.length === 1 ? "1 date" : `${dates.length} dates`;
  badge.classList.add("has-dates");
}

function iso(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function todayIso() {
  return iso(new Date());
}

function isFutureDate(dateStr) {
  return dateStr > todayIso();
}

function filterPastDates(dates) {
  const today = todayIso();
  return dates.filter((d) => d <= today);
}

function initDateInputLimits() {
  const today = todayIso();
  $("range-from").max = today;
  $("range-till").max = today;
}

function getEntryByDate(dateStr) {
  return state.generatedEntries.find((e) => (e.date || "").slice(0, 10) === dateStr);
}

function getSubmittedEntryByDate(dateStr) {
  return state.submittedEntries.find((e) => (e.date || "").slice(0, 10) === dateStr);
}

function snapshotEntryFields(entry) {
  return {
    description: entry.description || "",
    hoursWorked: entry.hoursWorked,
    skillsUsed: entry.skillsUsed || "",
    learningOutcomes: entry.learningOutcomes || "",
  };
}

function ensureEntryOriginal(entry) {
  if (entry.original) return;
  if (!entry.modified) {
    entry.original = snapshotEntryFields(entry);
  }
}

function normalizeLoadedEntry(entry) {
  if (!entry.original && !entry.modified) {
    entry.original = snapshotEntryFields(entry);
  }
  return entry;
}

function normalizeGeneratedEntries(entries) {
  return entries.map((e) => {
    const entry = { ...e, modified: Boolean(e.modified) };
    entry.original = snapshotEntryFields(entry);
    if (!entry.modified) {
      entry.modified = false;
    }
    return entry;
  });
}

function getDefaultHoursForNewEntry() {
  if (state.hoursMode === "range") {
    const min = parseFloat($("hours-min").value) || 5;
    const max = parseFloat($("hours-max").value) || 8;
    return Math.round(((min + max) / 2) * 4) / 4;
  }
  return parseFloat($("hours-constant").value) || 6;
}

function buildBlankEntry(dateStr) {
  return {
    date: dateStr,
    internship: $("internship").value.trim(),
    description: "",
    hoursWorked: getDefaultHoursForNewEntry(),
    learningOutcomes: "",
    skillsUsed: "",
    referenceLinks: "",
    blockersRisks: "",
    modified: false,
  };
}

function updateEntryEditorChrome(entry, { isNew = false } = {}) {
  const canRevert = Boolean(!isNew && entry?.original);
  $("edit-modified-badge").classList.toggle("hidden", isNew || !entry?.modified);
  $("edit-new-badge").classList.toggle("hidden", !isNew);
  $("edit-create-hint").classList.toggle("hidden", !isNew);
  $("edit-date-label").textContent = isNew ? `Create — ${state.activeEditDate}` : `Entry — ${state.activeEditDate}`;

  const editor = $("entry-editor");
  if (editor) {
    editor.classList.toggle("is-create", isNew);
    editor.classList.toggle("is-existing", !isNew);
  }

  const saveBtn = $("btn-save-entry");
  if (saveBtn) saveBtn.textContent = isNew ? "Create entry" : "Save this day";
  const revertBtn = $("btn-revert-entry");
  if (revertBtn) {
    revertBtn.disabled = !canRevert;
    revertBtn.title = canRevert
      ? "Restore the last AI-generated text for this day"
      : isNew
        ? "Use Fill with AI first"
        : "No AI version to revert to";
  }
  const deleteBtn = $("btn-delete-entry");
  if (deleteBtn) {
    deleteBtn.disabled = isNew;
    deleteBtn.classList.toggle("hidden", isNew);
    deleteBtn.title = isNew
      ? ""
      : "Remove this day from saved entries (you can recreate it right after)";
  }
  const addBackBtn = $("btn-add-back-entry");
  if (addBackBtn) {
    addBackBtn.classList.toggle("hidden", !isNew);
  }
}

/** Section 3: show editor for existing/new day, or pick-a-day hint. */
function refreshSection3View() {
  const hasDay = Boolean(state.activeEditDate);
  const selectHint = $("section3-select-hint");
  const editor = $("entry-editor");

  if (selectHint) {
    selectHint.classList.toggle("hidden", hasDay || !state.hasGenerated);
  }
  if (editor) {
    editor.classList.toggle("hidden", !hasDay);
  }

  const previewEmpty = $("preview-empty");
  if (previewEmpty && state.hasGenerated) {
    previewEmpty.classList.add("hidden");
  }
}

function buildReferenceContext() {
  if (!state.referenceDocuments.length) return "";
  return state.referenceDocuments
    .map((d) => `--- ${d.filename} (${d.kind}) ---\n${d.text}`)
    .join("\n\n");
}

function getStep2GenerateContext() {
  const work_description = $("work-description").value.trim();
  const reference_context = buildReferenceContext();
  const internship = $("internship").value.trim();
  if (!work_description && !reference_context) {
    throw new Error(
      "Enter what you did in Step 2 and/or upload at least one reference document."
    );
  }
  if (!internship) throw new Error("Set internship label in Step 2 first.");
  return {
    work_description,
    reference_context,
    internship,
    description_words: parseInt($("description-words").value, 10) || state.defaultDescriptionWords || 80,
    ...getHoursGeneratePayload(),
  };
}

function renderDocumentList() {
  const list = $("doc-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.referenceDocuments.length) return;

  state.referenceDocuments.forEach((doc) => {
    const li = document.createElement("li");
    li.className = "doc-item";
    li.dataset.id = doc.id;
    const chars =
      doc.char_count >= 1000
        ? `${(doc.char_count / 1000).toFixed(1)}k chars`
        : `${doc.char_count} chars`;
    li.innerHTML = `
      <span class="doc-item-meta">
        <strong class="doc-item-name">${escapeHtml(doc.filename)}</strong>
        <span class="doc-item-kind">${escapeHtml(doc.kind)} · ${chars}</span>
      </span>
      <button type="button" class="btn btn-icon doc-item-remove" aria-label="Remove ${escapeHtml(doc.filename)}">×</button>`;
    li.querySelector(".doc-item-remove").addEventListener("click", () => {
      state.referenceDocuments = state.referenceDocuments.filter((d) => d.id !== doc.id);
      renderDocumentList();
    });
    list.appendChild(li);
  });
}

function formatApiError(data, status, fallback) {
  let detail = data?.detail;
  if (Array.isArray(detail)) {
    detail = detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
  } else if (detail && typeof detail === "object") {
    detail = JSON.stringify(detail);
  }
  const msg = detail || fallback;
  if (status === 404 && String(msg).toLowerCase().includes("not found")) {
    return (
      "Upload API not found. Restart the app (close and open VTU AIDS again), " +
      "then hard-refresh this page (Ctrl+F5)."
    );
  }
  return msg;
}

async function uploadReferenceDocument(file) {
  const form = new FormData();
  form.append("file", file, file.name);
  const res = await fetch("/api/documents/extract", { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatApiError(data, res.status, res.statusText || "Upload failed"));
  }
  return data;
}

function initDocumentUpload() {
  const input = $("doc-file-input");
  const btn = $("btn-upload-doc");
  if (!input || !btn) return;

  btn.addEventListener("click", () => input.click());

  input.addEventListener("change", async () => {
    const files = [...input.files];
    input.value = "";
    if (!files.length) return;

    setLoading(btn, true);
    let ok = 0;
    try {
      for (const file of files) {
        try {
          const data = await uploadReferenceDocument(file);
          state.referenceDocuments.push({
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
            filename: data.filename,
            kind: data.kind,
            text: data.text,
            char_count: data.char_count,
          });
          ok += 1;
        } catch (e) {
          showStatus(`${file.name}: ${e.message}`, "error");
        }
      }
      renderDocumentList();
      if (ok) {
        showStatus(
          ok === 1 ? "Document added for AI context." : `${ok} documents added for AI context.`,
          "ok"
        );
      }
    } finally {
      setLoading(btn, false);
    }
  });
}

function applyAiEntryToState(dateStr, aiEntry) {
  const snap = snapshotEntryFields(aiEntry);
  const merged = {
    ...aiEntry,
    date: dateStr,
    modified: false,
    original: snap,
  };
  let entry = getEntryByDate(dateStr);
  if (!entry) {
    state.generatedEntries.push(merged);
    state.generatedEntries.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
    state.activeEditIsNew = false;
    entry = merged;
  } else {
    Object.assign(entry, merged);
    entry.original = snap;
    entry.modified = false;
  }
  fillEntryEditorFields(entry);
  updateEntryEditorChrome(entry, { isNew: false });
  return entry;
}

function fillEntryEditorFields(entry) {
  $("edit-description").value = entry.description || "";
  $("edit-hours").value = entry.hoursWorked ?? "";
  $("edit-skills").value = entry.skillsUsed || "";
  $("edit-learnings").value = entry.learningOutcomes || "";
}

function applyDayClasses(btn, isoStr) {
  if (isFutureDate(isoStr)) {
    btn.classList.add("disabled");
    btn.disabled = true;
    return;
  }

  const entry = getEntryByDate(isoStr);
  const submittedEntry = getSubmittedEntryByDate(isoStr);
  const todayStr = todayIso();

  if (entry) {
    btn.classList.add("has-entry");
    if (entry.modified) btn.classList.add("entry-modified");
  } else if (submittedEntry) {
    btn.classList.add("has-submitted-entry");
  } else if (state.hasGenerated) {
    btn.classList.add("no-entry");
  }

  if (state.activeEditDate === isoStr) {
    btn.classList.add("viewing");
    if (state.activeEditIsNew) btn.classList.add("day-creating");
  }

  const allowPickHighlight =
    !state.hasGenerated ||
    state.calMode === "pick" ||
    Boolean(state.rangeFrom && state.rangeTill);
  if (allowPickHighlight && state.selectedDates.has(isoStr)) {
    btn.classList.add("selected");
    if (state.rangeFrom && state.rangeTill) {
      const sorted = [...state.selectedDates].sort();
      if (isoStr === sorted[0]) btn.classList.add("range-start");
      if (isoStr === sorted[sorted.length - 1]) btn.classList.add("range-end");
    }
  }

  if (isoStr === todayStr) btn.classList.add("today");

  if (
    allowPickHighlight &&
    state.rangeFrom &&
    state.rangeTill &&
    isoStr >= state.rangeFrom &&
    isoStr <= state.rangeTill
  ) {
    btn.classList.add("in-range");
    if (!state.selectedDates.has(isoStr)) btn.classList.add("range-skip");
  }
}

function onDayClick(isoStr) {
  if (isFutureDate(isoStr)) return;
  if (!state.hasGenerated) {
    toggleDate(isoStr);
    return;
  }
  if (state.calMode === "pick") {
    toggleDate(isoStr);
    return;
  }
  openEntryEditor(isoStr);
}

function updateCalHint() {
  const el = $("cal-hint");
  if (!el) return;
  if (!state.hasGenerated) {
    el.textContent =
      "Future dates disabled. Select one or more past days, then use Generate with AI in Step 2.";
    return;
  }
  if (state.calMode === "pick") {
    el.textContent =
      "Select for AI (default): click days to highlight, then Generate with AI in Step 2.";
    return;
  }
  el.innerHTML =
    '<strong>Edit</strong> on: click any past day — <span class="legend-dot has-entry"></span> blue = outbox · ' +
    '<span class="legend-dot submitted-entry-legend"></span> green = submitted · ' +
    '<span class="legend-dot no-entry-legend"></span> dashed = create in Step 3.';
}

function reconcileEditorWithCalMode() {
  if (state.calMode === "pick") {
    if (state.activeEditDate) closeEntryEditor();
    return;
  }
  if (state.activeEditDate) {
    openEntryEditor(state.activeEditDate, { skipScroll: true });
  }
}

function syncCalModeToggleUi() {
  const wrap = $("cal-mode-wrap");
  const sw = $("cal-mode-switch");
  const pickLabel = $("cal-mode-label-pick");
  const editLabel = $("cal-mode-label-edit");
  const isEdit = state.calMode === "edit";
  if (sw) sw.checked = isEdit;
  if (wrap) wrap.classList.toggle("is-edit", isEdit);
  if (pickLabel) pickLabel.classList.toggle("is-active", !isEdit);
  if (editLabel) editLabel.classList.toggle("is-active", isEdit);
}

function setCalMode(mode) {
  state.calMode = mode === "edit" ? "edit" : "pick";
  syncCalModeToggleUi();
  if (state.calMode === "pick") {
    state.selectedDates = new Set();
    state.rangeFrom = "";
    state.rangeTill = "";
    state.resolvedDates = [];
    renderDateChips([]);
    closeEntryEditor();
  } else {
    reconcileEditorWithCalMode();
    if (state.hasGenerated) syncCalendarAfterGenerate();
  }
  updateCalHint();
  renderCalendar();
}

function setPostGenerateEnabled(enabled) {
  state.hasGenerated = enabled;
  $("btn-download").disabled = !enabled;
  $("btn-run").disabled = !enabled;
  const modeWrap = $("cal-mode-wrap");
  if (modeWrap) modeWrap.classList.toggle("hidden", !enabled || state.mode === "range");
  if (enabled) {
    $("btn-download").title = "Download Excel workbook";
    $("btn-run").title = "Upload entries to VTU Internyet portal";
    setCalMode("pick");
  } else {
    state.calMode = "pick";
    syncCalModeToggleUi();
    updateCalHint();
  }
}

function mergeGeneratedEntries(existing, incoming) {
  const byDate = new Map();
  for (const e of existing) {
    const d = (e.date || "").slice(0, 10);
    if (d) byDate.set(d, e);
  }
  for (const e of incoming) {
    const d = (e.date || "").slice(0, 10);
    if (d) byDate.set(d, e);
  }
  return [...byDate.values()].sort((a, b) => (a.date || "").localeCompare(b.date || ""));
}

function syncCalendarAfterGenerate() {
  const dates = [
    ...new Set([
      ...state.generatedEntries.map((e) => (e.date || "").slice(0, 10)),
      ...state.submittedEntries.map((e) => (e.date || "").slice(0, 10)),
    ].filter(Boolean))
  ].sort();
  state.selectedDates = new Set();
  state.rangeFrom = "";
  state.rangeTill = "";
  state.resolvedDates = dates;
  renderDateChips(dates);
  if (dates.length) focusCalendarOnDate(dates[0]);
  renderCalendar();
}

function focusCalendarOnDate(dateStr) {
  if (!dateStr) return;
  const d = new Date(dateStr + "T12:00:00");
  if (Number.isNaN(d.getTime())) return;
  state.calendarYear = d.getFullYear();
  state.calendarMonth = d.getMonth();
}

function applyResolvedDates(dates, { rangeFrom = "", rangeTill = "" } = {}) {
  const today = todayIso();
  const filtered = filterPastDates(dates);
  state.selectedDates = new Set(filtered);
  state.resolvedDates = [...filtered].sort();
  state.rangeFrom = rangeFrom;
  state.rangeTill = rangeTill && rangeTill > today ? today : rangeTill;
  if (dates.length) focusCalendarOnDate(dates[0]);
  renderDateChips(state.resolvedDates);
  renderCalendar();
}

function renderCalendar() {
  const grid = $("calendar-grid");
  grid.innerHTML = "";
  DOW_LABELS.forEach((l) => {
    const h = document.createElement("div");
    h.className = "dow";
    h.textContent = l;
    grid.appendChild(h);
  });

  const y = state.calendarYear;
  const m = state.calendarMonth;
  $("cal-month-label").textContent = new Date(y, m, 1).toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  const first = new Date(y, m, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const prevDays = new Date(y, m, 0).getDate();

  for (let i = 0; i < startPad; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "day other-month";
    btn.textContent = String(prevDays - startPad + i + 1);
    const pd = new Date(y, m - 1, prevDays - startPad + i + 1);
    const isoStr = iso(pd);
    applyDayClasses(btn, isoStr);
    btn.addEventListener("click", () => onDayClick(isoStr));
    grid.appendChild(btn);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "day";
    const isoStr = iso(new Date(y, m, d));
    applyDayClasses(btn, isoStr);
    btn.textContent = String(d);
    btn.addEventListener("click", () => onDayClick(isoStr));
    grid.appendChild(btn);
  }

  const total = startPad + daysInMonth;
  const rem = total % 7 === 0 ? 0 : 7 - (total % 7);
  for (let i = 1; i <= rem; i++) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "day other-month";
    btn.textContent = String(i);
    const nd = new Date(y, m + 1, i);
    const isoStr = iso(nd);
    applyDayClasses(btn, isoStr);
    btn.addEventListener("click", () => onDayClick(isoStr));
    grid.appendChild(btn);
  }
  applyCalendarModeClasses();
}

function applyCalendarModeClasses() {
  const grid = $("calendar-grid");
  if (!grid) return;
  grid.classList.toggle("cal-mode-edit", state.hasGenerated && state.calMode === "edit");
  grid.classList.toggle("cal-mode-pick", state.hasGenerated && state.calMode === "pick");
}

function openEntryEditor(dateStr, { forceCreate = false, skipScroll = false } = {}) {
  if (state.calMode === "pick") {
    setCalMode("edit");
  }
  let existing = forceCreate ? null : getEntryByDate(dateStr);
  
  if (!existing && !forceCreate) {
    const sub = getSubmittedEntryByDate(dateStr);
    if (sub) existing = sub;
  }
  
  state.activeEditDate = dateStr;
  state.activeEditIsNew = !existing;

  if (existing) {
    ensureEntryOriginal(existing);
    fillEntryEditorFields(existing);
    updateEntryEditorChrome(existing, { isNew: false });
  } else {
    fillEntryEditorFields(buildBlankEntry(dateStr));
    updateEntryEditorChrome(null, { isNew: true });
  }

  refreshSection3View();
  renderCalendar();
  renderPreview(state.generatedEntries);
  highlightTableRow(dateStr);
  if (!skipScroll) {
    $("entry-editor").scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function closeEntryEditor() {
  state.activeEditDate = null;
  state.activeEditIsNew = false;
  refreshSection3View();
  renderCalendar();
  renderPreview(state.generatedEntries);
  highlightTableRow(null);
}

function highlightTableRow(dateStr) {
  document.querySelectorAll("#preview-table tbody tr").forEach((tr) => {
    tr.classList.toggle("row-active", dateStr && tr.dataset.date === dateStr);
  });
}

function serializeEntryForApi(entry) {
  const out = {
    date: (entry.date || "").slice(0, 10),
    internship: entry.internship || "",
    description: entry.description || "",
    hoursWorked: entry.hoursWorked,
    learningOutcomes: entry.learningOutcomes || "",
    skillsUsed: entry.skillsUsed || "",
    referenceLinks: entry.referenceLinks || "",
    blockersRisks: entry.blockersRisks || "",
    modified: Boolean(entry.modified),
  };
  if (entry.original && typeof entry.original === "object") {
    out.original = entry.original;
  }
  return out;
}

async function persistEntries() {
  const payload = state.generatedEntries.map(serializeEntryForApi);
  const data = await api("/api/entries", {
    method: "PUT",
    body: JSON.stringify({ entries: payload }),
  });
  if (Array.isArray(data.entries)) {
    state.generatedEntries = data.entries.map(normalizeLoadedEntry);
  }
}

function readEntryFromEditor(dateStr) {
  const description = $("edit-description").value.trim();
  const skillsUsed = $("edit-skills").value.trim();
  const learningOutcomes = $("edit-learnings").value.trim();
  const internship = $("internship").value.trim();
  if (!description) throw new Error("Description is required.");
  if (!skillsUsed) throw new Error("Skills are required.");
  if (!learningOutcomes) throw new Error("Learnings are required.");
  if (!internship) throw new Error("Set internship label in Step 2 first.");
  const hoursWorked = parseFloat($("edit-hours").value);
  if (Number.isNaN(hoursWorked) || hoursWorked < 0 || hoursWorked > 24) {
    throw new Error("Enter valid hours (0–24).");
  }
  return {
    date: dateStr,
    internship,
    description,
    hoursWorked,
    skillsUsed,
    learningOutcomes,
    referenceLinks: "",
    blockersRisks: "",
  };
}

async function saveCurrentEntry() {
  const dateStr = state.activeEditDate;
  if (!dateStr) return;

  const payload = readEntryFromEditor(dateStr);
  let entry = getEntryByDate(dateStr);
  const submittedEntry = getSubmittedEntryByDate(dateStr);

  if (state.activeEditIsNew || (!entry && submittedEntry)) {
    entry = { ...payload, modified: true };
    if (submittedEntry) {
      entry.original = snapshotEntryFields(submittedEntry);
      state.submittedEntries = state.submittedEntries.filter((e) => (e.date || "").slice(0, 10) !== dateStr);
    }
    state.generatedEntries.push(entry);
    state.generatedEntries.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
    state.activeEditIsNew = false;
    syncCalendarAfterGenerate();
    showStatus(`Moved ${dateStr} back to outbox for update.`, "ok");
  } else if (entry) {
    ensureEntryOriginal(entry);
    Object.assign(entry, payload);
    entry.modified = true;
    showStatus(`Saved changes for ${dateStr}.`, "ok");
  } else {
    // Actually new
    entry = { ...payload, modified: true };
    state.generatedEntries.push(entry);
    state.generatedEntries.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
    state.activeEditIsNew = false;
    syncCalendarAfterGenerate();
    showStatus(`Created entry for ${dateStr}.`, "ok");
  }

  await persistEntries();
  updateEntryEditorChrome(entry, { isNew: false });
  renderPreview(state.generatedEntries);
  renderCalendar();
}

async function fillEntryWithAI() {
  const dateStr = state.activeEditDate;
  if (!dateStr) return;
  clearStatus();
  showStatus("Generating this day with AI…", "info");
  setLoading($("btn-fill-ai"), true);
  try {
    const data = await api(
      "/api/generate-day",
      { method: "POST", body: JSON.stringify({ date: dateStr, ...getStep2GenerateContext() }) },
      API_GENERATE_TIMEOUT_MS
    );
    applyAiEntryToState(dateStr, data.entry);
    await persistEntries();
    syncCalendarAfterGenerate();
    renderPreview(state.generatedEntries);
    renderCalendar();
    const note = data.model_used ? ` (model: ${data.model_used})` : "";
    showStatus(`Filled ${dateStr} with AI.${note}`, "ok");
  } finally {
    setLoading($("btn-fill-ai"), false);
  }
}

async function revertCurrentEntry() {
  const dateStr = state.activeEditDate;
  if (!dateStr) return;
  const entry = getEntryByDate(dateStr);
  if (!entry?.original) {
    showStatus("Use Fill with AI first, or revert is not available for this day.", "error");
    return;
  }
  const orig = entry.original;
  entry.description = orig.description || "";
  entry.hoursWorked = orig.hoursWorked;
  entry.skillsUsed = orig.skillsUsed || "";
  entry.learningOutcomes = orig.learningOutcomes || "";
  entry.modified = false;
  fillEntryEditorFields(entry);
  updateEntryEditorChrome(entry, { isNew: false });
  await persistEntries();
  renderPreview(state.generatedEntries);
  renderCalendar();
  showStatus(`Reverted ${dateStr} to the AI-generated version.`, "ok");
}

async function deleteCurrentEntry() {
  const dateStr = state.activeEditDate;
  if (!dateStr) return;
  if (state.calMode === "pick") setCalMode("edit");
  if (state.activeEditIsNew) {
    showStatus("No saved entry for this day yet.", "error");
    return;
  }
  if (!window.confirm(`Delete the saved entry for ${dateStr}? You can recreate it in this editor right after.`)) {
    return;
  }

  setLoading($("btn-delete-entry"), true);
  try {
    const data = await api(`/api/entries/day/${encodeURIComponent(dateStr)}`, {
      method: "DELETE",
    });
    state.generatedEntries = (data.entries || []).map(normalizeLoadedEntry);
    syncCalendarAfterGenerate();
    renderPreview(state.generatedEntries);
    setCalMode("edit");
    openEntryEditor(dateStr, { forceCreate: true });
    showStatus(
      `Deleted ${dateStr}. Use Fill with AI or Create entry below to add it back.`,
      "ok"
    );
  } finally {
    setLoading($("btn-delete-entry"), false);
  }
}

async function addBackEntryWithAI() {
  const dateStr = state.activeEditDate;
  if (!dateStr || !state.activeEditIsNew) return;
  try {
    await fillEntryWithAI();
  } catch (e) {
    showStatus(e.message, "error");
  }
}

function toggleDate(d) {
  if (isFutureDate(d)) return;
  if (state.selectedDates.has(d)) state.selectedDates.delete(d);
  else state.selectedDates.add(d);
  if (state.mode === "calendar") {
    state.rangeFrom = "";
    state.rangeTill = "";
  }
  syncFromSelection();
}

function syncFromSelection() {
  const filtered = filterPastDates([...state.selectedDates]);
  state.selectedDates = new Set(filtered);
  state.resolvedDates = filtered.sort();
  renderDateChips(state.resolvedDates);
  renderCalendar();
}

function getSkipWeekdays() {
  const skip = [];
  document.querySelectorAll(".skip-wd:checked").forEach((cb) => {
    skip.push(cb.value);
  });
  return skip;
}

async function resolveRangeDates(silent = false) {
  const today = todayIso();
  let from = $("range-from").value;
  let till = $("range-till").value;
  if (!from || !till) {
    if (!silent) throw new Error("Choose both From and Till dates.");
    return;
  }
  if (from > today) from = today;
  if (till > today) till = today;
  $("range-from").value = from;
  $("range-till").value = till;
  const body = {
    mode: "range",
    from,
    till,
    skip_weekdays: getSkipWeekdays(),
  };
  const data = await api("/api/dates/resolve", {
    method: "POST",
    body: JSON.stringify(body),
  });
  applyResolvedDates(data.dates, { rangeFrom: from, rangeTill: till });
  return data.dates;
}

function scheduleRangeResolve() {
  clearTimeout(rangeDebounceTimer);
  rangeDebounceTimer = setTimeout(async () => {
    const from = $("range-from").value;
    const till = $("range-till").value;
    if (!from || !till) return;
    try {
      await resolveRangeDates(true);
    } catch {
      /* ignore while user is still picking */
    }
  }, 450);
}

async function resolveCurrentDates() {
  if (state.mode === "range") {
    const dates = await resolveRangeDates();
    if (!dates.length) throw new Error("No dates in range (check weekday filters).");
    return dates;
  }
  syncFromSelection();
  if (!state.resolvedDates.length) throw new Error("Select at least one date on the calendar.");
  return state.resolvedDates;
}

function truncateWords(text, maxWords = 24) {
  const words = String(text || "").trim().split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return words.join(" ");
  return words.slice(0, maxWords).join(" ") + "…";
}

function renderPreview(entries) {
  if (!state.hasGenerated) {
    entries = [];
  }
  const table = $("preview-table");
  const empty = $("preview-empty");
  const countEl = $("preview-count");

  if (!entries.length && !(state.activeEditIsNew && state.activeEditDate)) {
    table.innerHTML = "";
    empty.classList.remove("hidden");
    countEl.textContent = "No entries yet";
    refreshSection3View();
    return;
  }

  empty.classList.add("hidden");
  if (state.activeEditIsNew && state.activeEditDate) {
    countEl.textContent = `New entry — ${state.activeEditDate}`;
  } else if (entries.length === 1) {
    countEl.textContent = "1 entry";
  } else {
    countEl.textContent = `${entries.length} entries`;
  }

  table.innerHTML = `
    <thead>
      <tr>
        <th>Date</th>
        <th>Description</th>
        <th>Hrs</th>
        <th>Learnings</th>
        <th>Skills</th>
      </tr>
    </thead>
    <tbody></tbody>`;
  const tbody = table.querySelector("tbody");
  const sorted = [...entries].sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  sorted.forEach((e) => {
    const tr = document.createElement("tr");
    const d = (e.date || "").slice(0, 10);
    tr.dataset.date = d;
    if (e.modified) tr.classList.add("row-modified");
    if (state.activeEditDate === d && !state.activeEditIsNew) tr.classList.add("row-active");
    tr.innerHTML = `
      <td>${escapeHtml(d)}</td>
      <td class="desc-cell">${escapeHtml(truncateWords(e.description, 28))}</td>
      <td>${escapeHtml(String(e.hoursWorked ?? ""))}</td>
      <td class="desc-cell">${escapeHtml(truncateWords(e.learningOutcomes, 16))}</td>
      <td>${escapeHtml(e.skillsUsed || "")}</td>`;
    tr.addEventListener("click", () => {
      setCalMode("edit");
      openEntryEditor(d);
    });
    tbody.appendChild(tr);
  });

  if (state.activeEditIsNew && state.activeEditDate) {
    const d = state.activeEditDate;
    const tr = document.createElement("tr");
    tr.className = "row-pending-create row-active";
    tr.dataset.date = d;
    tr.innerHTML = `
      <td>${escapeHtml(d)}</td>
      <td colspan="4" class="desc-cell">No entry yet — use the form above to create</td>`;
    tr.addEventListener("click", () => {
      setCalMode("edit");
      openEntryEditor(d, { forceCreate: true });
    });
    const rows = [...tbody.querySelectorAll("tr")];
    const insertBefore = rows.find((r) => r.dataset.date > d);
    if (insertBefore) tbody.insertBefore(tr, insertBefore);
    else tbody.appendChild(tr);
  }

  refreshSection3View();
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/** Restore saved entries after refresh (calendar marks, editor, step 3). */
async function loadPersistedEntries() {
  try {
    const res = await fetch("/api/entries/preview");
    if (!res.ok) return;
    const data = await res.json();
    if (!data.entries?.length && !data.submitted?.length) return;

    state.generatedEntries = (data.entries || []).map(normalizeLoadedEntry);
    state.submittedEntries = data.submitted || [];
    state.activeEditDate = null;
    state.activeEditIsNew = false;
    setPostGenerateEnabled(true);
    setCalMode("pick");
    syncCalendarAfterGenerate();
    renderPreview(state.generatedEntries);
    refreshSection3View();
  } catch {
    /* no saved file yet */
  }
}

async function generateEntries() {
  clearStatus();
  const dates = await resolveCurrentDates();
  const ctx = getStep2GenerateContext();
  const body = {
    dates,
    work_description: ctx.work_description,
    reference_context: ctx.reference_context,
    internship: ctx.internship,
    description_words: ctx.description_words,
    hours_mode: ctx.hours_mode,
    hours_constant: ctx.hours_constant,
    hours_min: ctx.hours_min,
    hours_max: ctx.hours_max,
  };
  showStatus("Generating with Gemini…", "info");
  setLoading($("btn-generate"), true);
  let data;
  try {
    data = await api(
      "/api/generate",
      { method: "POST", body: JSON.stringify(body) },
      API_GENERATE_TIMEOUT_MS
    );
  } finally {
    setLoading($("btn-generate"), false);
  }
  const incoming = normalizeGeneratedEntries(data.entries);
  const prev = state.generatedEntries;
  state.generatedEntries = mergeGeneratedEntries(prev, incoming);
  state.activeEditDate = null;
  state.activeEditIsNew = false;
  setPostGenerateEnabled(true);
  setCalMode("pick");
  syncCalendarAfterGenerate();
  renderPreview(state.generatedEntries);
  refreshSection3View();
  const modelNote = data.model_used ? ` (model: ${data.model_used})` : "";
  showStatus(
    `Generated ${incoming.length} day(s); ${state.generatedEntries.length} total saved.${modelNote}`,
    "ok"
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForBotCompletion() {
  const deadline = Date.now() + API_BOT_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const st = await api("/api/run-bot/status", {}, API_TIMEOUT_MS);
    if (!st.running) {
      return st;
    }
    await sleep(2000);
  }
  throw new Error(
    "Automation is still running (browser may be open). Wait for it to finish, or close Chromium and check %LOCALAPPDATA%\\VTU AIDS\\bot_run.log"
  );
}

async function runBot() {
  if (!state.hasGenerated) {
    showStatus("Generate entries with AI first (step 2).", "error");
    return;
  }
  clearStatus();
  showStatus(
    "Saving entries and starting automation… A Chromium window should open.",
    "info"
  );
  setLoading($("btn-run"), true);
  try {
    await persistEntries();
    const start = await api(
      "/api/run-bot",
      {
        method: "POST",
        body: JSON.stringify({
          headed: $("run-headed").checked,
          skip_on_error: $("run-skip-errors").checked,
        }),
      },
      API_TIMEOUT_MS
    );
    if (start.already_running) {
      showStatus(start.message || "Automation is already running.", "info");
    } else {
      showStatus(start.message || "Automation started…", "info");
    }
    const data = await waitForBotCompletion();
    let msg = data.ok
      ? "Automation finished successfully."
      : `Automation exited with code ${data.exit_code ?? "?"}.`;
    if (data.error) msg += `\n\n${data.error}`;
    if (data.stderr) msg += `\n\n${data.stderr}`;
    if (data.stdout) msg += `\n\n${data.stdout}`;
    if (data.ok) {
      state.generatedEntries.forEach((e) => {
        e.modified = false;
      });
      renderPreview(state.generatedEntries);
      renderCalendar();
    }
    showStatus(msg, data.ok ? "ok" : "error");
  } finally {
    setLoading($("btn-run"), false);
  }
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".segmented-item[data-mode]").forEach((t) => {
    t.classList.toggle("active", t.dataset.mode === mode);
    t.setAttribute("aria-selected", t.dataset.mode === mode ? "true" : "false");
  });
  $("panel-range").classList.toggle("hidden", mode !== "range");
  $("panel-calendar").classList.toggle("hidden", mode === "range");
  const modeWrap = $("cal-mode-wrap");
  if (modeWrap) modeWrap.classList.toggle("hidden", mode === "range" || !state.hasGenerated);
  if (mode === "range") {
    const from = $("range-from").value;
    const till = $("range-till").value;
    if (from && till) scheduleRangeResolve();
  } else {
    state.rangeFrom = "";
    state.rangeTill = "";
    renderCalendar();
  }
}

function setHoursMode(mode) {
  const m = mode === "range" ? "range" : "constant";
  state.hoursMode = m;
  document.querySelectorAll("#hours-mode-tabs .segmented-item").forEach((tab) => {
    const active = tab.dataset.hoursMode === m;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  $("hours-panel-constant").classList.toggle("hidden", m !== "constant");
  $("hours-panel-range").classList.toggle("hidden", m !== "range");
}

function getHoursGeneratePayload() {
  if (state.hoursMode === "range") {
    const hoursMin = parseFloat($("hours-min").value);
    const hoursMax = parseFloat($("hours-max").value);
    if (Number.isNaN(hoursMin) || Number.isNaN(hoursMax)) {
      throw new Error("Enter valid min and max work hours.");
    }
    if (hoursMin > hoursMax) {
      throw new Error("Min hours cannot be greater than max hours.");
    }
    return {
      hours_mode: "range",
      hours_min: hoursMin,
      hours_max: hoursMax,
      hours_constant: hoursMin,
    };
  }
  const hoursConstant = parseFloat($("hours-constant").value);
  if (Number.isNaN(hoursConstant)) {
    throw new Error("Enter valid work hours.");
  }
  return {
    hours_mode: "constant",
    hours_constant: hoursConstant,
    hours_min: hoursConstant,
    hours_max: hoursConstant,
  };
}

function initHoursModeTabs() {
  document.querySelectorAll("#hours-mode-tabs .segmented-item").forEach((tab) => {
    tab.addEventListener("click", () => setHoursMode(tab.dataset.hoursMode));
  });
  setHoursMode("constant");
}

function initTabs() {
  document.querySelectorAll(".segmented-item[data-mode]").forEach((tab) => {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
  });
  setMode("calendar");
}

function initCalModeToggle() {
  const sw = $("cal-mode-switch");
  if (!sw) return;
  sw.addEventListener("change", () => {
    setCalMode(sw.checked ? "edit" : "pick");
  });
  syncCalModeToggleUi();
}

function initRangeInputs() {
  ["range-from", "range-till"].forEach((id) => {
    $(id).addEventListener("change", scheduleRangeResolve);
  });
  document.querySelectorAll(".skip-wd").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (state.mode === "range") scheduleRangeResolve();
    });
  });
}

function openDrawer() {
  const overlay = $("settings-modal");
  overlay.classList.add("open");
  overlay.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeDrawer() {
  const overlay = $("settings-modal");
  overlay.classList.remove("open");
  overlay.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function initSettingsModal() {
  $("btn-quit").addEventListener("click", async () => {
    if (confirm("Are you sure you want to quit VTU AIDS? This will close the application completely.")) {
      try {
        await fetch("/api/shutdown", { method: "POST" });
      } catch (e) {} // Ignore network error from server shutting down
      window.close();
      document.body.innerHTML = "<div style='display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;'><h1>VTU AIDS has been closed. You can safely close this tab.</h1></div>";
    }
  });

  $("btn-settings").addEventListener("click", () => {
    openDrawer();
    loadConfig();
  });
  $("btn-close-settings").addEventListener("click", closeDrawer);
  $("btn-save-settings").addEventListener("click", async () => {
    const btn = $("btn-save-settings");
    setLoading(btn, true);
    try {
      await saveConfig();
      closeDrawer();
      showStatus("Settings saved.", "ok");
    } catch (e) {
      showStatus(e.message, "error");
    } finally {
      setLoading(btn, false);
    }
  });
  $("settings-modal").addEventListener("click", (e) => {
    if (e.target === $("settings-modal")) closeDrawer();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("settings-modal").classList.contains("open")) closeDrawer();
  });
}

function initCalendarNav() {
  $("cal-prev").addEventListener("click", () => {
    state.calendarMonth -= 1;
    if (state.calendarMonth < 0) {
      state.calendarMonth = 11;
      state.calendarYear -= 1;
    }
    renderCalendar();
  });
  $("cal-next").addEventListener("click", () => {
    state.calendarMonth += 1;
    if (state.calendarMonth > 11) {
      state.calendarMonth = 0;
      state.calendarYear += 1;
    }
    renderCalendar();
  });
}

function showInitError(err) {
  const msg = err && err.message ? err.message : String(err);
  try {
    showStatus(`UI failed to start: ${msg}`, "error");
  } catch {
    /* showStatus not ready */
  }
  const banner = document.getElementById("js-load-error");
  if (banner) {
    banner.hidden = false;
    banner.style.display = "flex";
  }
  console.error("VTU AIDS init failed:", err);
}

function init() {
  try {
    initTabs();
    initCalModeToggle();
    initDocumentUpload();
    initHoursModeTabs();
    initRangeInputs();
    initDateInputLimits();
    initSettingsModal();
    initCalendarNav();
    renderCalendar();
  } catch (err) {
    showInitError(err);
    return;
  }
  renderDateChips([]);
  state.generatedEntries = [];
  state.activeEditDate = null;
  state.activeEditIsNew = false;
  $("entry-editor").classList.add("hidden");
  renderPreview([]);
  setPostGenerateEnabled(false);
  updateCalHint();
  refreshSection3View();

  $("btn-save-entry").addEventListener("click", async () => {
    try {
      await saveCurrentEntry();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-revert-entry").addEventListener("click", async () => {
    try {
      await revertCurrentEntry();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-fill-ai").addEventListener("click", async () => {
    try {
      await fillEntryWithAI();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-add-back-entry")?.addEventListener("click", () => {
    void addBackEntryWithAI();
  });

  $("btn-delete-entry").addEventListener("click", async () => {
    try {
      await deleteCurrentEntry();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-resolve-range").addEventListener("click", async () => {
    try {
      clearStatus();
      const n = (await resolveRangeDates()).length;
      showStatus(`Range applied: ${n} dates highlighted on calendar.`, "ok");
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-generate").addEventListener("click", async () => {
    try {
      await generateEntries();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  $("btn-download").addEventListener("click", () => {
    if (!state.hasGenerated) return;
    window.location.href = "/api/entries/download-excel";
  });

  $("btn-run").addEventListener("click", async () => {
    if (!state.hasGenerated) return;
    try {
      await runBot();
    } catch (e) {
      showStatus(e.message, "error");
    }
  });

  loadConfig().catch((e) => showStatus(e.message, "error"));
  void loadPersistedEntries();
  void checkDependencies();
}

async function checkDependencies() {
  try {
    const data = await fetch("/api/status").then((r) => r.json());
    if (data.dependencies?.google_genai) return;
    const msg =
      data.message ||
      "google-genai is not installed. Run Install VTU AIDS.bat or: pip install -r requirements.txt";
    showStatus(msg, "error");
    const genBtn = $("btn-generate");
    const fillBtn = $("btn-fill-ai");
    if (genBtn) genBtn.disabled = true;
    if (fillBtn) fillBtn.disabled = true;
  } catch {
    /* server not ready */
  }
}

document.addEventListener("DOMContentLoaded", init);
