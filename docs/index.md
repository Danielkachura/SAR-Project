# Project Documentation Index

## SAR Ground Station Refactor

This repository contains the refactor of the SAR Ground Station system.

The documentation is organized into four main specification files:

---

## 1. Core Specifications

### Part A — Core System Specification
Use this document for:
- system overview
- features
- user flows
- architecture
- data models
- rules and constraints
- folder structure
- top-level modules

This is the architectural source of truth.

### Part B — Algorithms, Parameters, APIs
Use this document for:
- filter taxonomy
- parameter inventory
- rerun propagation rules
- calibration algorithm
- enrichment algorithm
- Re-ID algorithm
- localization algorithm
- API contracts

This is the runtime and algorithmic source of truth.

### Part C — Implementation Order, UI Skeleton, and AI Workflow
Use this document for:
- implementation order
- UI/page skeleton
- backend/frontend structure
- AI-assisted coding workflow
- prompt templates

This is the implementation-planning source of truth.

---

## 2. Agent Instructions

### AGENTS.md
This file defines the working rules for coding agents.

It covers:
- source priority
- documentation policy
- implementation rules
- rerun discipline
- current project priority

All coding agents should read this before starting work.

---

## 3. Source Priority

When implementing or reviewing code, always follow this priority:

1. Part A — Core System Specification
2. Part B — Algorithms, Parameters, APIs
3. Part C — Implementation Order, UI Skeleton, and AI Workflow
4. Legacy codebase — reference only, never authoritative

If legacy behavior conflicts with the specification, the specification wins.

---

## 4. Implementation Strategy

Recommended high-level order:

1. repo skeleton
2. session/inventory/artifact plumbing
3. Overview
4. Calibration
5. Enrichment
6. Re-ID
7. Localization
8. Result Analysis
9. Save/Resume
10. hardening and regression checks

Do not attempt full end-to-end generation of the whole system in one task.

---

## 5. Documentation Maintenance Rule

When changing any:
- top-level module
- canonical model
- public API group
- algorithm

update the matching Markdown document in `/docs` during the same task.

Do not create documentation for trivial helper files unless they expose important behavior.

---

## 6. Recommended Starting Task

Recommended first implementation slice:

- backend/frontend repository skeleton
- canonical models skeleton
- session state skeleton
- scan folder listing from DATA
- session creation from selected folder
- mode detection + manual override
- folder inventory listing
- artifact classification
- artifact activation
- stage jump suggestion
- API skeleton for these flows
- basic frontend shells for Session Start and Overview

---

## 7. Notes

- Treat `*_ENRICHED.csv` and `*_REID.csv` as official artifacts
- Keep `TEMP` non-persistent
- Save/resume must not depend on reconstructing missing TEMP artifacts
- Do not invent numeric defaults marked TBD
- Leave explicit TODOs where the specification says TBD
