const state = {
  receipts: [],
  categories: [],
  month: "",
  category: "",
  q: "",
  editing: null,
};

const els = {
  drop: document.getElementById("drop"),
  file: document.getElementById("file"),
  browse: document.getElementById("browse"),
  paste: document.getElementById("paste"),
  pasteSend: document.getElementById("paste-send"),
  q: document.getElementById("q"),
  month: document.getElementById("month"),
  category: document.getElementById("category"),
  export: document.getElementById("export"),
  summary: document.getElementById("summary"),
  rows: document.getElementById("rows"),
  empty: document.getElementById("empty"),
  count: document.getElementById("count-note"),
  status: document.getElementById("status"),
  queue: document.getElementById("queue"),
  editor: document.getElementById("editor"),
  editorForm: document.getElementById("editor-form"),
  editorCancel: document.getElementById("editor-cancel"),
};

const money = (amount, code) => {
  if (amount === null || amount === undefined) return "—";
  const currency = code || "USD";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
};

const prettyDate = (value) => {
  if (!value) return "No date";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsed);
};

const titleCase = (value) =>
  (value || "other").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const params = () => {
  const query = new URLSearchParams();
  if (state.month) query.set("month", state.month);
  if (state.category) query.set("category", state.category);
  if (state.q) query.set("q", state.q);
  return query;
};

async function load() {
  try {
    const response = await fetch(`/api/receipts?${params()}`);
    if (!response.ok) throw new Error("Could not load the ledger.");
    const data = await response.json();
    state.receipts = data.receipts;
    renderSummary(data.summary);
    renderRows();
  } catch (error) {
    note(error.message, "error");
  }
}

async function boot() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    state.categories = health.categories;
    fillCategoryOptions(els.category, true);
    const ready = health.model && health.model.ready;
    els.status.textContent = ready
      ? "Gemma 3 1B ready · local"
      : "Fallback parser · add a model for Gemma";
    els.status.classList.add(ready ? "ready" : "off");
    if (!ready) {
      note(
        "No local model found. Entries are parsed with a conservative fallback parser; run `make models` to let Gemma read them.",
        "hint",
      );
    }
  } catch {
    els.status.textContent = "offline";
  }
  await load();
}

function fillCategoryOptions(select, withAll, selected) {
  select.innerHTML = "";
  if (withAll) {
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "All";
    select.append(all);
  }
  for (const category of state.categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = titleCase(category);
    if (category === selected) option.selected = true;
    select.append(option);
  }
}

function renderSummary(summary) {
  els.summary.innerHTML = "";
  const buckets = summary && summary.currencies.length ? summary.currencies : [];
  if (!buckets.length) {
    els.summary.append(card("Nothing logged", "0.00", "0 receipts", ""));
  }
  for (const bucket of buckets) {
    const top = Object.entries(bucket.by_category).sort((a, b) => b[1] - a[1])[0];
    const meta = top
      ? `${bucket.count} receipt${bucket.count === 1 ? "" : "s"} · mostly ${titleCase(top[0])}`
      : `${bucket.count} receipt${bucket.count === 1 ? "" : "s"}`;
    els.summary.append(card(`Logged in ${bucket.currency}`, money(bucket.total, bucket.currency), meta, bucket.currency));
  }
  if (summary && summary.unpriced) {
    els.summary.append(
      card("Needs a total", String(summary.unpriced), "correct these by hand", "")
    );
  }
}

function card(label, value, meta, currency) {
  const element = document.createElement("div");
  element.className = "card";
  const eyebrow = document.createElement("div");
  eyebrow.className = "label";
  eyebrow.textContent = label;
  const big = document.createElement("div");
  big.className = "value";
  big.textContent = currency ? value : value;
  const small = document.createElement("div");
  small.className = "meta";
  small.textContent = meta;
  element.append(eyebrow, big, small);
  return element;
}

function renderRows() {
  els.rows.innerHTML = "";
  els.empty.classList.toggle("hidden", state.receipts.length > 0);
  els.count.textContent = state.receipts.length
    ? `${state.receipts.length} entr${state.receipts.length === 1 ? "y" : "ies"}`
    : "";

  for (const record of state.receipts) {
    const row = document.createElement("tr");

    const date = document.createElement("td");
    date.textContent = prettyDate(record.date);
    if (!record.date) date.style.color = "var(--muted)";

    const vendor = document.createElement("td");
    vendor.textContent = record.vendor || "Unknown vendor";

    const categoryCell = document.createElement("td");
    const categorySelect = document.createElement("select");
    fillCategoryOptions(categorySelect, false, record.category);
    categorySelect.addEventListener("change", async () => {
      await patch(record.id, { category: categorySelect.value });
      await load();
    });
    categoryCell.append(categorySelect);

    const total = document.createElement("td");
    total.className = "num";
    total.textContent = money(record.total, record.currency);

    const reader = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = record.extracted_by === "gemma-3-1b-it" ? "badge" : "badge fallback";
    badge.textContent =
      record.extracted_by === "gemma-3-1b-it" ? "Gemma" : "Parser";
    reader.append(badge);

    const actions = document.createElement("td");
    const wrap = document.createElement("div");
    wrap.className = "row-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "icon-btn";
    edit.textContent = "Fix";
    edit.addEventListener("click", () => openEditor(record));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon-btn danger";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => destroy(record));
    wrap.append(edit, remove);
    actions.append(wrap);

    row.append(date, vendor, categoryCell, total, reader, actions);
    els.rows.append(row);
  }
}

async function patch(id, changes) {
  const response = await fetch(`/api/receipts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    note(detail.detail || "Could not save that correction.", "error");
    return false;
  }
  return true;
}

async function destroy(record) {
  if (!confirm(`Delete the entry from ${record.vendor || "this receipt"}?`)) return;
  const response = await fetch(`/api/receipts/${record.id}`, { method: "DELETE" });
  if (!response.ok) {
    note("Could not delete that entry.", "error");
    return;
  }
  await load();
}

function openEditor(record) {
  state.editing = record;
  const form = els.editorForm;
  form.vendor.value = record.vendor || "";
  form.date.value = record.date || "";
  form.total.value = record.total ?? "";
  form.tax.value = record.tax ?? "";
  form.currency.value = record.currency || "";
  form.invoice_number.value = record.invoice_number || "";
  form.payment_method.value = record.payment_method || "";
  form.notes.value = record.notes || "";
  fillCategoryOptions(form.category, false, record.category);
  els.editor.showModal();
}

els.editorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.editing) return;
  const form = els.editorForm;
  const changes = {
    vendor: form.vendor.value,
    date: form.date.value || null,
    total: form.total.value === "" ? null : Number(form.total.value),
    tax: form.tax.value === "" ? null : Number(form.tax.value),
    currency: form.currency.value.toUpperCase(),
    category: form.category.value,
    payment_method: form.payment_method.value,
    invoice_number: form.invoice_number.value,
    notes: form.notes.value,
  };
  const saved = await patch(state.editing.id, changes);
  if (saved) {
    els.editor.close();
    state.editing = null;
    await load();
  }
});

els.editorCancel.addEventListener("click", () => {
  els.editor.close();
  state.editing = null;
});

async function upload(files) {
  for (const file of files) {
    const entry = note(`${file.name} · reading`, "hint", true);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch("/api/ingest", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) {
        entry.className = "error";
        entry.textContent = `${file.name} · ${data.detail || "could not read that file"}`;
        continue;
      }
      const receipt = data.receipt;
      entry.textContent = data.duplicate
        ? `${file.name} · already sorted`
        : `${file.name} · ${receipt.vendor} · ${money(receipt.total, receipt.currency)}`;
      if (receipt.total === null) {
        entry.textContent += " · needs a total, hit Fix";
        entry.classList.add("hint");
      }
      setTimeout(() => entry.remove(), 6000);
      await load();
    } catch {
      entry.className = "error";
      entry.textContent = `${file.name} · upload failed, is the server running?`;
    }
  }
}

function note(message, kind = "info", keep = false) {
  const item = document.createElement("li");
  item.textContent = message;
  if (kind === "error") item.className = "error";
  if (kind === "hint") item.classList.add("hint");
  els.queue.append(item);
  if (!keep) setTimeout(() => item.remove(), 6000);
  return item;
}

els.browse.addEventListener("click", () => els.file.click());
els.file.addEventListener("change", () => {
  upload([...els.file.files]);
  els.file.value = "";
});

["dragenter", "dragover"].forEach((eventName) =>
  els.drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.drop.classList.add("hot");
  })
);

["dragleave", "drop"].forEach((eventName) =>
  els.drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.drop.classList.remove("hot");
  })
);

els.drop.addEventListener("drop", (event) => {
  const files = [...(event.dataTransfer?.files || [])];
  if (files.length) upload(files);
});

els.pasteSend.addEventListener("click", async () => {
  const text = els.paste.value.trim();
  if (text.length < 12) {
    note("Paste a little more of the receipt first.", "hint");
    return;
  }
  const response = await fetch("/api/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await response.json();
  if (!response.ok) {
    note(data.detail || "Could not sort that text.", "error");
    return;
  }
  els.paste.value = "";
  note(`${data.receipt.vendor} · ${money(data.receipt.total, data.receipt.currency)}`);
  await load();
});

let timer;
els.q.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    state.q = els.q.value.trim();
    load();
  }, 220);
});

els.month.addEventListener("change", () => {
  state.month = els.month.value;
  updateExport();
  load();
});

els.category.addEventListener("change", () => {
  state.category = els.category.value;
  load();
});

function updateExport() {
  const query = state.month ? `?month=${encodeURIComponent(state.month)}` : "";
  els.export.href = `/api/export.csv${query}`;
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

boot();
