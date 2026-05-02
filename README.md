# Patentis Marketing Site

Production-style static marketing website for **Patentis**, an AI-powered patent whitespace discovery platform.

## Stack

- Pure HTML/CSS/JS (no frameworks, no build tools)
- Google Fonts (`Inter`)
- Designed for static hosting on GitHub Pages

## Local preview

Because this is a static site, you can open `index.html` directly in a browser.  
For a cleaner local server workflow:

```bash
cd patentis-website
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Live site (GitHub Pages)

Public repo: **https://github.com/DarthJarJarBinks-Meesa/patentis-website**

After you enable Pages (below), the site will be at:

**https://darthjarjarbinks-meesa.github.io/patentis-website/**

Canonical URLs, Open Graph, `robots.txt`, and `sitemap.xml` already use that origin.

## Deploy to GitHub Pages

### Option A: Deploy from `main` branch

1. Repository: https://github.com/DarthJarJarBinks-Meesa/patentis-website (`main` branch).
2. In GitHub, open **Settings -> Pages**.
3. Under **Build and deployment**:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main`
   - **Folder**: `/ (root)`
4. Save settings and wait for the Pages URL to be published.

### Option B: Deploy from `gh-pages` branch

1. Commit your site files on `main`.
2. Create and switch to deployment branch:

   ```bash
   git checkout -b gh-pages
   ```

3. Push branch:

   ```bash
   git push -u origin gh-pages
   ```

4. In GitHub **Settings -> Pages**, choose:
   - **Source**: `Deploy from a branch`
   - **Branch**: `gh-pages`
   - **Folder**: `/ (root)`
5. Save and use the generated Pages URL.

## SEO, robots, and sharing

The HTML pages include `<meta name="description">`, canonical URLs, Open Graph tags, Twitter summary tags, and JSON-LD (`Organization`) on the home page. Absolute URLs point at `https://darthjarjarbinks-meesa.github.io/patentis-website`.

**Optional social preview image:** add a `og-image.png` (about 1200×630) to the site root, then add to each page’s `<head>`:

- `<meta property="og:image" content="YOUR_URL/og-image.png">`
- `<meta name="twitter:image" content="YOUR_URL/og-image.png">` and set `twitter:card` to `summary_large_image` if you use it.

## Files

- `index.html` - Home page with interactive patent node graph canvas
- `about.html` - Team and mission
- `potential.html` - Market scale, buyers, roadmap
- `model.html` - Under-construction model page
- `contact.html` - Contact information
- `styles.css` - Shared visual system and responsive layout
- `script.js` - Canvas animation, intersection reveals, counters, mobile nav
- `robots.txt` - Crawler rules and sitemap pointer
- `sitemap.xml` - URL list for search engines
