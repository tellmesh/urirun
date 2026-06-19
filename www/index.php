<?php
$site = require __DIR__ . '/site-data.php';
$docs = $site['docs'];

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES);
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>urirun - URI-addressed command runtime</title>
  <meta name="description" content="urirun turns functions, scripts, containers, and services into reusable URI routes compiled into one registry.">
  <link rel="icon" href="assets/urirun-favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="index.php" aria-label="urirun home">
      <img src="assets/urirun-horizontal.svg" alt="urirun">
    </a>
    <nav aria-label="Main navigation">
      <a href="docs.php?doc=getting-started">Docs</a>
      <a href="#workflow">Workflow</a>
      <a href="#examples">Examples</a>
      <a href="https://github.com/tellmesh/urihandler">GitHub</a>
    </nav>
  </header>

  <main>
    <section class="hero">
      <div class="hero-copy">
        <p class="kicker">urirun://project/home</p>
        <h1>One URI registry for commands across code, shell, containers, and services.</h1>
        <p class="lede">Declare a route once, compile it into a registry, and call the same URI in-process or over HTTP, gRPC, a queue, serverless, Docker, MCP, or an A2A agent card.</p>
        <div class="actions">
          <a class="button primary" href="docs.php?doc=getting-started">Start with v8</a>
          <a class="button" href="docs.php?doc=commands">CLI commands</a>
        </div>
      </div>

      <section class="command-panel" aria-label="Quick command sequence">
        <div class="panel-head">
          <span>quickstart</span>
          <strong>GitHub install</strong>
        </div>
        <pre><code>pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
urirun scan ./project \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
urirun list generated/registry.json
urirun run 'tool://local/report/render' --registry generated/registry.json</code></pre>
      </section>
    </section>

    <section class="facts" aria-label="Project facts">
      <div><span>Runtime</span><strong>urirun</strong></div>
      <div><span>Repository</span><strong>tellmesh/urihandler</strong></div>
      <div><span>Default contract</span><strong>v8 JSON Schema</strong></div>
      <div><span>Execution</span><strong>dry-run first</strong></div>
    </section>

    <section class="section split" id="workflow">
      <div>
        <p class="kicker">flow://registry/build</p>
        <h2>Use existing artifacts as URI packages.</h2>
        <p class="section-copy">The useful path is not writing a new SDK. Point urirun at what your project already ships, generate bindings, validate the registry, and run by URI.</p>
      </div>
      <div class="flow-list">
        <?php foreach ($site['workflow'] as $step): ?>
          <article class="flow-item">
            <code><?= h($step['uri']) ?></code>
            <h3><?= h($step['title']) ?></h3>
            <p><?= h($step['text']) ?></p>
          </article>
        <?php endforeach; ?>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <p class="kicker">registry://local/value/query</p>
        <h2>What gets simpler.</h2>
      </div>
      <div class="feature-grid">
        <?php foreach ($site['features'] as $feature): ?>
          <article class="feature">
            <h3><?= h($feature['title']) ?></h3>
            <p><?= h($feature['text']) ?></p>
          </article>
        <?php endforeach; ?>
      </div>
    </section>

    <section class="section runtime-map">
      <div>
        <p class="kicker">transport://any/adapter/query</p>
        <h2>Same URI, different runtime.</h2>
        <p class="section-copy">A URI names what should run. The transport decides how it runs: in-process, argv, shell, Docker, HTTP, gRPC, a message queue, serverless, MCP, or A2A. The contract and the policy gate stay in one place.</p>
      </div>
      <div class="transport-grid">
        <?php foreach ($site['transports'] as $transport): ?>
          <div class="transport">
            <strong><?= h($transport['name']) ?></strong>
            <span><?= h($transport['detail']) ?></span>
          </div>
        <?php endforeach; ?>
      </div>
    </section>

    <section class="section docs-grid" aria-labelledby="doc-list">
      <div class="section-head">
        <p class="kicker">docs://local/index/query</p>
        <h2 id="doc-list">Documentation.</h2>
      </div>
      <div class="grid">
        <?php foreach ($docs as $slug => $doc): ?>
          <a class="doc-card" href="docs.php?doc=<?= h($slug) ?>">
            <span><?= h($doc['title']) ?></span>
            <small><?= h($doc['description']) ?></small>
          </a>
        <?php endforeach; ?>
      </div>
    </section>

    <section class="section split" id="examples">
      <div>
        <p class="kicker">examples://repo/current/query</p>
        <h2>Examples that show the layers working together.</h2>
        <p class="section-copy">The examples are intentionally small: they show how one registry can be used by browser UI, backend services, Docker workers, generators, and firmware-style adapters.</p>
      </div>
      <div class="example-list">
        <?php foreach ($site['examples'] as $example): ?>
          <article class="example">
            <code><?= h($example['path']) ?></code>
            <p><?= h($example['text']) ?></p>
          </article>
        <?php endforeach; ?>
      </div>
    </section>

    <section class="section roadmap" id="roadmap">
      <div class="section-head">
        <p class="kicker">todo://urirun/usability/query</p>
        <h2>Next usability work.</h2>
      </div>
      <ol>
        <?php foreach ($site['roadmap'] as $item): ?>
          <li><?= h($item) ?></li>
        <?php endforeach; ?>
      </ol>
    </section>
  </main>

  <footer>
    <span>Runtime: urirun</span>
    <span>Repo: tellmesh/urihandler</span>
    <span><a href="docs.php?doc=naming">Naming rules</a></span>
  </footer>
</body>
</html>
