const runtimeConfig = window.URI_RUN_NOVNC_CONFIG || {};
const host = window.location.hostname || "127.0.0.1";
const protocol = window.location.protocol || "http:";
const pcConfig = runtimeConfig.pcs || {
  pc1: { novncPort: "7901", apiPort: "9001" },
  pc2: { novncPort: "7902", apiPort: "9002" },
  pc3: { novncPort: "7903", apiPort: "9003" },
  pc4: { novncPort: "7904", apiPort: "9004" },
};

const pcs = Object.fromEntries(
  Object.entries(pcConfig).map(([pc, config]) => [pc, `${protocol}//${host}:${config.apiPort}`]),
);

const output = document.querySelector("#output");
const timeline = document.querySelector("#timeline");

function setNovncFrames() {
  document.querySelectorAll("iframe[data-pc]").forEach((frame) => {
    const pc = frame.dataset.pc;
    const config = pcConfig[pc];
    if (!config) return;
    frame.src = `${protocol}//${host}:${config.novncPort}/vnc.html?autoconnect=1&resize=scale`;
  });
}

function show(value) {
  output.textContent = JSON.stringify(value, null, 2);
}

function append(uri, ok) {
  const li = document.createElement("li");
  const code = document.createElement("code");
  code.textContent = uri;
  li.append(code, ` ${ok ? "ok" : "failed"}`);
  timeline.appendChild(li);
}

async function run(pc, uri, payload = {}) {
  const response = await fetch(`${pcs[pc]}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri, payload }),
  });
  const data = await response.json();
  append(uri, Boolean(data.ok));
  return data;
}

async function routes() {
  const result = {};
  for (const [pc, base] of Object.entries(pcs)) {
    result[pc] = await fetch(`${base}/routes`).then((response) => response.json());
  }
  show(result);
}

async function browserDemo() {
  timeline.innerHTML = "";
  const results = [];
  results.push(await run("pc1", "log://pc1/session/command/write", {
    event: "browser.demo.started",
    detail: "dashboard started the LAN demo",
  }));
  results.push(await run("pc2", "pc://pc2/service/command/start", {
    name: "orders",
    port: 9102,
    message: "orders service started from dashboard",
  }));
  results.push(await run("pc3", "pc://pc3/http/command/get", {
    url: "http://pc2:9102/",
  }));
  results.push(await run("pc4", "pc://pc4/http/command/get", {
    url: "http://pc2:9102/",
  }));
  results.push(await run("pc1", "log://pc1/session/query/recent", {
    limit: 10,
  }));
  show(results);
}

document.querySelector("#browser-demo").addEventListener("click", () => {
  browserDemo().catch((error) => show({ ok: false, error: String(error) }));
});

document.querySelector("#refresh-routes").addEventListener("click", () => {
  routes().catch((error) => show({ ok: false, error: String(error) }));
});

routes().catch(() => {
  show({
    ok: false,
    message: "Start the example with `make up`, then refresh this page.",
  });
});

setNovncFrames();
