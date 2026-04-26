# Project Documentation Index

## SAR Ground Station Refactor

This repository contains the refactor of the SAR Ground Station system.

## 1. Core Specifications
- [Part A — Core System Specification](./Part%20A.md)
- [Part B — Algorithms, Parameters, APIs](./Part%20B.md)
- [Part C — Implementation Order, UI Skeleton, and AI Workflow](./Part%20C.md)

## 2. Implemented Module Docs
- [MOD-001 App Session & Navigation](./mod-001-session-navigation.md)
- [MOD-002 Dataset Discovery & Artifact Resolver](./mod-002-dataset-discovery-artifact-resolver.md)
- [MOD-005 Overview Module](./mod-005-overview-module.md)
- [MOD-006 Calibration Module](./mod-006-calibration-module.md)
- [MOD-007 Enrichment Module](./mod-007-enrichment-module.md)
- [MOD-008 Re-ID Module](./mod-008-reid-module.md)
- [MOD-009 Localization Module](./mod-009-localization-module.md)
- [MOD-010 Spatial Presentation Module](./mod-010-spatial-presentation.md)
- [MOD-010 Spatial Presentation (Overview Subset)](./mod-010-spatial-presentation-overview-subset.md)
- [MOD-012 Artifact Management](./mod-012-artifact-management.md)
- [MOD-013 Save / Resume (Skeleton)](./mod-013-save-resume-skeleton.md)
- [MOD-014 Canonical Models & Schema](./mod-014-canonical-models-schema.md)

## 3. API and Frontend Docs
- [API Contracts — Phase 0 + Phase 1 + Phase 2 (Overview) + Phase 3 (Calibration)](./api-phase0-phase1.md)
- [Frontend — Session Start + Overview + Calibration (Phase 3 state)](./frontend-session-start-overview-skeleton.md)

## 4. Source Priority
1. Part A — Core System Specification
2. Part B — Algorithms, Parameters, APIs
3. Part C — Implementation Order, UI Skeleton, and AI Coding Workflow
4. Legacy codebase — reference only, never authoritative

## 5. Notes
- Treat `*_ENRICHED.csv` and `*_REID.csv` as official artifacts.
- Keep `TEMP` non-persistent.
- Save/resume must not depend on reconstructing missing TEMP artifacts.
- Leave explicit TODO markers for spec TBDs and deferred phase behavior.
