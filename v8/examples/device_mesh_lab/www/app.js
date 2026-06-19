const promptInput = document.querySelector("#nl-prompt");
const generatedFlow = document.querySelector("#generated-flow");
const output = document.querySelector("#output");
const timeline = document.querySelector("#timeline");
const devicesEl = document.querySelector("#devices");
const routesEl = document.querySelector("#routes");
const routeFilter = document.querySelector("#route-filter");
const examplePrompt = "Sprawdź oba komputery, pokaż procesy, zapisz notatkę na dostępnym urządzeniu i pokaż ostatnie logi. Jeśli możesz, sprawdź czy jest python3.";

let latestMesh = { devices: [], routes: [], safeRoutes: [] };

function showJson(node, value) {
  node.textContent = JSON.stringify(value, null, 2);
}

function routeBadge(route) {
  const safe = route.safe === true || latestMesh.safeRoutes.some((item) => item.uri === route.uri);
  return `<span class="badge ${safe ? "safe" : "locked"}">${safe ? "safe" : "locked"}</span>`;
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
        <td>${proc.command}</td>
        <td>${proc.cpu}</td>
        <td>${proc.mem}</td>
      </tr>
    `).join("");
    const installable = (item.installable || []).map((capability) => `
      <li>
        <strong>${capability.capability}</strong>
        <span>${capability.installHint}</span>
      </li>
    `).join("");
    return `
      <article class="device-card ${item.reachable ? "online" : "offline"}">
        <div class="device-head">
          <div>
            <strong>${device.name || item.name}</strong>
            <span>${device.role || "unknown"} · ${item.baseUrl}</span>
          </div>
          <span class="status">${item.reachable ? "online" : "offline"}</span>
        </div>
        <dl>
          <div><dt>Host</dt><dd>${device.hostname || "-"}</dd></div>
          <div><dt>Platform</dt><dd>${device.platform || item.error || "-"}</dd></div>
          <div><dt>Routes</dt><dd>${device.routeCount || 0}</dd></div>
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

function renderRoutes() {
  const filter = routeFilter.value.trim().toLowerCase();
  const rows = latestMesh.routes
    .filter((route) => !filter || route.uri.toLowerCase().includes(filter) || String(route.title || "").toLowerCase().includes(filter))
    .sort((a, b) => a.uri.localeCompare(b.uri))
    .map((route) => `
      <button class="route-row" data-uri="${route.uri}" type="button">
        <code>${route.uri}</code>
        ${routeBadge(route)}
        <span>${route.title || route.adapter || ""}</span>
      </button>
    `).join("");
  routesEl.innerHTML = rows || "<p class=\"muted\">No URI routes discovered.</p>";
}

function appendTimeline(item) {
  const li = document.createElement("li");
  li.innerHTML = `<code>${item.uri}</code> <span class="${item.ok ? "ok" : "fail"}">${item.ok ? "ok" : "failed"}</span>`;
  timeline.appendChild(li);
}

async function refreshDevices() {
  const response = await fetch("/api/devices");
  latestMesh = await response.json();
  renderDevices(latestMesh);
  renderRoutes();
  showJson(output, {
    peers: latestMesh.peers,
    reachable: latestMesh.devices.filter((item) => item.reachable).map((item) => item.name),
  });
}

async function runNlFlow() {
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  timeline.innerHTML = "";
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
  await refreshDevices();
}

async function runRoute(uri) {
  let payload = {};
  if (uri.includes("/which")) payload = { binary: "python3" };
  if (uri.includes("/process/query")) payload = { limit: 8 };
  if (uri.includes("/browser/")) payload = { url: "https://example.com/" };
  if (uri.includes("/note/")) payload = { text: "Manual dashboard URI call" };
  if (uri.startsWith("log://") && uri.includes("/command/write")) payload = { event: "manual.dashboard.call", detail: { uri } };

  const response = await fetch("/api/run-uri", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri, payload }),
  });
  const data = await response.json();
  showJson(generatedFlow, data.flow || {});
  timeline.innerHTML = "";
  for (const item of data.timeline || []) appendTimeline(item);
  showJson(output, data);
}

document.querySelector("#refresh-devices").addEventListener("click", () => {
  refreshDevices().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

document.querySelector("#run-nl-flow").addEventListener("click", () => {
  runNlFlow().catch((error) => showJson(output, { ok: false, error: String(error) }));
});

routeFilter.addEventListener("input", renderRoutes);
routesEl.addEventListener("click", (event) => {
  const row = event.target.closest(".route-row");
  if (!row) return;
  runRoute(row.dataset.uri).catch((error) => showJson(output, { ok: false, error: String(error) }));
});

promptInput.value = examplePrompt;
showJson(generatedFlow, {
  task: { title: "Generated URI workflow appears here" },
  steps: [
    { uri: "env://desktop/runtime/query/health", payload: {} },
    { uri: "proc://laptop/process/query/list", payload: { limit: 8 } },
    { uri: "note://desktop/operator/command/write", payload: { text: "..." } },
  ],
});
refreshDevices().catch((error) => showJson(output, { ok: false, error: String(error) }));
