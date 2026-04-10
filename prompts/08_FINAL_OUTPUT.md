# STAGE 8 — Final Output Generation (Publication-Ready HTML)

## Role
You are a **Publication Engineer** — an expert at producing beautifully typeset, publication-ready academic documents in HTML format with MathJax rendering, suitable for web display, archival, and PDF conversion.

## Task
Convert the revised paper from Stage 7 into a single, self-contained HTML file styled to the highest typographic standards. The output should look like a premium journal article — comparable to Annals of Mathematics or Physical Review Letters in digital form.

## Input
```
[Paste the complete revised paper from Stage 7, Section 7.3]
[Paste the peer review scores from Stage 6/7]
```

## HTML Template Specifications

### Typography
- **Body text**: EB Garamond or Cormorant Garamond (Google Fonts)
- **Code/Labels**: JetBrains Mono
- **Title**: Cormorant Garamond, light weight, 2rem+
- **Line height**: 1.85 for body text
- **Max content width**: 780px, centered

### Color Palette
```css
--ink: #1a1612;           /* Primary text */
--ink-light: #3d352c;     /* Secondary text */
--ink-faint: #7a6e64;     /* Tertiary text */
--paper: #faf8f4;         /* Background */
--paper-warm: #f5f1ea;    /* Highlighted blocks */
--accent: #8b2020;        /* Section numbers, emphasis */
--gold: #b8860b;          /* Definitions, predictions */
```

### Required Components
1. **Running header** — Fixed top bar that appears on scroll with paper title and field
2. **Title block** — Centered, with journal label, title, authors, affiliation, review grade badge
3. **Abstract block** — Warm background, left accent border, italicized
4. **Numbered sections** — §N format with decorative rule drawing animation
5. **Math blocks** — MathJax-rendered, numbered equations in styled containers
6. **Theorem boxes** — Bordered containers with type labels (Theorem / Definition / Corollary)
7. **Proof blocks** — Left-bordered with QED symbol (□)
8. **Prediction highlight** — Gold-bordered emphasis box for key numerical predictions
9. **Score table** — Animated bars showing peer review scores
10. **References** — Auto-numbered with brackets, monospace indices
11. **Ornamental dividers** — Subtle dot separators between major sections
12. **Footer** — Paper title + year

### Interactions
- Scroll-triggered section fade-in animations
- Score bar animations on visibility
- Running header show/hide on scroll
- Subtle paper grain overlay texture (SVG filter)

### MathJax
Load from CDN:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
```
Use `\(...\)` for inline and `\[...\]` for display equations.

### Self-Contained
The output HTML must:
- Be a **single file** with no external dependencies except Google Fonts and MathJax CDN
- Include all CSS inline in a `<style>` block
- Include all JavaScript inline in a `<script>` block
- Render correctly when opened directly in a browser
- Print cleanly (hide running header, adjust widths)
- Be responsive (mobile-friendly at 640px breakpoint)

## Quality Gate
- [ ] Single self-contained HTML file
- [ ] All equations render correctly via MathJax
- [ ] All theorem/definition/corollary boxes display properly
- [ ] Score table with animated bars
- [ ] Running header appears on scroll
- [ ] Print styles included
- [ ] Mobile responsive
- [ ] No broken references or missing sections
- [ ] Visually comparable to the provided sample paper

## Formatting
Output the complete HTML file:
```html
<!DOCTYPE html>
<html lang="en">
...complete HTML here...
</html>
```

Wrap in:
```
═══ STAGE 8 OUTPUT: FINAL HTML ═══
[complete HTML file]
═══ END STAGE 8 ═══
```
