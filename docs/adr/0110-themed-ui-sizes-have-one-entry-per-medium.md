---
status: accepted
---

# Themed UI sizes have one entry per medium

ADR 0103 made the layout theme own application sizing, but icons kept pixel
props, preview gizmo handles and timeline hit zones stayed fixed, and JS
geometry multiplied scattered literals by the scale. On larger presets text
grew while its icons, header column and grab targets did not.

Every themed size now enters through one place per medium. CSS uses `--ui-px`
and the role tokens in `styles/layout-theme.css`. Icons render through
`components/AppIcon` with a role named after the text role they accompany
(`micro` … `display`); the baseline sizes match the old pixel props, so the
1080p Standard theme is unchanged. JS geometry declares its baselines in
`settings/uiMetrics.ts` and resolves them through `layoutTheme.ts`:
`uiPixels()` for boxes, constraints and hit zones, `uiScaled()` for fractional
SVG geometry.

This covers the preview transform gizmo, the timeline header column, trim edge
zone, clip label, marker lane, keyframe sub-lanes and curve handles, ruler label
spacing, and track heights. Track
heights persist in baseline units, like the agent record and log console drag
sizes, so a dragged row keeps its proportion to the text inside it when the
theme changes; existing saved heights read as baselines, which is identical at
1080p Standard.

Composition and time-axis coordinates, render tiles, stroke widths, borders,
shadows and native window chrome stay in real pixels. A CSS length that must
stay fixed carries a same-line `/* fixed-px: <reason> */` marker.
`settings/uiSizing.test.ts` rejects unmarked CSS pixel lengths, pixel icon sizes,
lucide glyphs rendered without AppIcon, and literal numbers in UI-scale
arithmetic.
