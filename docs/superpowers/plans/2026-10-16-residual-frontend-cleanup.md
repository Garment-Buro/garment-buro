# Residual Frontend Cleanup Implementation Plan

> **For agentic workers:** Execute inline with superpowers:executing-plans, preserving the existing dirty checkout. No commit, push, deployment, or user-data deletion in this stage.

**Goal:** Remove unreachable demo sources, obsolete local pricing fields, and the unselected legacy collapsed cart presentation without changing current screens.

**Architecture:** Keep the shared CartActionBar used by both current presentations (`glass-compact`, `liquid-v2`). Panel reveal geometry is shared and no longer needs a variant argument. Constructor placement geometry remains independent of server pricing.

**Tech Stack:** TypeScript, Next.js 16, React 19, Node test runner.

**Spec:** Existing release scope in docs/release-refactoring.md; current customization pricing specification in docs/superpowers/specs/2026-10-16-customization-pricing.md.

## Constraints

- Preserve the accepted server price rule: minimum 80 RUB, current scale formula.
- Preserve legacy draft reading/migration and referenced images; historical snapshots can contain `/mock/` URLs.
- Preserve current cart appearance, interaction, checkout and account boundaries.
- Delete only files verified to have no imports, dynamic imports or symbol consumers.
- No new dependencies and no backend changes.

## Task 1: Delete unreachable sources and pricing fields

- [x] Search full frontend for defaultDecorations/createRepeatedHardware/DRAFT_PREVIEW_FIXTURES/COLLECTION_PREVIEW_FIXTURES and verify imports.
- [x] Delete frontend/lib/constructor/config/defaultDecorations.ts, frontend/lib/constructor/utils/data.ts and frontend/lib/unfinished/fixtures/savedItems.ts.
- [x] Remove write-only PlacedHardware.baseLongSideCm and HardwareVariant.basePrice from types, constructor restoration and controller. Keep priceResource.basePrice (actual Product price), geometry dimensions and scale limits.
- [x] Run constructor geometry/customization, draft and pricing tests.

## Task 2: Retire the unselected cart presentation

- [x] Cover collapsed/expanded endpoints, mid-drag reveal and both drag bounds with real getCartPanelPresentation output assertions before simplification.
- [x] Remove legacy from CartCollapsedVariant, legacy count badge and unreachable collapsed glow. Remove only their unused constants.
- [x] Remove collapsedVariant from getCartPanelPresentation and its one controller caller; share existing compact reveal math between current presentations.
- [x] Remove obsolete source assertions requiring legacy code; preserve unrelated assertions for current visuals.
- [x] Run full frontend tests, lint and production build; review current variants and saved-project compatibility.

## Task 3: Refresh the project map

- [x] Record exact retired files and preserve the distinction between shared cart implementation and V2 presentation.
- [x] Refresh AST graph/file explanations, export offline HTML, and run map browser checks.
- [x] Record verified results and any limitations in docs/release-refactoring.md.
