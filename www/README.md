# urirun website

The `www/` directory contains the static GitHub Pages site and the local PHP
documentation renderer.

Static Pages entry points:

- `/index.html` - Polish page with SEO `hreflang` links.
- `/index.en.html` - English page with SEO `hreflang` links.
- `/language.js` - remembers the last language selected without replacing the
  static page content.

Regenerate the static pages after editing copy or `site-data.php`:

```bash
php www/build-static.php
```

Serve the local PHP documentation site from the repository root:

```bash
php -S 127.0.0.1:8098 -t www
```

The site reads Markdown documents from `../docs/` and uses copied SVG logo
assets from `www/assets/`.

Routes:

- `/index.php` - project overview, quickstart, workflow, examples, and roadmap.
- `/docs.php?doc=getting-started` - Markdown docs rendered from `../docs/`.
- `/index.html` and `/index.en.html` - static pages for GitHub Pages.

Deployment:

- `.github/workflows/pages.yml` builds a static `_site` artifact from `www/`
  and uploads it to GitHub Pages.
- Enable GitHub Pages with source set to GitHub Actions in the repository
  settings.
