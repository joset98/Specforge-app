# Design

World: an engineering workbench. Calm drafting paper in light mode, graphite ink in dark mode (follows the OS). One accent, forge ember, used only for live or attention states (the active pipeline step, retries, primary action). No gradients, glows or decorative blur.

- Type: Instrument Sans (UI, headings), JetBrains Mono only for real code/data (Gherkin, paths, SQL-ish names, ids, logs).
- Color tokens on `:root` (light) and `prefers-color-scheme: dark`; neutrals tinted warm.
- Elevation: borders only, no shadows except the sticky input panel on scroll.
- Radii: 10px panels, 6px controls, pills only for small badges.
- Icons: lucide-react, 1.75 stroke.
- Motion: one authored moment, the pipeline step becoming active; everything else instant.
