const promptInput = document.querySelector("#nl-prompt");
const generatedFlow = document.querySelector("#generated-flow");
const output = document.querySelector("#output");
const timeline = document.querySelector("#timeline");
const devicesEl = document.querySelector("#devices");
const routesEl = document.querySelector("#routes");
const routeFilter = document.querySelector("#route-filter");
const selectedCommand = document.querySelector("#selected-command");
const payloadForm = document.querySelector("#payload-form");
const runSelectedButton = document.querySelector("#run-selected-uri");
const runNlFlowButton = document.querySelector("#run-nl-flow");
const runNlFlowInlineButton = document.querySelector("#run-nl-flow-inline");
const refreshLogsButton = document.querySelector("#refresh-logs");
const novncGrid = document.querySelector("#novnc-grid");
const activityLog = document.querySelector("#activity-log");
const viewTabs = Array.from(document.querySelectorAll(".tab-button"));
const viewPanes = Array.from(document.querySelectorAll(".view-pane"));
const navigationButtons = Array.from(document.querySelectorAll("[data-focus]"));
const examplePrompt = "Sprawdź oba komputery, pokaż procesy, zapisz notatkę na dostępnym urządzeniu i pokaż ostatnie logi. Jeśli możesz, sprawdź czy jest python3.";

let latestMesh = { devices: [], routes: [], safeRoutes: [] };
let selectedRoute = null;
let latestLogGroups = [];
let localActivity = [];

function showJson(node, value) {
  node.textContent = JSON.stringify(value, null, 2);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[char]);
}

function focusTargetFor(name) {
  return {
    overview: "#overview",
    flow: "#flow-panel",
    uri: "#command-workbench",
    devices: "#devices",
    novnc: "#presentation-panel",
    logs: "#presentation-panel",
    results: "#presentation-panel",
  }[name] || "#overview";
}

function setMenuActive(name) {
  for (const button of navigationButtons) {
    button.classList.toggle("active", button.dataset.focus === name);
  }
}

function showView(name, syncMenu = true) {
  for (const tab of viewTabs) {
    tab.classList.toggle("active", tab.dataset.view === name);
  }
  for (const pane of viewPanes) {
    pane.classList.toggle("active", pane.id === `view-${name}`);
  }
  if (syncMenu) setMenuActive(name);
}

function focusArea(name) {
  if (["novnc", "logs", "results"].includes(name)) {
    showView(name);
  } else {
    setMenuActive(name);
  }

  const target = document.querySelector(focusTargetFor(name));
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function recordActivity(event, detail = {}) {
  localActivity.unshift({
    at: new Date().toLocaleTimeString(),
    event,
    detail,
  });
  localActivity = localActivity.slice(0, 20);
  renderActivityLog();
}

function targetFromUri(uri) {
  try {
    return new URL(uri).host;
  } catch {
    return String(uri).split("://")[1]?.split("/")[0] || "";
  }
}

function routeByUri(uri) {
  return latestMesh.routes.find((route) => route.uri === uri);
}

async function runUri(uri, payload = {}) {
  const response = await fetch("/api/run-uri", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri, payload }),
  });
  return response.json();
}

function isRouteSafe(route) {
  return route.safe === true || latestMesh.safeRoutes.some((item) => item.uri === route.uri);
}

function routeBadge(route) {
  const safe = isRouteSafe(route);
  return `<span class="badge ${safe ? "safe" : "locked"}">${safe ? "safe" : "locked"}</span>`;
}

function schemaFor(route) {
  return route?.inputSchema || route?.config?.inputSchema || { type: "object", properties: {} };
}

function requiredSet(schema) {
  return new Set(Array.isArray(schema.required) ? schema.required : []);
}

function defaultValueFor(name, field) {
  if (field && Object.prototype.hasOwnProperty.call(field, "default")) return field.default;
  const lower = name.toLowerCase();
  if (lower === "url") return "https://example.com/";
  if (lower === "binary") return "python3";
  if (lower === "text") return "Manual dashboard URI call";
  if (lower === "event") return "manual.dashboard.call";
  if (lower === "detail") return {};
  if (lower === "name") return "python";
  if (lower === "limit") return 8;
  if (field?.type === "boolean") return false;
  if (field?.type === "integer" || field?.type === "number") return "";
  if (field?.type === "array") return [];
  if (field?.type === "object") return {};
  return "";
}

function valueToInput(value, type) {
  if (type === "object" || type === "array") return JSON.stringify(value, null, 2);
  return value ?? "";
}

function renderDevices(mesh) {
  const reachable = mesh.devices.filter((item) => item.reachable).length;
  document.querySelector("#device-count").textContent = mesh.devices.length;
  document.querySelector("#reachable-count").textContent = reachable;
  document.querySelector("#route-count").textContent = mesh.routes.length;
  document.querySelector("#safe-route-count").textContent = mesh.safeRoutes.length;

  devicesEl.innerHTML = mesh.devices.map((item) => {
    const device = item.device || {};
    const processes = (item.processes || []).slice(0, 8).map((proc) => `
      <tr>
        <td>${proc.pid}</td>
        <td>${escapeHtml(proc.command)}</td>
        <td>${proc.cpu}</td>
        <td>${proc.mem}</td>
      </tr>
    `).join("");
    const installable = (item.installable || []).map((capability) => `
      <li>
        <strong>${escapeHtml(capability.capability)}</strong>
        <span>${escapeHtml(capability.installHint)}</span>
      </li>
    `).join("");
    return `
      <article class="device-card ${item.reachable ? "online" : "offline"}">
        <div class="device-head">
          <div>
            <strong>${escapeHtml(device.name || item.name)}</strong>
            <span>${escapeHtml(device.role || "unknown")} · ${escapeHtml(item.baseUrl)}</span>
          </div>
          <span class="status">${item.reachable ? "online" : "offline"}</span>
        </div>
        <dl>
          <div><dt>Host</dt><dd>${escapeHtml(device.hostname || "-")}</dd></div>
          <div><dt>Platform</dt><dd>${escapeHtml(device.platform || item.error || "-")}</dd></div>
          <div><dt>Routes</dt><dd>${device.routeCount || 0}</dd></div>
          <div><dt>Browser</dt><dd>${device.allowBrowser ? "<span class=\"badge safe\">enabled</span>" : "<span class=\"badge locked\">blocked</span>"}</dd></div>
        </dl>
        <h3>Processes</h3>
        <table>
          <thead><tr><th>PID</th><th>Command</th><th>CPU</th><th>MEM</th></tr></thead>
          <tbody>${processes || "<tr><td colspan=\"4\">No process data</td></tr>"}</tbody>
        </table>
        <h3>Installable URI adapters</h3>
        <ul class="installable">${installable || "<li><span>No install hints</span></li>"}</ul>
      </article>
    `;
  }).join("");
}

function novncEntryFor(deviceName, index) {
  const config = window.URI_RUN_NOVNC_CONFIG || {};
  const pcs = config.pcs || {};
  return pcs[deviceName] || pcs[`pc${index + 1}`] || {};
}

function novncUrlFor(deviceName, index) {
  const entry = novncEntryFor(deviceName, index);
  if (entry.novncUrl || entry.url) return entry.novncUrl || entry.url;
  if (!entry.novncPort) return "";
  const host = entry.host || window.URI_RUN_NOVNC_HOST || window.location.hostname || "127.0.0.1";
  const path = entry.path || "/vnc.html?autoconnect=1&resize=remote";
  return `http://${host}:${entry.novncPort}${path}`;
}

function renderNovnc(mesh) {
  const devices = mesh.devices.length ? mesh.devices : [
    { name: "desktop", reachable: false, device: { role: "controller" } },
    { name: "laptop", reachable: false, device: { role: "remote-laptop" } },
  ];

  novncGrid.innerHTML = devices.map((item, index) => {
    const device = item.device || {};
    const name = device.name || item.name || `pc${index + 1}`;
    const url = novncUrlFor(name, index);
    const status = item.reachable ? "online" : "offline";
    return `
      <article class="novnc-card">
        <div class="novnc-head">
          <div>
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(device.role || "device")} · ${status}</span>
          </div>
          ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">open</a>` : ""}
        </div>
        ${url
          ? `<iframe title="noVNC ${escapeHtml(name)}" src="${escapeHtml(url)}" loading="lazy"></iframe>`
          : `<div class="novnc-empty">
              <code>window.URI_RUN_NOVNC_CONFIG.pcs.${escapeHtml(name)}.novncUrl</code>
              <span>No noVNC URL configured for this device.</span>
            </div>`}
      </article>
    `;
  }).join("");
}

function renderRoutes() {
  const filter = routeFilter.value.trim().toLowerCase();
  const rows = latestMesh.routes
    .filter((route) => !filter || route.uri.toLowerCase().includes(filter) || String(route.title || "").toLowerCase().includes(filter))
    .sort((a, b) => a.uri.localeCompare(b.uri))
    .map((route) => `
      <button class="route-row ${selectedRoute?.uri === route.uri ? "active" : ""}" data-uri="${escapeHtml(route.uri)}" type="button">
        <code>${escapeHtml(route.uri)}</code>
        ${routeBadge(route)}
        <span>${escapeHtml(route.title || route.adapter || "")}</span>
      </button>
    `).join("");
  routesEl.innerHTML = rows || "<p class=\"muted\">No URI routes discovered.</p>";
}

function selectRoute(uri) {
  selectedRoute = latestMesh.routes.find((route) => route.uri === uri) || null;
  renderRoutes();
  renderPayloadForm();
  setMenuActive("uri");
  showJson(output, {
    selected: selectedRoute?.uri || null,
    payload: previewPayload(),
  });
}

function renderField(name, field, required) {
  const type = field?.type || "string";
  const value = defaultValueFor(name, field || {});
  const label = `${name}${required ? " *" : ""}`;
  const description = field?.description ? `<small>${escapeHtml(field.description)}</small>` : "";

  if (type === "boolean") {
    return `
      <label class="payload-field inline">
        <input name="${escapeHtml(name)}" type="checkbox" data-type="boolean" ${value ? "checked" : ""}>
        <span>${escapeHtml(label)}</span>
        ${description}
      </label>
    `;
  }

  if (type === "object" || type === "array") {
    return `
      <label class="payload-field">
        <span>${escapeHtml(label)}</span>
        <textarea name="${escapeHtml(name)}" data-type="${escapeHtml(type)}" rows="5">${escapeHtml(valueToInput(value, type))}</textarea>
        ${description}
      </label>
    `;
  }

  const inputType = type === "integer" || type === "number" ? "number" : "text";
  const step = type === "number" ? "any" : "1";
  return `
    <label class="payload-field">
      <span>${escapeHtml(label)}</span>
      <input name="${escapeHtml(name)}" type="${inputType}" step="${step}" value="${escapeHtml(valueToInput(value, type))}" data-type="${escapeHtml(type)}" ${required ? "required" : ""}>
      ${description}
    </label>
  `;
}

function renderPayloadForm() {
  runSelectedButton.disabled = !selectedRoute || !isRouteSafe(selectedRoute);
  payloadForm.innerHTML = "";

  if (!selectedRoute) {
    selectedCommand.className = "selected-command empty-state";
    selectedCommand.textContent = "Select a URI command to build its payload.";
    return;
  }

  const schema = schemaFor(selectedRoute);
  const properties = schema.properties || {};
  const required = requiredSet(schema);
  selectedCommand.className = "selected-command";
  selectedCommand.innerHTML = `
    <code>${escapeHtml(selectedRoute.uri)}</code>
    ${routeBadge(selectedRoute)}
    <p>${escapeHtml(selectedRoute.title || selectedRoute.adapter || "URI command")}</p>
  `;

  payloadForm.innerHTML = Object.keys(properties).length
    ? Object.entries(properties).map(([name, field]) => renderField(name, field, required.has(name))).join("")
    : "<p class=\"empty-state\">This URI has an empty payload schema. RUN will send <code>{}</code>.</p>";
}

function parsePayloadValue(input) {
  const type = input.dataset.type || "string";
  if (type === "boolean") return input.checked;
  if (input.value === "" && !input.required) return undefined;
  if (type === "integer") return Number.parseInt(input.value, 10);
  if (type === "number") return Number.parseFloat(input.value);
  if (type === "object" || type === "array") {
    const trimmed = input.value.trim();
    if (!trimmed && !input.required) return undefined;
    return JSON.parse(trimmed || (type === "array" ? "[]" : "{}"));
  }
  return input.value;
}

function payloadFromForm() {
  const payload = {};
  for (const input of payloadForm.querySelectorAll("input[name], textarea[name]")) {
    const value = parsePayloadValue(input);
    if (value !== undefined) payload[input.name] = value;
  }
  return payload;
}

function previewPayload() {
  if (!selectedRoute) return {};
  try {
    return payloadFromForm();
  } catch {
    return { error: "payload form contains invalid JSON" };
  }
}

function appendTimeline(item) {
  const li = document.createElement("li");
  li.innerHTML = `<code>${escapeHtml(item.uri)}</code> <span class="${item.ok ? "ok" : "fail"}">${item.ok ? "ok" : "failed"}</span>`;
  timeline.appendChild(li);
}

function extractRunResult(data) {
  const manual = data?.results?.manual;
  return manual?.response?.result || manual?.result || data?.result || {};
}

function renderActivityLog() {
  const frontendRows = localActivity.map((item) => `
    <article class="log-row frontend-log">
      <div>
        <strong>frontend</strong>
        <span>${escapeHtml(item.at)} · ${escapeHtml(item.event)}</span>
      </div>
      <code>${escapeHtml(JSON.stringify(item.detail))}</code>
    </article>
  `).join("");

  const deviceRows = latestLogGroups.flatMap((group) => (
    group.logs.map((entry) => `
      <article class="log-row">
        <div>
          <strong>${escapeHtml(entry.device || group.device)}</strong>
          <span>${escapeHtml(entry.at || "")} · ${escapeHtml(entry.event || "log")}</span>
        </div>
        <code>${escapeHtml(JSON.stringify(entry.detail || entry))}</code>
      </article>
    `)
  )).join("");

  activityLog.innerHTML = frontendRows || deviceRows
    ? `${frontendRows}${deviceRows}`
    : "<p class=\"empty-state\">Run a URI command or refresh logs to populate this view.</p>";
}

async function refreshLogs() {
  if (!latestMesh.devices.length) {
    latestLogGroups = [];
    renderActivityLog();
    return;
  }

  activityLog.innerHTML = "<p class=\"empty-state\">Loading log:// routes...</p>";
  const groups = await Promise.all(latestMesh.devices.map(async (item) => {
    const name = item.device?.name || item.name;
    const uri = `log://${name}/session/query/recent`;
    const route = routeByUri(uri);
    if (!route) return { device: name, logs: [], error: "log route not discovered" };
    try {
      const data = await runUri(uri, { limit: 12 });
      const result = extractRunResult(data);
      return { device: name, logs: result.logs || [], ok: data.ok };
    } catch (error) {
      return { device: name, logs: [], error: String(error) };
    }
  }));

  latestLogGroups = groups;
  renderActivityLog();
}

async function refreshDevices(updateOutput = true) {
  const response = await fetch("/api/devices");
  latestMesh = await response.json();
  renderDevices(latestMesh);
  renderNovnc(latestMesh);
  if (selectedRoute && !latestMesh.routes.some((route) => route.uri === selectedRoute.uri)) {
    selectedRoute = null;
  }
  renderRoutes();
  renderPayloadForm();
  if (updateOutput) {
    showJson(output, {
      peers: latestMesh.peers,
      reachable: latestMesh.devices.filter((item) => item.reachable).map((item) => item.name),
    });
  }
  renderActivityLog();
}

async function runNlFlow() {
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  timeline.innerHTML = "";
  recordActivity("llm.flow.requested", { prompt });
  showJson(generatedFlow, { status: "generating" });
  showJson(output, { status: "running" });
  const response = await fetch("/api/nl-flow", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, execute: true }),
  });
  const data = await response.json();
  showJson(generatedFlow, data.flow || {});
  for (const item of data.timeline || []) appendTimeline(item);
  showJson(output, data);
  recordActivity("llm.flow.completed", { ok: data.ok, steps: (data.timeline || []).length });
  await refreshDevices(false);
  await refreshLogs();
  showView("results");
}

async function runSelectedRoute() {
  if (!selectedRoute) return;
  if (!payloadForm.reportValidity()) return;
  let payload;
  try {
    payload = payloadFromForm();
  } catch (error) {
    showJson(output, { ok: false, error: String(error) });
    return;
  }

  timeline.innerHTML = "";
  showJson(output, { status: "running", uri: selectedRoute.uri, payload });
  recordActivity("uri.command.started", { uri: selectedRoute.uri, target: targetFromUri(selectedRoute.uri), payload });
  const data = await runUri(selectedRoute.uri, payload);
  showJson(generatedFlow, data.flow || {});
  for (const item of data.timeline || []) appendTimeline(item);
  showJson(output, data);
  recordActivity("uri.command.completed", { uri: selectedRoute.uri, ok: data.ok });
  await refreshDevices(false);
  await refreshLogs();
  showView("results");
}

document.querySelector("#refresh-devices").addEventListener("click", () => {
  recordActivity("mesh.refresh.requested");
  refreshDevices()
    .then(() => refreshLogs())
    .catch((error) => showJson(output, { ok: false, error: String(error) }));
});

runNlFlowButton.addEventListener("click", () => {
  runNlFlow().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

runNlFlowInlineButton.addEventListener("click", () => {
  runNlFlow().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

runSelectedButton.addEventListener("click", () => {
  runSelectedRoute().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

refreshLogsButton.addEventListener("click", () => {
  recordActivity("logs.refresh.requested");
  refreshLogs().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

for (const tab of viewTabs) {
  tab.addEventListener("click", () => showView(tab.dataset.view));
}

for (const button of navigationButtons) {
  button.addEventListener("click", () => focusArea(button.dataset.focus));
}

payloadForm.addEventListener("input", () => {
  showJson(output, {
    selected: selectedRoute?.uri || null,
    payload: previewPayload(),
  });
});

routeFilter.addEventListener("input", renderRoutes);
routesEl.addEventListener("click", (event) => {
  const row = event.target.closest(".route-row");
  if (!row) return;
  selectRoute(row.dataset.uri);
});

promptInput.value = examplePrompt;
setMenuActive("overview");
recordActivity("dashboard.loaded", { view: "device_mesh_lab" });
showJson(generatedFlow, {
  task: { title: "Generated URI workflow appears here" },
  steps: [
    { uri: "env://desktop/runtime/query/health", payload: {} },
    { uri: "proc://laptop/process/query/list", payload: { limit: 8 } },
    { uri: "note://desktop/operator/command/write", payload: { text: "..." } },
  ],
});
refreshDevices()
  .then(() => refreshLogs())
  .catch((error) => showJson(output, { ok: false, error: String(error) }));
