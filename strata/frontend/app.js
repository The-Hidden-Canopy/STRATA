const dates = [
  { label: "1880", detail: "01 Jan 1880", value: "1880-01-01", year: 1880 },
  { label: "1920", detail: "01 Jan 1920", value: "1920-01-01", year: 1920 },
  { label: "1970", detail: "01 Jan 1970", value: "1970-01-01", year: 1970 },
  { label: "Today", detail: "28 Sep 2026", value: "2026-09-28", year: 2026 },
];

const sources = [
  {
    id: "source-photo-1920",
    icon: "PH",
    title: "Main Street photograph, 1920",
    type: "PHOTO",
    time: "1920",
    role: "South facade / window count",
    confidence: 0.94,
  },
  {
    id: "source-permit-1911",
    icon: "PR",
    title: "Remodel permit 882",
    type: "RECORD",
    time: "1911",
    role: "Floor count and annex",
    confidence: 0.88,
  },
  {
    id: "source-map-1880",
    icon: "MP",
    title: "Sanborn district map",
    type: "MAP",
    time: "1880",
    role: "Parcel footprint",
    confidence: 0.91,
  },
  {
    id: "source-survey-2026",
    icon: "SV",
    title: "Current condition survey",
    type: "SURVEY",
    time: "2026",
    role: "Existing curb and facade",
    confidence: 0.98,
  },
  {
    id: "source-inference-branch",
    icon: "NT",
    title: "Fire damage hypothesis note",
    type: "NOTE",
    time: "1948",
    role: "Competing branch only",
    confidence: 0.63,
  },
];

const entities = [
  {
    id: "ent_building_031",
    name: "Old Hotel",
    type: "Building",
    className: "documented",
    description: "Three-storey commercial building",
    confidence: 0.92,
    evidence: ["source-photo-1920", "source-permit-1911", "source-map-1880"],
    geometry: {
      1880: { x: 250, y: 188, w: 196, h: 124 },
      1920: { x: 260, y: 178, w: 214, h: 135 },
      1970: { x: 260, y: 168, w: 214, h: 145 },
      2026: { x: 260, y: 160, w: 214, h: 153 },
    },
    properties: {
      1880: [["Floors", "2"], ["Use", "Lodging"], ["Status", "Documented"]],
      1920: [["Floors", "3"], ["Use", "Hotel"], ["Status", "Documented"]],
      1970: [["Floors", "3"], ["Use", "Hotel"], ["Status", "Documented"]],
      2026: [["Floors", "3"], ["Use", "Mixed commercial"], ["Status", "Observed"]],
    },
  },
  {
    id: "ent_annex_044",
    name: "North Annex",
    type: "Building",
    className: "inferred",
    description: "Rear wing inferred from permit geometry",
    confidence: 0.77,
    evidence: ["source-permit-1911", "source-photo-1920"],
    geometry: {
      1880: null,
      1920: { x: 484, y: 206, w: 126, h: 95 },
      1970: { x: 484, y: 198, w: 142, h: 105 },
      2026: { x: 484, y: 190, w: 154, h: 112 },
    },
    properties: {
      1920: [["Floors", "2"], ["Use", "Service wing"], ["Status", "Inferred"]],
      1970: [["Floors", "2"], ["Use", "Storage"], ["Status", "Inferred"]],
      2026: [["Floors", "2"], ["Use", "Workshop"], ["Status", "Observed"]],
    },
  },
  {
    id: "ent_stable_012",
    name: "Carriage Stable",
    type: "Building",
    className: "observed",
    description: "Small outbuilding behind the original parcel",
    confidence: 0.84,
    evidence: ["source-map-1880", "source-photo-1920"],
    geometry: {
      1880: { x: 640, y: 335, w: 112, h: 82 },
      1920: { x: 650, y: 330, w: 105, h: 76 },
      1970: null,
      2026: null,
    },
    properties: {
      1880: [["Floors", "1"], ["Use", "Stable"], ["Status", "Observed"]],
      1920: [["Floors", "1"], ["Use", "Garage"], ["Status", "Observed"]],
    },
  },
  {
    id: "ent_street_001",
    name: "Main Street",
    type: "Street",
    className: "observed",
    description: "Primary street edge and curb line",
    confidence: 0.98,
    evidence: ["source-map-1880", "source-survey-2026"],
    geometry: { 1880: { x: 0, y: 90, w: 900, h: 72 }, 1920: { x: 0, y: 90, w: 900, h: 72 }, 1970: { x: 0, y: 90, w: 900, h: 72 }, 2026: { x: 0, y: 90, w: 900, h: 72 } },
    properties: {
      1880: [["Surface", "Unpaved"], ["Use", "Main Street"], ["Status", "Observed"]],
      1920: [["Surface", "Paved"], ["Use", "Main Street"], ["Status", "Observed"]],
      1970: [["Surface", "Paved"], ["Use", "Main Street"], ["Status", "Observed"]],
      2026: [["Surface", "Paved"], ["Use", "Main Street"], ["Status", "Observed"]],
    },
  },
  {
    id: "ent_future_001",
    name: "Speculative Tower",
    type: "Building",
    className: "speculative",
    description: "Unresolved massing in the fire damage hypothesis",
    confidence: 0.41,
    evidence: ["source-inference-branch"],
    geometry: { 1880: null, 1920: null, 1970: null, 2026: { x: 690, y: 190, w: 95, h: 150 } },
    properties: { 2026: [["Floors", "5"], ["Use", "Unresolved"], ["Status", "Speculative"]] },
  },
];

const appState = {
  dateIndex: 1,
  branch: "main",
  selectedId: "ent_building_031",
  inspectorTab: "inspector",
  nav: "overview",
  mode: "topdown",
  zoom: 1,
  layers: { buildings: true, streets: true, parcels: true, evidence: true },
  branches: [
    { id: "main", name: "main", status: "ACTIVE", description: "Canonical reconstruction", changes: 0 },
    { id: "hypothesis-fire", name: "hypothesis-fire", status: "DRAFT", description: "Alternate 1948 fire damage sequence", changes: 4 },
  ],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
}[character]));

function currentDate() {
  return dates[appState.dateIndex];
}

function selectedEntity() {
  return entities.find((entity) => entity.id === appState.selectedId) || entities[0];
}

function visibleEntities() {
  const year = currentDate().year;
  return entities.filter((entity) => {
    if (entity.id === "ent_future_001") return appState.branch === "hypothesis-fire" && year >= 2026;
    return Boolean(entity.geometry[year]);
  });
}

function selectedGeometry(entity) {
  return entity.geometry[currentDate().year];
}

function entityClass(entity) {
  if (appState.branch === "hypothesis-fire" && entity.id === "ent_building_031" && currentDate().year >= 1970) return "speculative";
  return entity.className;
}

function showToast(message, tone = "") {
  const toast = $("#toast");
  toast.className = `toast ${tone}`;
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => { toast.hidden = true; }, 3600);
}

function renderTimeline() {
  const events = [
    { year: 1880, label: "Original footprint", tone: "teal" },
    { year: 1911, label: "Annex permit", tone: "rust" },
    { year: 1920, label: "South facade photo", tone: "amber" },
    { year: 1948, label: "Fire hypothesis", tone: "violet" },
    { year: 2026, label: "Current survey", tone: "teal" },
  ];
  const eventMarkup = events.map((event) => {
    const left = ((event.year - 1880) / (2026 - 1880)) * 100;
    return `<button class="timeline-event ${event.tone}" style="left:${left}%" data-year="${event.year}" title="${escapeHtml(event.label)}"><span class="event-dot"></span><span class="event-label">${escapeHtml(event.label)}</span><span class="event-year">${event.year}</span></button>`;
  }).join("");
  $("#timeline-events").innerHTML = eventMarkup;
  $$(".timeline-event").forEach((button) => button.addEventListener("click", () => {
    const year = Number(button.dataset.year);
    const nearest = dates.reduce((best, date, index) => Math.abs(date.year - year) < Math.abs(dates[best].year - year) ? index : best, 0);
    appState.dateIndex = nearest;
    updateApp();
  }));
}

function renderScene() {
  const year = currentDate().year;
  const selected = appState.selectedId;
  const scene = $("#scene-svg");
  const visible = visibleEntities();
  const grid = Array.from({ length: 20 }, (_, index) => `<line x1="${index * 48}" y1="0" x2="${index * 48}" y2="540"></line>`).join("") + Array.from({ length: 12 }, (_, index) => `<line x1="0" y1="${index * 48}" x2="900" y2="${index * 48}"></line>`).join("");
  const parcels = appState.layers.parcels ? `<g class="scene-parcels"><path d="M95 185H835V465H95Z"></path><path d="M220 178V470M474 175V470M640 175V470M95 320H835"></path></g>` : "";
  const streets = appState.layers.streets ? `<g class="scene-street"><rect x="0" y="90" width="900" height="72"></rect><path d="M0 153H900"></path><text x="30" y="130">MAIN STREET</text></g>` : "";
  const buildings = appState.layers.buildings ? visible.filter((entity) => entity.type === "Building").map((entity) => {
    const geometry = selectedGeometry(entity);
    if (!geometry) return "";
    const isSelected = entity.id === selected;
    const className = entityClass(entity);
    const fill = className === "inferred" ? "#d9e6e5" : className === "speculative" ? "#e8d9ee" : className === "observed" ? "#e5e9eb" : "#f3e2c4";
    const roof = className === "speculative" ? "#88629a" : className === "inferred" ? "#3c7d7b" : className === "observed" ? "#596c7a" : "#a24f36";
    const windows = Array.from({ length: Math.max(2, Math.floor(geometry.w / 42)) }, (_, index) => {
      const x = geometry.x + 20 + index * ((geometry.w - 40) / Math.max(1, Math.floor(geometry.w / 42) - 1));
      return `<rect class="scene-window" x="${x - 5}" y="${geometry.y + 35}" width="10" height="15"></rect><rect class="scene-window" x="${x - 5}" y="${geometry.y + 70}" width="10" height="15"></rect>`;
    }).join("");
    return `<g class="scene-entity ${className} ${isSelected ? "selected" : ""}" data-entity-id="${entity.id}" tabindex="0" role="button" aria-label="${escapeHtml(entity.name)}"><rect class="building-body" x="${geometry.x}" y="${geometry.y}" width="${geometry.w}" height="${geometry.h}" rx="2" fill="${fill}"></rect><rect class="building-roof" x="${geometry.x}" y="${geometry.y}" width="${geometry.w}" height="12" fill="${roof}"></rect>${windows}<text class="building-label" x="${geometry.x + 12}" y="${geometry.y + geometry.h - 14}">${escapeHtml(entity.name)}</text><circle class="entity-pin" cx="${geometry.x + geometry.w - 14}" cy="${geometry.y + 18}" r="5"></circle></g>`;
  }).join("") : "";
  const evidence = appState.layers.evidence ? visible.filter((entity) => entity.type === "Building").map((entity, index) => {
    const geometry = selectedGeometry(entity);
    if (!geometry) return "";
    const source = sources.find((item) => item.id === entity.evidence[0]);
    return `<g class="evidence-anchor ${entity.id === selected ? "selected" : ""}" data-entity-id="${entity.id}"><line x1="${geometry.x + geometry.w / 2}" y1="${geometry.y - 4}" x2="${geometry.x + geometry.w / 2}" y2="${geometry.y - 24 - index * 5}"></line><circle cx="${geometry.x + geometry.w / 2}" cy="${geometry.y - 30 - index * 5}" r="10"></circle><text x="${geometry.x + geometry.w / 2}" y="${geometry.y - 27 - index * 5}">${escapeHtml(source ? source.icon : "EV")}</text></g>`;
  }).join("") : "";
  scene.innerHTML = `<rect class="scene-bg" width="900" height="540" rx="4"></rect><g class="scene-grid">${grid}</g>${parcels}${streets}<g class="scene-buildings">${buildings}</g><g class="scene-evidence">${evidence}</g><g class="north-arrow"><path d="M820 460L820 405M820 405L812 420M820 405L828 420"></path><text x="814" y="480">N</text></g><text class="scene-date" x="36" y="505">${year} / ${appState.branch.toUpperCase()}</text>`;
  scene.style.transform = `scale(${appState.zoom})`;
  $$("[data-entity-id]", scene).forEach((node) => {
    node.addEventListener("click", () => {
      appState.selectedId = node.dataset.entityId;
      appState.inspectorTab = "inspector";
      updateApp();
    });
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        appState.selectedId = node.dataset.entityId;
        updateApp();
      }
    });
  });
}

function confidenceBar(value) {
  return `<span class="confidence-bar"><span style="width:${Math.round(value * 100)}%"></span></span><strong>${Math.round(value * 100)}%</strong>`;
}

function renderInspector() {
  const entity = selectedEntity();
  const props = entity.properties[currentDate().year] || entity.properties[Object.keys(entity.properties)[0]] || [];
  const traces = [
    ["SOURCE", sources.find((source) => source.id === entity.evidence[0])?.title || "Local source"],
    ["OBSERVATION", `${entity.name} geometry at ${currentDate().year}`],
    ["ASSERTION", `${entity.type} exists in the selected state`],
    ["DECISION", appState.branch === "main" ? "Accepted into main" : "Pending branch review"],
    ["COMPILED", "Scene graph / glTF export"],
  ];
  const inspectorContent = appState.inspectorTab === "inspector" ? `
    <div class="entity-heading"><div class="entity-mark ${entityClass(entity)}">${escapeHtml(entity.name.slice(0, 2).toUpperCase())}</div><div><h2>${escapeHtml(entity.name)}</h2><p>${escapeHtml(entity.description)}</p></div></div>
    <div class="confidence-summary"><span>Confidence</span><span class="confidence-value">${confidenceBar(entity.confidence)}</span></div>
    <div class="property-table">${props.map(([key, value]) => `<div class="property-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>
    <div class="trace-block"><div class="section-kicker">PROVENANCE TRACE</div>${traces.map(([label, value], index) => `<div class="trace-row"><span class="trace-node ${index === traces.length - 1 ? "final" : ""}"></span><div><small>${label}</small><strong>${escapeHtml(value)}</strong></div></div>`).join("")}</div>
  ` : appState.inspectorTab === "evidence" ? `
    <div class="panel-subhead"><div><span class="section-kicker">LINKED EVIDENCE</span><h2>${escapeHtml(entity.name)}</h2></div><span class="count-badge">${entity.evidence.length}</span></div>
    <div class="linked-evidence">${entity.evidence.map((sourceId) => { const source = sources.find((item) => item.id === sourceId); return source ? `<article class="linked-item"><span class="source-icon">${source.icon}</span><div><strong>${escapeHtml(source.title)}</strong><span>${source.type} / ${source.time}</span></div><b>${Math.round(source.confidence * 100)}%</b></article>` : ""; }).join("")}</div>
    <div class="uncertainty-note"><span class="note-icon">!</span><p>This selection has ${entity.className === "inferred" ? "inferred geometry. Review the linked permit before publishing." : "a traceable evidence chain ready for export."}</p></div>
  ` : `
    <div class="panel-subhead"><div><span class="section-kicker">CHANGE LOG</span><h2>${escapeHtml(entity.name)}</h2></div></div>
    <div class="change-list"><div class="change-item"><span>1880</span><p>Original footprint recorded from district map.</p></div><div class="change-item"><span>1911</span><p>North annex enters the reconstruction through a permit assertion.</p></div><div class="change-item"><span>2026</span><p>Current survey confirms street edge and facade condition.</p></div></div>
  `;
  $("#inspector-content").innerHTML = inspectorContent;
  $$(".inspector-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === appState.inspectorTab);
    tab.classList.toggle("is-active", tab.dataset.tab === appState.inspectorTab);
  });
}

function renderEvidenceTable() {
  $("#evidence-list").innerHTML = sources.map((source) => `<tr><td><div class="source-cell"><span class="source-icon">${source.icon}</span><strong>${escapeHtml(source.title)}</strong></div></td><td><span class="type-label">${source.type}</span></td><td>${source.time}</td><td>${escapeHtml(source.role)}</td><td><div class="table-confidence"><span style="width:${Math.round(source.confidence * 100)}%"></span></div><strong>${Math.round(source.confidence * 100)}%</strong></td></tr>`).join("");
}

function renderEntityIndex() {
  const items = entities.filter((entity) => entity.type === "Building").map((entity) => `<button class="index-row ${entity.id === appState.selectedId ? "active" : ""}" data-entity-id="${entity.id}"><span class="entity-mark ${entity.className}">${escapeHtml(entity.name.slice(0, 2).toUpperCase())}</span><span><strong>${escapeHtml(entity.name)}</strong><small>${escapeHtml(entity.type)} / ${Math.round(entity.confidence * 100)}% confidence</small></span><span class="row-arrow">›</span></button>`).join("");
  $("#entity-grid").innerHTML = items;
  $$("#entity-grid .index-row").forEach((row) => row.addEventListener("click", () => { appState.selectedId = row.dataset.entityId; appState.nav = "overview"; updateApp(); }));
}

function renderBranchIndex() {
  $("#branch-list").innerHTML = appState.branches.map((branch) => `<button class="branch-card ${branch.id === appState.branch ? "active" : ""}" data-branch-id="${branch.id}"><span class="branch-symbol">${branch.id === "main" ? "M" : "B"}</span><span><strong>${escapeHtml(branch.name)}</strong><small>${escapeHtml(branch.description)}</small></span><span class="branch-status ${branch.status.toLowerCase()}">${branch.status}</span></button>`).join("");
  $$("#branch-list .branch-card").forEach((card) => card.addEventListener("click", () => { appState.branch = card.dataset.branchId; updateApp(); showToast(`Viewing ${appState.branch}`); }));
}

function updateHeader() {
  const date = currentDate();
  $("#time-label").textContent = date.year;
  $("#time-detail").textContent = date.detail;
  $("#time-slider").value = appState.dateIndex;
  $("#timeline-progress").style.width = `${(appState.dateIndex / (dates.length - 1)) * 100}%`;
  document.documentElement.style.setProperty("--timeline-position", `${(appState.dateIndex / (dates.length - 1)) * 100}%`);
  $("#branch-select").value = appState.branch;
  $("#scene-title").textContent = `${date.year} / ${appState.branch}`;
  $("#entity-count").textContent = visibleEntities().length;
}

function updateNavigation() {
  $$(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === appState.nav);
    item.classList.toggle("is-active", item.dataset.view === appState.nav);
  });
  const showWorkspace = appState.nav === "overview" || appState.nav === "timeline";
  $("#overview-view").hidden = !showWorkspace;
  $("#evidence-view").hidden = appState.nav !== "evidence";
  $("#entities-view").hidden = appState.nav !== "entities";
  $("#branches-view").hidden = appState.nav !== "branches";
  $("#exports-view").hidden = appState.nav !== "exports";
  if (appState.nav === "timeline") window.setTimeout(() => $("#timeline-band").scrollIntoView({ behavior: "smooth", block: "center" }), 0);
}

function updateApp() {
  updateHeader();
  renderTimeline();
  renderScene();
  renderInspector();
  renderEvidenceTable();
  renderEntityIndex();
  renderBranchIndex();
  updateNavigation();
  $$("[data-layer]").forEach((control) => { control.checked = appState.layers[control.dataset.layer]; });
}

function addBranch(name) {
  const id = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `branch-${Date.now()}`;
  if (appState.branches.some((branch) => branch.id === id)) {
    showToast("A branch with that name already exists", "error");
    return;
  }
  appState.branches.push({ id, name: id, status: "DRAFT", description: "New working hypothesis", changes: 0 });
  appState.branch = id;
  $("#branch-dialog").close();
  updateApp();
  showToast(`Created ${id}`);
}

async function checkApi() {
  try {
    const response = await fetch("/api/v1/project", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("API unavailable");
    $(".sync-status").innerHTML = `<span class="status-dot online"></span><span id="sync-label">Local project</span>`;
  } catch (_error) {
    $(".sync-status").innerHTML = `<span class="status-dot"></span><span id="sync-label">Demo data</span>`;
  }
}

function downloadScene() {
  const payload = {
    format: "strata-ui-export",
    generated_at: new Date().toISOString(),
    branch: appState.branch,
    time: currentDate().value,
    selected_entity: appState.selectedId,
    entities: visibleEntities().map((entity) => ({ id: entity.id, name: entity.name, type: entity.type, geometry: selectedGeometry(entity) })),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `strata-${appState.branch}-${currentDate().year}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("Scene export downloaded");
}

function init() {
  $("#time-slider").addEventListener("input", (event) => { appState.dateIndex = Number(event.target.value); updateApp(); });
  $("#branch-select").addEventListener("change", (event) => { appState.branch = event.target.value; updateApp(); });
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => { appState.nav = item.dataset.view; updateApp(); }));
  $$(".inspector-tab").forEach((tab) => tab.addEventListener("click", () => { appState.inspectorTab = tab.dataset.tab; renderInspector(); }));
  $$("[data-layer]").forEach((control) => control.addEventListener("change", () => { appState.layers[control.dataset.layer] = control.checked; renderScene(); }));
  $("[data-mode=topdown]").addEventListener("click", () => { appState.mode = "topdown"; $("[data-mode=topdown]").classList.add("active", "is-active"); $("[data-mode=perspective]").classList.remove("active", "is-active"); });
  $("[data-mode=perspective]").addEventListener("click", () => { appState.mode = "3d"; $("[data-mode=perspective]").classList.add("active", "is-active"); $("[data-mode=topdown]").classList.remove("active", "is-active"); showToast("3D preview is reserved for compiled scene exports", "info"); });
  $("#zoom-in").addEventListener("click", () => { appState.zoom = Math.min(1.35, appState.zoom + 0.1); renderScene(); });
  $("#zoom-out").addEventListener("click", () => { appState.zoom = Math.max(0.8, appState.zoom - 0.1); renderScene(); });
  $("#fit-scene").addEventListener("click", () => { appState.zoom = 1; renderScene(); });
  $$("#new-branch, #new-branch-secondary").forEach((button) => button.addEventListener("click", () => $("#branch-dialog").showModal()));
  $("#branch-form").addEventListener("submit", (event) => { event.preventDefault(); addBranch($("#branch-name").value); });
  $("#branch-dialog [value=cancel]").addEventListener("click", () => $("#branch-dialog").close());
  $("#import-button").addEventListener("click", () => showToast("Import a source with `strata import` to preserve its provenance", "info"));
  $("#create-entity").addEventListener("click", () => showToast("Entity creation is ready through the CLI and project API", "info"));
  $("#export-button").addEventListener("click", downloadScene);
  $("#export-secondary").addEventListener("click", downloadScene);
  $("#show-all-evidence").addEventListener("click", () => { appState.nav = "evidence"; updateApp(); });
  $("#reset-layers").addEventListener("click", () => { appState.layers = { buildings: true, streets: true, parcels: true, evidence: true }; updateApp(); showToast("Layers reset"); });
  updateApp();
  checkApi();
}

document.addEventListener("DOMContentLoaded", init);
