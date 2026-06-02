# About Page Rewrite - Design Spec (2026-06-02)

## Goal
- Rewrite About page copy to be fuller and more product-focused while keeping a friendly tone.
- Fix the desktop alignment issue in the Vision section by stacking the content in a single column.

## Non-goals
- No new sections or routes.
- No new data sources or state changes.
- No changes to app navigation.

## Scope and locations
- Component: frontend/src/components/AppPages.tsx (AboutPage)
- Styles: frontend/src/styles.css (.about-section)

## Design summary
- Keep the existing structure: hero + feature grid + vision block.
- Expand hero and feature copy to balance vision, product value, and usage flow.
- Update the vision block to be a single column on desktop to remove the current misalignment.

## Content outline (draft)
- Hero
  - Eyebrow: friendly, community-driven tone.
  - Headline: position the product as a visual, interactive math space.
  - Body: 2-3 sentences explaining purpose, benefits, and how users explore.
- Feature grid (4 cards)
  - Each card: 1-line title + 1-2 sentences describing a concrete outcome.
- Vision block
  - Label: "Tam nhin".
  - Title: "Toan hoc khong chi la nhung con so".
  - Body: 2 sentences about observing, interacting, and self-directed discovery.

## Layout adjustments
- Change .about-section to a single-column layout on desktop (no two-column split).
- Keep existing top border and spacing rules.
- Ensure the text width remains readable (use existing max widths or add a safe max width if needed).

## Error handling and data flow
- No data flow changes. Static content only.

## Testing and verification
- Visual check on desktop: vision block stacks correctly, no offset between title and body.
- Visual check on mobile: layout remains single-column and readable.

## Rollout
- Safe to ship as a front-end content and layout change only.
