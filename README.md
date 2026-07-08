# Test-Project

## Interactive Family Tree

A self-contained, dependency-free family tree app in a single file: [`index.html`](index.html). Open it in any modern browser — no build step, no server required.

### Features

- **Visual tree** — automatic generational layout with marriage lines and sibling connectors, rendered as SVG
- **Pan & zoom** — drag the canvas to pan, scroll to zoom, plus zoom buttons and a "Fit view" control
- **Click to edit** — select any person to edit their name, birth/death years, gender, and notes in the sidebar
- **Build the tree** — add spouses, children, and parents from the sidebar; navigate between relatives with one click
- **Search** — find anyone by name and jump straight to them
- **Persistence** — the tree is saved to your browser's localStorage automatically
- **Export / Import** — download the tree as JSON and load it back later or on another machine
- **Sample data** — ships with a three-generation example family; restore it anytime with the "Sample data" button
- **Dark mode** — follows your system color scheme

### Usage

Open `index.html` directly, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```
