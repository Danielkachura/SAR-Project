# Project Documentation Index

## SAR Ground Station Refactor

This repository contains the refactor of the SAR Ground Station system.

## 1. Core Specifications
- [Part A — Core System Specification](./Part%20A.md)
- [Part B — Algorithms, Parameters, APIs](./Part%20B.md)
- [Part C — Implementation Order, UI Skeleton, and AI Workflow](./Part%20C.md)

## 2. Phase 0 + Phase 1 Foundation Docs
- [MOD-001 App Session & Navigation (Phase 0-1)](./mod-001-session-navigation.md)
- [MOD-002 Dataset Discovery & Artifact Resolver (Phase 0-1)](./mod-002-dataset-discovery-artifact-resolver.md)
- [MOD-012 Artifact Management (Phase 0-1)](./mod-012-artifact-management.md)
- [MOD-013 Save / Resume (Skeleton)](./mod-013-save-resume-skeleton.md)
- [MOD-014 Canonical Models & Schema (Phase 0-1)](./mod-014-canonical-models-schema.md)
- [API Contracts — Phase 0 + Phase 1 Foundation](./api-phase0-phase1.md)
- [Frontend Skeleton — Session Start + Overview (Phase 0-1)](./frontend-session-start-overview-skeleton.md)

## 3. Source Priority
1. Part A — Core System Specification
2. Part B — Algorithms, Parameters, APIs
3. Part C — Implementation Order, UI Skeleton, and AI Workflow
4. Legacy codebase — reference only, never authoritative

## 4. Notes
- Treat `*_ENRICHED.csv` and `*_REID.csv` as official artifacts.
- Keep `TEMP` non-persistent.
- Save/resume must not depend on reconstructing missing TEMP artifacts.
- Leave explicit TODO markers for any spec `TBD` and incomplete phase behavior.
