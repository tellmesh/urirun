# urirun website

Static, GitHub-Pages-friendly site generated from a single content source. There
is **one homepage** and **no PHP at serve time** - PHP only runs at build time to
generate the static files.

## Files

- `index.html` / `index.en.html` - generated landing pages (PL / EN).
- `docs/` - one generated HTML page per `../docs/*.md` (e.g. `docs/transports.html`).
- `style.css`, `language.js`, `assets/` - styles, language switch, logo + images.
- `site-data.php` - the single content source.
- `build-static.php` - generator: reads `site-data.php` + `../docs/*.md` and
  writes `index.html`, `index.en.html`, and `docs.html`.

## Build

```bash
php www/build-static.php   # regenerates index.html, index.en.html, docs/*.html
```

The committed `*.html` files are the build output.

## Preview locally

```bash
python3 -m http.server 8099 -d www   # http://127.0.0.1:8099/
```

## Deploy

`.github/workflows/pages.yml` copies the static files (`index.html`,
`index.en.html`, `docs/`, `language.js`, `style.css`, `assets/`, `.nojekyll`)
into `_site` and publishes them to GitHub Pages. Enable Pages with the source set
to GitHub Actions.
