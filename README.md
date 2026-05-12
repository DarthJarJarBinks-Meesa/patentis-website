# Patentis

AI-powered patent whitespace discovery platform.

**Live site:** https://darthjarjarbinks-meesa.github.io/patentis-website/

**Open-source prototype:** https://github.com/Natheoah/patentisv1

---

## Repository structure

```
patentis-website/
├── index.html          # Landing page
├── about.html          # Team & mission
├── potential.html      # Market & opportunity
├── model.html          # Demo / open-source prototype
├── contact.html        # Contact
├── styles.css
├── script.js
├── robots.txt
├── sitemap.xml
└── app/                # Full-stack prototype (Python + React)
    ├── backend/        # FastAPI + Groq LLM + patent search APIs
    ├── frontend/       # React + TypeScript + Vite
    └── start.sh        # One-command startup
```

## Running the app locally

```bash
cd app
./start.sh
```

Requires Python 3.11+, Node.js 18+, and a free [Groq API key](https://console.groq.com).
Enter the key on the app's home screen when prompted.

## Website

Static HTML/CSS/JS — no build step. Edit the `.html` files and push; GitHub Pages deploys automatically.
