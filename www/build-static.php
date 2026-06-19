<?php
declare(strict_types=1);

$site = require __DIR__ . '/site-data.php';

$baseUrl = 'https://tellmesh.github.io/urihandler/';
$repoUrl = 'https://github.com/tellmesh/urihandler';

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES);
}

function doc_url(string $slug, string $base = 'docs/'): string
{
    return $base . rawurlencode($slug) . '.html';
}

function inline_md(string $text): string
{
    $text = htmlspecialchars($text, ENT_QUOTES);
    $text = preg_replace_callback('/\[([^\]]+)\]\(([a-z0-9-]+)\.md\)/i', static function (array $m): string {
        return '<a href="' . rawurlencode($m[2]) . '.html">' . $m[1] . '</a>';
    }, $text);
    $text = preg_replace('/`([^`]+)`/', '<code>$1</code>', $text);
    $text = preg_replace('/\*\*([^*]+)\*\*/', '<strong>$1</strong>', $text);
    return $text;
}

function render_md(string $markdown): string
{
    $html = '';
    $inCode = false;
    $paragraph = [];
    $inList = false;
    $listItem = null;
    $flushParagraph = static function () use (&$html, &$paragraph): void {
        if ($paragraph !== []) {
            $html .= '<p>' . inline_md(implode(' ', $paragraph)) . "</p>\n";
            $paragraph = [];
        }
    };
    $flushListItem = static function () use (&$html, &$listItem): void {
        if ($listItem !== null) {
            $html .= '<li>' . inline_md($listItem) . "</li>\n";
            $listItem = null;
        }
    };
    $closeList = static function () use (&$html, &$inList, $flushListItem): void {
        if ($inList) {
            $flushListItem();
            $html .= "</ul>\n";
            $inList = false;
        }
    };
    foreach (preg_split('/\R/', $markdown) as $line) {
        if (str_starts_with($line, '```')) {
            $flushParagraph();
            $closeList();
            $html .= $inCode ? "</code></pre>\n" : '<pre><code>';
            $inCode = !$inCode;
            continue;
        }
        if ($inCode) {
            $html .= htmlspecialchars($line, ENT_QUOTES) . "\n";
            continue;
        }
        if ($line === '') {
            $flushParagraph();
            $closeList();
            continue;
        }
        if (preg_match('/^(#{1,3})\s+(.*)$/', $line, $m)) {
            $flushParagraph();
            $closeList();
            $level = strlen($m[1]) + 1; // shift h1->h2 under the page title
            $html .= "<h{$level}>" . htmlspecialchars($m[2], ENT_QUOTES) . "</h{$level}>\n";
            continue;
        }
        if (preg_match('/^-\s+(.*)$/', $line, $m)) {
            $flushParagraph();
            if (!$inList) {
                $html .= "<ul>\n";
                $inList = true;
            }
            $flushListItem();
            $listItem = $m[1];
            continue;
        }
        if ($inList && preg_match('/^\s{2,}(.+)$/', $line, $m)) {
            $listItem = trim(($listItem ?? '') . ' ' . trim($m[1]));
            continue;
        }
        $closeList();
        $paragraph[] = trim($line);
    }
    if ($inCode) {
        $html .= "</code></pre>\n";
    }
    $flushParagraph();
    $closeList();
    return $html;
}

function docs_file_map(): array
{
    return [
        'index' => 'index.md',
        'getting-started' => 'getting-started.md',
        'naming' => 'naming.md',
        'commands' => 'commands.md',
        'registry-and-bindings' => 'registry-and-bindings.md',
        'transports' => 'transports.md',
        'logo' => 'logo.md',
        'roadmap' => 'roadmap.md',
    ];
}

function doc_titles(string $lang): array
{
    if ($lang === 'pl') {
        return [
            'index' => 'Dokumentacja', 'getting-started' => 'Pierwsze kroki', 'naming' => 'Nazewnictwo',
            'commands' => 'Komendy', 'registry-and-bindings' => 'Registry', 'transports' => 'Transporty',
            'logo' => 'Logo', 'roadmap' => 'Roadmap',
        ];
    }
    return [
        'index' => 'Docs index', 'getting-started' => 'Getting started', 'naming' => 'Naming',
        'commands' => 'Commands', 'registry-and-bindings' => 'Registry', 'transports' => 'Transports',
        'logo' => 'Logo', 'roadmap' => 'Roadmap',
    ];
}

/**
 * Build one HTML page per doc for a language. EN pages live in www/docs/ and PL
 * pages in www/docs/pl/, so asset/home links use the right relative prefix and a
 * PL/EN switch points at the sibling translation.
 */
function build_doc_pages(array $site, string $repoUrl, string $lang): array
{
    $isPl = $lang === 'pl';
    $assetPrefix = $isPl ? '../../' : '../';        // www/docs/pl/* vs www/docs/*
    $srcDir = __DIR__ . '/../docs/' . ($isPl ? 'pl/' : '');
    $titles = doc_titles($lang);
    $homeLabel = $isPl ? 'Strona główna' : 'Home';

    $sidebar = "    <aside>\n";
    foreach (docs_file_map() as $slug => $file) {
        $sidebar .= '      <a data-slug="' . h($slug) . '" href="' . h($slug) . '.html"><span>' . h($titles[$slug] ?? $slug) . "</span></a>\n";
    }
    $sidebar .= "    </aside>\n";

    $pages = [];
    foreach (docs_file_map() as $slug => $file) {
        $path = $srcDir . $file;
        $markdown = is_file($path) ? file_get_contents($path) : '# Missing document';
        $title = $titles[$slug] ?? $slug;
        $plHref = $isPl ? ($slug . '.html') : ('pl/' . $slug . '.html');
        $enHref = $isPl ? ('../' . $slug . '.html') : ($slug . '.html');

        $html = '<!doctype html>' . "\n" . '<html lang="' . $lang . '">' . "\n<head>\n";
        $html .= "  <meta charset=\"utf-8\">\n";
        $html .= "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n";
        $html .= '  <title>urirun docs: ' . h($title) . "</title>\n";
        $html .= '  <meta name="description" content="urirun documentation - ' . h($title) . "\">\n";
        $html .= '  <link rel="icon" href="' . $assetPrefix . "assets/urirun-favicon.svg\" type=\"image/svg+xml\">\n";
        $html .= '  <link rel="alternate" hreflang="en" href="' . h($enHref) . "\">\n";
        $html .= '  <link rel="alternate" hreflang="pl" href="' . h($plHref) . "\">\n";
        $html .= '  <link rel="stylesheet" href="' . $assetPrefix . "style.css\">\n";
        $html .= "</head>\n<body>\n";
        $html .= "  <header class=\"topbar\">\n";
        $html .= '    <a class="brand" href="' . $assetPrefix . 'index.html" aria-label="urirun home"><img src="' . $assetPrefix . "assets/urirun-horizontal.svg\" alt=\"urirun\"></a>\n";
        $html .= "    <nav>\n";
        $html .= '      <a href="' . $assetPrefix . 'index.html">' . h($homeLabel) . "</a>\n";
        $html .= "      <a href=\"index.html\">Docs</a>\n";
        $html .= "      <a href=\"" . h($repoUrl) . "\">GitHub</a>\n";
        $html .= "      <span class=\"language-switch\">\n";
        $html .= '        <a class="' . (!$isPl ? 'active' : '') . '" href="' . h($enHref) . "\" hreflang=\"en\" lang=\"en\">EN</a>\n";
        $html .= '        <a class="' . ($isPl ? 'active' : '') . '" href="' . h($plHref) . "\" hreflang=\"pl\" lang=\"pl\">PL</a>\n";
        $html .= "      </span>\n";
        $html .= "    </nav>\n";
        $html .= "  </header>\n";
        $aside = str_replace('data-slug="' . $slug . '" href', 'class="active" data-slug="' . $slug . '" href', $sidebar);
        $html .= "  <main class=\"docs-layout\">\n" . $aside;
        $html .= "    <article class=\"doc-body\">\n" . render_md($markdown) . "    </article>\n";
        $html .= "  </main>\n</body>\n</html>\n";
        $pages[$slug] = $html;
    }
    return $pages;
}

function render_doc_cards(array $docs, string $base = 'docs/'): string
{
    $html = '';
    foreach ($docs as $slug => $doc) {
        $html .= '          <a class="doc-card" href="' . h(doc_url((string) $slug, $base)) . '">' . "\n";
        $html .= '            <span>' . h($doc['title']) . '</span>' . "\n";
        $html .= '            <small>' . h($doc['description']) . '</small>' . "\n";
        $html .= "          </a>\n";
    }
    return $html;
}

function render_flow_items(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $html .= "          <article class=\"flow-item\">\n";
        $html .= '            <code>' . h($item['uri']) . '</code>' . "\n";
        $html .= '            <h3>' . h($item['title']) . '</h3>' . "\n";
        $html .= '            <p>' . h($item['text']) . '</p>' . "\n";
        $html .= "          </article>\n";
    }
    return $html;
}

function render_features(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $html .= "          <article class=\"feature\">\n";
        $html .= '            <h3>' . h($item['title']) . '</h3>' . "\n";
        $html .= '            <p>' . h($item['text']) . '</p>' . "\n";
        $html .= "          </article>\n";
    }
    return $html;
}

function render_transports(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $html .= "          <div class=\"transport\">\n";
        $html .= '            <strong>' . h($item['name']) . '</strong>' . "\n";
        $html .= '            <span>' . h($item['detail']) . '</span>' . "\n";
        $html .= "          </div>\n";
    }
    return $html;
}

function render_examples(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $href = 'https://github.com/tellmesh/urihandler/tree/main/' . $item['path'];
        $html .= "          <article class=\"example\">\n";
        $html .= '            <a href="' . h($href) . '"><code>' . h($item['path']) . '</code></a>' . "\n";
        $html .= '            <p>' . h($item['text']) . '</p>' . "\n";
        $html .= "          </article>\n";
    }
    return $html;
}

function render_roadmap(array $items): string
{
    $html = '';
    foreach ($items as $item) {
        $html .= '        <li>' . h($item) . "</li>\n";
    }
    return $html;
}

function render_code_block(string $label, string $code): string
{
    return "            <div class=\"code-block\">\n"
        . '              <span>' . h($label) . "</span>\n"
        . '              <pre><code>' . h($code) . "</code></pre>\n"
        . "            </div>\n";
}

function render_contract_tabs(array $page): string
{
    $tabs = $page['tech_tabs'];
    $steps = $page['schema_steps'];
    $active = $tabs[0]['id'];
    $html = "    <section class=\"section contract-section\" id=\"contract\">\n";
    $html .= "      <div class=\"contract-intro\">\n";
    $html .= "        <div>\n";
    $html .= '          <p class="kicker">' . h($page['contract_kicker']) . "</p>\n";
    $html .= '          <h2>' . h($page['contract_title']) . "</h2>\n";
    $html .= '          <p class="section-copy">' . h($page['contract_text']) . "</p>\n";
    $html .= "        </div>\n";
    $html .= "        <div class=\"schema-steps\" aria-label=\"" . h($page['schema_steps_label']) . "\">\n";
    foreach ($steps as $step) {
        $html .= "          <div class=\"schema-step\">\n";
        $html .= '            <span>' . h($step['mark']) . "</span>\n";
        $html .= '            <strong>' . h($step['title']) . "</strong>\n";
        $html .= '            <small>' . h($step['text']) . "</small>\n";
        $html .= "          </div>\n";
    }
    $html .= "        </div>\n";
    $html .= "      </div>\n";
    $html .= "\n";
    $html .= "      <div class=\"tech-tabs\" data-tech-tabs>\n";
    $html .= "        <div class=\"tab-list\" role=\"tablist\" aria-label=\"" . h($page['tech_tabs_label']) . "\">\n";
    foreach ($tabs as $tab) {
        $selected = $tab['id'] === $active;
        $html .= '          <button class="tab-button' . ($selected ? ' active' : '') . '" type="button" role="tab" aria-selected="' . ($selected ? 'true' : 'false') . '" aria-controls="panel-' . h($tab['id']) . '" id="tab-' . h($tab['id']) . '" data-tech-tab="' . h($tab['id']) . '">' . h($tab['label']) . "</button>\n";
    }
    $html .= "        </div>\n";
    foreach ($tabs as $tab) {
        $selected = $tab['id'] === $active;
        $html .= '        <article class="tech-panel' . ($selected ? ' active' : '') . '" id="panel-' . h($tab['id']) . '" role="tabpanel" aria-labelledby="tab-' . h($tab['id']) . '"' . ($selected ? '' : ' hidden') . ">\n";
        $html .= "          <div class=\"tech-copy\">\n";
        $html .= '            <span>' . h($tab['eyebrow']) . "</span>\n";
        $html .= '            <h3>' . h($tab['title']) . "</h3>\n";
        $html .= '            <p>' . h($tab['text']) . "</p>\n";
        $html .= "          </div>\n";
        $html .= "          <div class=\"tech-code-grid\">\n";
        $html .= render_code_block($page['declare_label'], $tab['declare']);
        $html .= render_code_block($page['registry_label'], $tab['registry']);
        $html .= "          </div>\n";
        $html .= "        </article>\n";
    }
    $html .= "      </div>\n";
    $html .= "    </section>\n";
    return $html;
}

function render_page(array $page, array $site, string $baseUrl, string $repoUrl): string
{
    $isPl = $page['lang'] === 'pl';
    $currentFile = $isPl ? 'index.html' : 'index.en.html';
    $otherFile = $isPl ? 'index.en.html' : 'index.html';
    $canonical = $baseUrl . ($isPl ? '' : 'index.en.html');
    $plUrl = $baseUrl;
    $enUrl = $baseUrl . 'index.en.html';
    $docsBase = $isPl ? 'docs/pl/' : 'docs/';
    $docsUrl = $docsBase . 'index.html';
    $quickstartUrl = $docsBase . 'getting-started.html';
    $commandsUrl = $docsBase . 'commands.html';
    $namingUrl = $docsBase . 'naming.html';

    $nav = $page['nav'];
    $html = '<!doctype html>' . "\n";
    $html .= '<html lang="' . h($page['lang']) . '">' . "\n";
    $html .= "<head>\n";
    $html .= "  <meta charset=\"utf-8\">\n";
    $html .= "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n";
    $html .= '  <title>' . h($page['title']) . "</title>\n";
    $html .= '  <meta name="description" content="' . h($page['description']) . "\">\n";
    $html .= "  <link rel=\"icon\" href=\"assets/urirun-favicon.svg\" type=\"image/svg+xml\">\n";
    $html .= '  <link rel="canonical" href="' . h($canonical) . "\">\n";
    $html .= '  <link rel="alternate" hreflang="pl" href="' . h($plUrl) . "\">\n";
    $html .= '  <link rel="alternate" hreflang="en" href="' . h($enUrl) . "\">\n";
    $html .= '  <link rel="alternate" hreflang="x-default" href="' . h($plUrl) . "\">\n";
    $html .= '  <meta property="og:title" content="' . h($page['title']) . "\">\n";
    $html .= '  <meta property="og:description" content="' . h($page['description']) . "\">\n";
    $html .= '  <meta property="og:type" content="website">' . "\n";
    $html .= '  <meta property="og:url" content="' . h($canonical) . "\">\n";
    $html .= "  <link rel=\"stylesheet\" href=\"style.css\">\n";
    $html .= "</head>\n";
    $html .= "<body>\n";
    $html .= "  <header class=\"topbar\">\n";
    $html .= '    <a class="brand" href="' . h($currentFile) . "\" aria-label=\"urirun home\">\n";
    $html .= "      <img src=\"assets/urirun-horizontal.svg\" alt=\"urirun\">\n";
    $html .= "    </a>\n";
    $html .= "    <nav aria-label=\"" . h($nav['label']) . "\">\n";
    $html .= '      <a href="' . h($docsUrl) . '">' . h($nav['docs']) . "</a>\n";
    $html .= '      <a href="#workflow">' . h($nav['workflow']) . "</a>\n";
    $html .= '      <a href="#examples">' . h($nav['examples']) . "</a>\n";
    $html .= '      <a href="' . h($repoUrl) . "\">GitHub</a>\n";
    $html .= "      <span class=\"language-switch\" aria-label=\"" . h($nav['language']) . "\">\n";
    $html .= '        <a class="' . ($isPl ? 'active' : '') . '" href="index.html" hreflang="pl" lang="pl" data-lang-choice="pl">PL</a>' . "\n";
    $html .= '        <a class="' . (!$isPl ? 'active' : '') . '" href="index.en.html" hreflang="en" lang="en" data-lang-choice="en">EN</a>' . "\n";
    $html .= "      </span>\n";
    $html .= "    </nav>\n";
    $html .= "  </header>\n";
    $html .= "\n";
    $html .= "  <main>\n";
    $html .= "    <p class=\"language-memory\" data-language-memory hidden><a href=\"" . h($otherFile) . "\"></a></p>\n";
    $html .= "    <section class=\"hero\">\n";
    $html .= "      <div class=\"hero-copy\">\n";
    $html .= '        <p class="kicker">' . h($page['hero_kicker']) . "</p>\n";
    $html .= '        <h1>' . h($page['hero_title']) . "</h1>\n";
    $html .= '        <p class="lede">' . h($page['hero_text']) . "</p>\n";
    $html .= "        <div class=\"actions\">\n";
    $html .= '          <a class="button primary" href="' . h($quickstartUrl) . '">' . h($page['primary_cta']) . "</a>\n";
    $html .= '          <a class="button" href="' . h($commandsUrl) . '">' . h($page['secondary_cta']) . "</a>\n";
    $html .= "        </div>\n";
    $html .= "      </div>\n";
    $html .= "\n";
    $html .= "      <section class=\"command-panel\" aria-label=\"" . h($page['quickstart_label']) . "\">\n";
    $html .= "        <div class=\"panel-head\">\n";
    $html .= '          <span>' . h($page['quickstart_short']) . "</span>\n";
    $html .= '          <strong>' . h($page['quickstart_title']) . "</strong>\n";
    $html .= "        </div>\n";
    $html .= "        <pre><code>pip install \"git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python\"\n";
    $html .= "urirun scan ./project \\\n";
    $html .= "  --out generated/bindings.v8.json \\\n";
    $html .= "  --registry-out generated/registry.json\n";
    $html .= "urirun list generated/registry.json\n";
    $html .= "urirun run 'tool://local/report/render' --registry generated/registry.json</code></pre>\n";
    $html .= "      </section>\n";
    $html .= "    </section>\n";
    $html .= "\n";
    $html .= "    <section class=\"facts\" aria-label=\"" . h($page['facts_label']) . "\">\n";
    foreach ($page['facts'] as $fact) {
        $html .= "      <div><span>" . h($fact[0]) . "</span><strong>" . h($fact[1]) . "</strong></div>\n";
    }
    $html .= "    </section>\n";
    $html .= "\n";
    $html .= render_contract_tabs($page);
    $html .= "\n";
    $html .= "    <section class=\"section split\" id=\"workflow\">\n";
    $html .= "      <div>\n";
    $html .= '        <p class="kicker">' . h($page['workflow_kicker']) . "</p>\n";
    $html .= '        <h2>' . h($page['workflow_title']) . "</h2>\n";
    $html .= '        <p class="section-copy">' . h($page['workflow_text']) . "</p>\n";
    $html .= "      </div>\n";
    $html .= "      <div class=\"flow-list\">\n";
    $html .= render_flow_items($page['workflow']);
    $html .= "      </div>\n";
    $html .= "    </section>\n";
    $html .= "    <section class=\"section runtime-map\">\n";
    $html .= "      <div>\n";
    $html .= '        <p class="kicker">' . h($page['runtime_kicker']) . "</p>\n";
    $html .= '        <h2>' . h($page['runtime_title']) . "</h2>\n";
    $html .= '        <p class="section-copy">' . h($page['runtime_text']) . "</p>\n";
    $html .= "      </div>\n";
    $html .= "      <div class=\"transport-grid\">\n";
    $html .= render_transports($page['transports']);
    $html .= "      </div>\n";
    $html .= "    </section>\n";
    $html .= "\n";
    $html .= "    <section class=\"section docs-grid\" aria-labelledby=\"doc-list\">\n";
    $html .= "      <div class=\"section-head\">\n";
    $html .= '        <p class="kicker">' . h($page['docs_kicker']) . "</p>\n";
    $html .= '        <h2 id="doc-list">' . h($page['docs_title']) . "</h2>\n";
    $html .= "      </div>\n";
    $html .= "      <div class=\"grid\">\n";
    $html .= render_doc_cards($page['docs'], $docsBase);
    $html .= "      </div>\n";
    $html .= "    </section>\n";
    $html .= "\n";
    $html .= "    <section class=\"section split\" id=\"examples\">\n";
    $html .= "      <div>\n";
    $html .= '        <p class="kicker">' . h($page['examples_kicker']) . "</p>\n";
    $html .= '        <h2>' . h($page['examples_title']) . "</h2>\n";
    $html .= '        <p class="section-copy">' . h($page['examples_text']) . "</p>\n";
    $html .= "        <figure class=\"showcase\">\n";
    $html .= '          <a href="https://github.com/tellmesh/urihandler/tree/main/v8/examples/novnc_lan_flow"><img src="assets/pc4.png" alt="' . h($page['showcase_alt']) . '" loading="lazy" width="1200" height="740"></a>' . "\n";
    $html .= '          <figcaption>' . h($page['showcase_caption']) . "</figcaption>\n";
    $html .= "        </figure>\n";
    $html .= "      </div>\n";
    $html .= "      <div class=\"example-list\">\n";
    $html .= render_examples($page['examples']);
    $html .= "      </div>\n";
    $html .= "    </section>\n";
    $html .= "\n";
    $html .= "    <section class=\"section roadmap\" id=\"roadmap\">\n";
    $html .= "      <div class=\"section-head\">\n";
    $html .= '        <p class="kicker">' . h($page['roadmap_kicker']) . "</p>\n";
    $html .= '        <h2>' . h($page['roadmap_title']) . "</h2>\n";
    $html .= "      </div>\n";
    $html .= "      <ol>\n";
    $html .= render_roadmap($page['roadmap']);
    $html .= "      </ol>\n";
    $html .= "    </section>\n";
    $html .= "  </main>\n";
    $html .= "\n";
    $html .= "  <footer>\n";
    $html .= "    <span>Runtime: urirun</span>\n";
    $html .= "    <span>Repo: tellmesh/urihandler</span>\n";
    $html .= '    <span><a href="' . h($namingUrl) . '">' . h($page['naming_link']) . "</a></span>\n";
    $html .= "  </footer>\n";
    $html .= "  <script src=\"language.js\" defer></script>\n";
    $html .= "</body>\n";
    $html .= "</html>\n";

    return $html;
}

$plDocs = [
    'getting-started' => [
        'title' => 'Start',
        'description' => 'Instalacja z GitHuba, skanowanie artefaktów, walidacja i pierwsze uruchomienie URI.',
    ],
    'naming' => [
        'title' => 'Nazewnictwo',
        'description' => 'Gdzie używać nazwy urirun i czemu URL repozytorium nadal zawiera urihandler.',
    ],
    'commands' => [
        'title' => 'Komendy',
        'description' => 'CLI, wersjonowane entry pointy i generowanie bindingów w jednej linii.',
    ],
    'registry-and-bindings' => [
        'title' => 'Registry',
        'description' => 'Jak przenośne bindingi stają się trasami runtime do wykonania.',
    ],
    'transports' => [
        'title' => 'Transporty',
        'description' => 'Funkcje lokalne, shell, Docker, HTTP, gRPC, przeglądarka, MCP i A2A.',
    ],
    'logo' => [
        'title' => 'Logo',
        'description' => 'Wektory SVG dla ikony, wordmarka, favicony i lockupów.',
    ],
    'roadmap' => [
        'title' => 'Roadmap',
        'description' => 'Praktyczne kroki, które uproszczą użycie urirun.',
    ],
];

$techTabsPl = [
    [
        'id' => 'python',
        'label' => 'Python',
        'eyebrow' => 'decorator + Pydantic',
        'title' => 'Dekorator robi binding z sygnatury funkcji.',
        'text' => 'Typy i wartości domyślne trafiają do JSON Schema, a lista argv zostaje deterministycznym szablonem komendy.',
        'declare' => <<<'CODE'
from urirun.v8 import decorated_bindings, uri_command

@uri_command("media://local/video/transcode")
def transcode(input: str, output: str, width: int = 1280, height: int = 720):
    return ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]
CODE,
        'registry' => <<<'CODE'
from urirun.v8 import compile_registry, decorated_bindings

bindings = decorated_bindings()
registry = compile_registry(bindings)
CODE,
    ],
    [
        'id' => 'javascript',
        'label' => 'JavaScript',
        'eyebrow' => 'plain JS helper',
        'title' => 'Helper JS składa binding bez transpilerów.',
        'text' => 'Deklaracja pól tworzy inputSchema, a factory komendy zwraca argv z placeholderami.',
        'declare' => <<<'CODE'
import { bindingDocument, string, uriCommand } from "./uri-command.mjs";

const greet = uriCommand(
  "js://local/greet/message",
  { name: string({ required: true }) },
  ({ name }) => ["node", "-e", "console.log(process.argv[1])", name],
);
CODE,
        'registry' => <<<'CODE'
node generate-bindings.mjs > generated/bindings.v8.json
python -m urirun.v8 compile generated/bindings.v8.json \
  --out generated/registry.json
CODE,
    ],
    [
        'id' => 'c',
        'label' => 'C',
        'eyebrow' => 'firmware route table',
        'title' => 'Firmware może mieć prostą tabelę tras URI.',
        'text' => 'Kod C obsługuje lokalny dispatch, a registry dla reszty systemu można wygenerować jako kontrakt obok firmware.',
        'declare' => <<<'CODE'
static const UriRoute routes[] = {
  {"firmware://device-01/led/command/set", led_set},
  {"firmware://device-01/telemetry/query/latest", telemetry_latest},
};
CODE,
        'registry' => <<<'CODE'
python -m urirun.v8 add-command "firmware://device-01/led/command/set" \
  --argv "./firmware-cli led set {state}" \
  --param state:boolean:required \
  --out generated/bindings.v8.json
python -m urirun.v8 compile generated/bindings.v8.json --out generated/registry.json
CODE,
    ],
    [
        'id' => 'shell',
        'label' => 'Shell',
        'eyebrow' => 'scan scripts',
        'title' => 'Skrypt shell staje się URI przez skan projektu.',
        'text' => 'Nie trzeba przepisywać istniejących skryptów. urirun skanuje pliki i tworzy bindingi do kontrolowanego wykonania.',
        'declare' => <<<'CODE'
#!/usr/bin/env bash
# scripts/render-report.sh
set -euo pipefail
echo "report for ${1:-today}"
CODE,
        'registry' => <<<'CODE'
python -m urirun.v8 scan ./scripts \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
CODE,
    ],
    [
        'id' => 'docker',
        'label' => 'Docker',
        'eyebrow' => 'image label + manifest',
        'title' => 'Obraz Dockera wskazuje manifest URI.',
        'text' => 'Kontener niesie własne bindings.json, a skan Dockerfile zbiera manifesty do wspólnego registry.',
        'declare' => <<<'CODE'
FROM python:3.12-slim
LABEL io.tellmesh.urirun.manifest="/app/bindings.json"
COPY bindings.json /app/bindings.json
COPY worker.py /app/worker.py
CODE,
        'registry' => <<<'CODE'
python -m urirun.v8 scan ./docker-stack \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
CODE,
    ],
    [
        'id' => 'typescript',
        'label' => 'TypeScript',
        'eyebrow' => 'decorator-style declaration',
        'title' => 'Dekorator TS daje typowaną deklarację komendy.',
        'text' => 'Metoda zwraca argv, a pola dekoratora są schematem wejścia dla runtime.',
        'declare' => <<<'CODE'
class MathCommands {
  @uriCommand("ts://local/math/add", {
    a: { type: "integer", required: true },
    b: { type: "integer", default: 0 },
  })
  add({ a, b }) {
    return ["node", "-e", "console.log(Number(process.argv[1]) + Number(process.argv[2]))", a, b];
  }
}
CODE,
        'registry' => <<<'CODE'
npx tsx decorators.ts > generated/bindings.v8.json
python -m urirun.v8 compile generated/bindings.v8.json \
  --out generated/registry.json
CODE,
    ],
    [
        'id' => 'php',
        'label' => 'PHP',
        'eyebrow' => 'PHP 8 attribute + reflection',
        'title' => 'Atrybut PHP generuje binding przez reflection.',
        'text' => 'Parametry funkcji stają się inputSchema, a atrybut trzyma URI i argv.',
        'declare' => <<<'CODE'
#[UriCommand(
  uri: "php://local/slug/create",
  argv: ["php", "-r", "echo strtolower($argv[1]);", "{text}"],
)]
function slug(string $text, int $limit = 64): void {}
CODE,
        'registry' => <<<'CODE'
php examples/php/generate-bindings.php > generated/bindings.v8.json
python -m urirun.v8 compile generated/bindings.v8.json \
  --out generated/registry.json
CODE,
    ],
];

$techTabsEn = [
    [
        'id' => 'python',
        'label' => 'Python',
        'eyebrow' => 'decorator + Pydantic',
        'title' => 'The decorator turns a function signature into a binding.',
        'text' => 'Types and defaults become JSON Schema, while the returned argv list becomes a deterministic command template.',
        'declare' => $techTabsPl[0]['declare'],
        'registry' => $techTabsPl[0]['registry'],
    ],
    [
        'id' => 'javascript',
        'label' => 'JavaScript',
        'eyebrow' => 'plain JS helper',
        'title' => 'A small JS helper emits bindings without a transpiler.',
        'text' => 'Field declarations produce inputSchema, and the command factory returns argv placeholders.',
        'declare' => $techTabsPl[1]['declare'],
        'registry' => $techTabsPl[1]['registry'],
    ],
    [
        'id' => 'c',
        'label' => 'C',
        'eyebrow' => 'firmware route table',
        'title' => 'Firmware can expose a small URI route table.',
        'text' => 'C handles local dispatch, while a generated registry gives the rest of the system the same contract.',
        'declare' => $techTabsPl[2]['declare'],
        'registry' => $techTabsPl[2]['registry'],
    ],
    [
        'id' => 'shell',
        'label' => 'Shell',
        'eyebrow' => 'scan scripts',
        'title' => 'A shell script becomes a URI by scanning the project.',
        'text' => 'Existing scripts stay in place. urirun scans them and creates bindings for controlled execution.',
        'declare' => $techTabsPl[3]['declare'],
        'registry' => $techTabsPl[3]['registry'],
    ],
    [
        'id' => 'docker',
        'label' => 'Docker',
        'eyebrow' => 'image label + manifest',
        'title' => 'A Docker image points to its URI manifest.',
        'text' => 'The container carries bindings.json, and Dockerfile scanning collects manifests into the shared registry.',
        'declare' => $techTabsPl[4]['declare'],
        'registry' => $techTabsPl[4]['registry'],
    ],
    [
        'id' => 'typescript',
        'label' => 'TypeScript',
        'eyebrow' => 'decorator-style declaration',
        'title' => 'A TS decorator gives a typed command declaration.',
        'text' => 'The method returns argv, while decorator fields become the runtime input schema.',
        'declare' => $techTabsPl[5]['declare'],
        'registry' => $techTabsPl[5]['registry'],
    ],
    [
        'id' => 'php',
        'label' => 'PHP',
        'eyebrow' => 'PHP 8 attribute + reflection',
        'title' => 'A PHP attribute generates a binding through reflection.',
        'text' => 'Function parameters become inputSchema, and the attribute carries URI plus argv.',
        'declare' => $techTabsPl[6]['declare'],
        'registry' => $techTabsPl[6]['registry'],
    ],
];

$pages = [
    [
        'lang' => 'pl',
        'file' => __DIR__ . '/index.html',
        'title' => 'urirun - runtime komend adresowanych URI',
        'description' => 'urirun zmienia funkcje, skrypty, kontenery i usługi w reużywalne trasy URI kompilowane do jednego registry.',
        'nav' => [
            'label' => 'Nawigacja główna',
            'docs' => 'Dokumentacja',
            'workflow' => 'Workflow',
            'examples' => 'Przykłady',
            'language' => 'Wersje językowe',
        ],
        'hero_kicker' => 'urirun://project/home',
        'hero_title' => 'Jedno registry URI dla komend w kodzie, shellu, kontenerach i usługach.',
        'hero_text' => 'Deklarujesz trasę raz, kompilujesz ją do registry i wywołujesz ten sam URI lokalnie albo przez HTTP, gRPC, kolejkę, serverless, Docker, MCP lub kartę agenta A2A.',
        'primary_cta' => 'Zacznij od v8',
        'secondary_cta' => 'Komendy CLI',
        'quickstart_label' => 'Sekwencja szybkiego startu',
        'quickstart_short' => 'quickstart',
        'quickstart_title' => 'Instalacja z GitHuba',
        'facts_label' => 'Fakty o projekcie',
        'facts' => [
            ['Runtime', 'urirun'],
            ['Repozytorium', 'tellmesh/urihandler'],
            ['Domyślny kontrakt', 'v8 JSON Schema'],
            ['Wykonanie', 'dry-run first'],
        ],
        'workflow_kicker' => 'flow://registry/build',
        'workflow_title' => 'Używaj istniejących artefaktów jako paczek URI.',
        'workflow_text' => 'Najprostsza droga to nie nowe SDK. Wskazujesz urirun to, co projekt już ma, generujesz bindingi, walidujesz registry i uruchamiasz po URI.',
        'workflow' => [
            ['uri' => 'repo://project/artifacts/query/scan', 'title' => 'Skanuj artefakty', 'text' => 'Czytaj etykiety Dockerfile, metadane paczek, targety Make, skrypty shell i jawne bindingi.'],
            ['uri' => 'registry://local/routes/command/compile', 'title' => 'Kompiluj registry', 'text' => 'Zamień przenośne pliki bindingów w jedno drzewo lookup dla każdego runtime.'],
            ['uri' => 'policy://local/execution/query/check', 'title' => 'Kontroluj wykonanie', 'text' => 'Najpierw dry-run, potem jawne allow rules dla argv, shell, Docker lub wywołań sieciowych.'],
            ['uri' => 'flow://local/task/command/run', 'title' => 'Uruchamiaj ten sam URI', 'text' => 'Wołaj go z shella, backendu, przeglądarki, usługi Docker, narzędzia MCP albo karty A2A.'],
        ],
        'features_kicker' => 'registry://local/value/query',
        'features_title' => 'Co robi się prostsze.',
        'features' => [
            ['title' => 'Adopcja artifact-first', 'text' => 'Dockerfile, pyproject, package.json, shell, Makefile i jawne bindingi stają się trasami bez ręcznego pisania każdego endpointa.'],
            ['title' => 'Wywołania schema-first', 'text' => 'Bindingi v8 używają JSON Schema. Dekoratory Pythona mogą generować schema z sygnatur funkcji przez Pydantic.'],
            ['title' => 'Jeden adres w wielu warstwach', 'text' => 'Frontend, backend, shell, firmware i flow usług mogą dzielić ten sam standard nazewnictwa URI.'],
            ['title' => 'Policy przed wykonaniem', 'text' => 'Komendy są domyślnie dry-run. Realne wykonanie wymaga jawnych reguł allow i deny.'],
        ],
        'contract_kicker' => 'urirun://schema',
        'contract_title' => 'Jeden kontrakt, wiele runtime’ów.',
        'contract_text' => 'Pakowanie komend zaczyna się od schematu. Dekorator, helper albo skan artefaktu generuje binding, potem urirun kompiluje go do registry i uruchamia po tym samym adresie URI.',
        'schema_steps_label' => 'Proces tworzenia komendy URI',
        'schema_steps' => [
            ['mark' => 'fn', 'title' => 'Napisz funkcję', 'text' => 'Typy i wartości domyślne są źródłem prawdy.'],
            ['mark' => '{ }', 'title' => 'Wygeneruj binding', 'text' => 'Powstaje inputSchema i szablon argv lub shell.'],
            ['mark' => '✓', 'title' => 'Skompiluj registry', 'text' => 'Trasy są walidowane i gotowe do odkrywania.'],
            ['mark' => '▶', 'title' => 'Uruchom URI', 'text' => 'Dry-run najpierw, execute dopiero z polityką.'],
        ],
        'tech_tabs_label' => 'Technologie generujące bindingi URI',
        'declare_label' => 'deklaracja',
        'registry_label' => 'binding + registry',
        'tech_tabs' => $techTabsPl,
        'runtime_kicker' => 'transport://any/adapter/query',
        'runtime_title' => 'Ten sam URI, inny runtime.',
        'runtime_text' => 'URI nazywa to, co ma się wykonać. Transport decyduje jak: in-process, argv, shell, Docker, HTTP, gRPC, kolejka, serverless, MCP lub A2A. Kontrakt i bramka policy zostają w jednym miejscu.',
        'transports' => $site['transports'],
        'docs_kicker' => 'docs://local/index/query',
        'docs_title' => 'Dokumentacja.',
        'docs' => $plDocs,
        'examples_kicker' => 'examples://repo/current/query',
        'examples_title' => 'Przykłady pokazujące współpracę warstw.',
        'examples_text' => 'Przykłady są małe celowo: pokazują, jak jedno registry obsługuje UI w przeglądarce, backend, usługi Docker, generatory i adaptery firmware.',
        'showcase_alt' => 'Cztery pulpity noVNC (pc1 controller, pc2 service-node, pc3 client-node, pc4 monitor-node) w jednym dashboardzie, każdy terminal pokazuje zdarzenia JSON z przepływu URI',
        'showcase_caption' => 'novnc_lan_flow: cztery komputery Docker komunikują się przez ten sam kontrakt URI (pc://…, log://…), pokazane razem w dashboardzie.',
        'examples' => $site['examples'],
        'roadmap_kicker' => 'todo://urirun/usability/query',
        'roadmap_title' => 'Następne prace nad użytecznością.',
        'roadmap' => [
            'urirun init dla startowego registry, policy i przykładowej trasy',
            'urirun doctor dla środowiska, zależności, portów i konfliktów tras',
            'urirun serve dla lokalnej przeglądarki tras, logów, dry-run console i policy-gated execution',
            'standardowe log:// w frontendzie, backendzie, shellu, firmware i przykładach Docker',
            'urirun diff do porównywania registry przed wdrożeniem',
        ],
        'naming_link' => 'Zasady nazewnictwa',
    ],
    [
        'lang' => 'en',
        'file' => __DIR__ . '/index.en.html',
        'title' => 'urirun - URI-addressed command runtime',
        'description' => 'urirun turns functions, scripts, containers, and services into reusable URI routes compiled into one registry.',
        'nav' => [
            'label' => 'Main navigation',
            'docs' => 'Docs',
            'workflow' => 'Workflow',
            'examples' => 'Examples',
            'language' => 'Language versions',
        ],
        'hero_kicker' => 'urirun://project/home',
        'hero_title' => 'One URI registry for commands across code, shell, containers, and services.',
        'hero_text' => 'Declare a route once, compile it into a registry, and call the same URI in-process or over HTTP, gRPC, a queue, serverless, Docker, MCP, or an A2A agent card.',
        'primary_cta' => 'Start with v8',
        'secondary_cta' => 'CLI commands',
        'quickstart_label' => 'Quick command sequence',
        'quickstart_short' => 'quickstart',
        'quickstart_title' => 'GitHub install',
        'facts_label' => 'Project facts',
        'facts' => [
            ['Runtime', 'urirun'],
            ['Repository', 'tellmesh/urihandler'],
            ['Default contract', 'v8 JSON Schema'],
            ['Execution', 'dry-run first'],
        ],
        'workflow_kicker' => 'flow://registry/build',
        'workflow_title' => 'Use existing artifacts as URI packages.',
        'workflow_text' => 'The useful path is not writing a new SDK. Point urirun at what your project already ships, generate bindings, validate the registry, and run by URI.',
        'workflow' => $site['workflow'],
        'features_kicker' => 'registry://local/value/query',
        'features_title' => 'What gets simpler.',
        'features' => $site['features'],
        'contract_kicker' => 'urirun://schema',
        'contract_title' => 'One contract, many runtimes.',
        'contract_text' => 'Packaging commands starts with a schema. A decorator, helper, or artifact scan generates a binding, then urirun compiles it into a registry and runs the same URI everywhere.',
        'schema_steps_label' => 'URI command creation process',
        'schema_steps' => [
            ['mark' => 'fn', 'title' => 'Write a function', 'text' => 'Types and defaults are the source of truth.'],
            ['mark' => '{ }', 'title' => 'Generate a binding', 'text' => 'inputSchema plus argv or shell template is emitted.'],
            ['mark' => '✓', 'title' => 'Compile registry', 'text' => 'Routes are validated and discoverable.'],
            ['mark' => '▶', 'title' => 'Run the URI', 'text' => 'Dry-run first; execute only after policy allows it.'],
        ],
        'tech_tabs_label' => 'Technologies that generate URI bindings',
        'declare_label' => 'declaration',
        'registry_label' => 'binding + registry',
        'tech_tabs' => $techTabsEn,
        'runtime_kicker' => 'transport://any/adapter/query',
        'runtime_title' => 'Same URI, different runtime.',
        'runtime_text' => 'A URI names what should run. The transport decides how it runs: in-process, argv, shell, Docker, HTTP, gRPC, a message queue, serverless, MCP, or A2A. The contract and the policy gate stay in one place.',
        'transports' => $site['transports'],
        'docs_kicker' => 'docs://local/index/query',
        'docs_title' => 'Documentation.',
        'docs' => $site['docs'],
        'examples_kicker' => 'examples://repo/current/query',
        'examples_title' => 'Examples that show the layers working together.',
        'examples_text' => 'The examples are intentionally small: they show how one registry can be used by browser UI, backend services, Docker workers, generators, and firmware-style adapters.',
        'showcase_alt' => 'Four noVNC desktops (pc1 controller, pc2 service-node, pc3 client-node, pc4 monitor-node) in one dashboard, each terminal streaming URI-flow JSON events',
        'showcase_caption' => 'novnc_lan_flow: four Docker computers communicating over one URI contract (pc://…, log://…), shown together in a dashboard.',
        'examples' => $site['examples'],
        'roadmap_kicker' => 'todo://urirun/usability/query',
        'roadmap_title' => 'Next usability work.',
        'roadmap' => $site['roadmap'],
        'naming_link' => 'Naming rules',
    ],
];

foreach ($pages as $page) {
    file_put_contents($page['file'], render_page($page, $site, $baseUrl, $repoUrl));
    echo 'Wrote ' . basename($page['file']) . PHP_EOL;
}

foreach (['en' => __DIR__ . '/docs', 'pl' => __DIR__ . '/docs/pl'] as $lang => $docsDir) {
    if (!is_dir($docsDir)) {
        mkdir($docsDir, 0o755, true);
    }
    $rel = $lang === 'pl' ? 'docs/pl/' : 'docs/';
    foreach (build_doc_pages($site, $repoUrl, $lang) as $slug => $docHtml) {
        file_put_contents($docsDir . '/' . $slug . '.html', $docHtml);
        echo 'Wrote ' . $rel . $slug . '.html' . PHP_EOL;
    }
}
