\# SAR Ground Station Spec --- Part C \## Implementation Order, UI
Skeleton, and AI Coding Workflow

\> This document is the practical bridge from the specification to
implementation. \> It assumes Part A and Part B are the source of truth
and defines: \> - implementation order \> - UI/page skeleton \> -
recommended AI-assisted coding workflow \> - prompt templates for staged
implementation

\-\--

\## 1. Purpose of Part C

This part exists to reduce implementation risk.

It defines: - the recommended build order - which parts should be
implemented first - which parts depend on others - which parts can stay
stubbed or TODO at first - how to work safely with coding agents

This part SHALL NOT override Parts A or B.

\-\--

\## 2. Recommended Implementation Strategy

\### 2.1 General Principle Implement the system in \*\*vertical
slices\*\*, but in a dependency-safe order.

Do \*\*not\*\* begin by implementing all algorithms first. Do
\*\*not\*\* begin by implementing all UI first. Do \*\*not\*\* ask an AI
engine to build the entire system in one step.

Instead: 1. establish backend and frontend skeletons 2. implement
state/session/inventory plumbing 3. implement lightweight pages first 4.
then add pipeline stages one by one 5. add heavy algorithms only after
their data contracts and UI entry points already exist

\-\--

\## 3. Recommended Build Order

\## Phase 0 --- Repo and Architecture Skeleton Goal: - create the
project structure - enforce module boundaries - create canonical models
and state containers - prepare backend/frontend separation

\### Deliverables - repository structure - backend app skeleton -
frontend app skeleton - canonical model definitions - session state
model - API route skeletons - test skeleton

\### Acceptance Criteria - project runs - session can be created - no
algorithms required yet - placeholder endpoints/pages may return stub
data

\-\--

\## Phase 1 --- Session, Inventory, and Artifact Plumbing Goal: - make
the system aware of scan folders, files, artifacts, active session state

\### Modules - MOD-001 App Session & Navigation - MOD-002 Dataset
Discovery & Artifact Resolver - MOD-012 Artifact Management - MOD-013
Save / Resume Module - MOD-014 Canonical Models & Schema Module

\### Deliverables - list DATA folders - create session from selected
folder - detect/override mode - list inventory - activate existing
artifact - stage jump suggestion - save/load state skeleton

\### Acceptance Criteria - user can select a folder - session state
persists correctly - inventory is visible - official artifacts can be
activated immediately

\-\--

\## Phase 2 --- Overview Goal: - make the app useful early, with
lightweight inspection and no heavy processing

\### Modules - MOD-005 Overview Module - MOD-010 Spatial Presentation
Module (basic subset only)

\### Deliverables - Overview page - CSV selector - summary statistics -
preview table - basic charts - spatial inspection section - device
inspection section - hover metadata on points

\### Acceptance Criteria - Overview opens automatically after folder
selection - no file-level outputs before CSV selection - CSV-level
outputs appear after file selection - no enrichment / re-id /
localization required yet

\-\--

\## Phase 3 --- Calibration Goal: - provide session-level parameter
derivation and fallback selection

\### Modules - MOD-006 Calibration Module - relevant subset of MOD-010
Spatial Presentation Module

\### Deliverables - calibration CSV dropdown - MAC selection - GT mode
selection - manual map click GT - scatter plot - linear regression -
optional RANSAC - fallback presets - approval flow

\### Acceptance Criteria - user can derive and approve calibration -
user can choose fallback instead - approved session calibration is
stored and reused

\-\--

\## Phase 4 --- Enrichment Goal: - convert raw CSV + matching PCAP into
official ENRICHED artifact

\### Modules - MOD-007 Enrichment Module - artifact plumbing

\### Deliverables - enrichment execution endpoint - PCAP parsing -
matching index - row-level matching - diagnostics fields - quality
stats - official ENRICHED artifact writing

\### Acceptance Criteria - matching PCAP required - ENRICHED artifact
written correctly - overwrite is silent - row-level diagnostics are
preserved - BLE enrichment fields exist in schema

\-\--

\## Phase 5 --- Re-ID Goal: - generate \`cluster_id\` and
\`cluster_type\`

\### Modules - MOD-008 Re-ID Engine

\### Deliverables - static MAC bypass - candidate generation -
protocol-specific feature extraction - weighted association scoring -
thresholding - greedy conflict resolution - dynamic cluster generation -
REID artifact writing

\### Acceptance Criteria - every relevant output row has
\`cluster_id\` - every relevant output row has \`cluster_type\` - static
rows bypass dynamic association - Wi-Fi uses legacy-aligned feature
families and defaults - BLE uses starter feature family set

\-\--

\## Phase 6 --- Localization Goal: - compute multi-target localization
and build consumable result object

\### Modules - MOD-009 Localization Engine - MOD-010 Spatial
Presentation Module (full localization subset)

\### Deliverables - search-area resolution - pre-localization filters -
optional RANSAC pre-cleaning - grid building - likelihood/heatmap
computation - candidate peaks - uncertainty region generation - computed
localization result object - layered map rendering

\### Acceptance Criteria - localization can run on full REID or filtered
subset - cluster failures do not kill successful clusters - one-to-three
reported uncertainty regions per cluster - view controls do not trigger
rerun

\-\--

\## Phase 7 --- Result Analysis Goal: - move from "system works" to
"system can be evaluated and tuned"

\### Modules - MOD-011 Result Analysis Module - MOD-010 Spatial
Presentation Module (analysis tools subset)

\### Deliverables - ground truth import - map-based ground truth
placement - delete/clear GT - evaluation metrics - numeric score - rerun
orchestration - future advanced parameter placeholders

\### Acceptance Criteria - Ground Truth exists only here - quality
metrics are computed - score is computed - rerun affects only required
stages

\-\--

\## Phase 8 --- Save / Resume Full Session Goal: - persist real analysis
sessions independent of TEMP

\### Deliverables - save current session into \`Saved Scans\` - restore
saved session - restore current result, GT, parameters, and view state

\### Acceptance Criteria - resume does not depend on missing TEMP
artifacts - restored session opens correctly

\-\--

\## Phase 9 --- Hardening and Legacy Parity Check Goal: - validate
parity and remove hidden divergence

\### Deliverables - regression suite - fixture scans - side-by-side
comparisons against legacy outputs - performance profiling - TODO/TBD
review

\-\--

\## 4. Recommended UI Skeleton

\## 4.1 Global App Shell Suggested persistent layout: - top header -
left navigation / stage navigation - main content area - optional
right-side contextual controls panel - global status / warnings bar

\### Suggested persistent header items - active session name - active
folder - active mode - active artifact summary - save session action -
current warnings badge

\-\--

\## 4.2 Page Skeletons

\### Page 1 --- Session Start / Folder Selection Sections: 1. folder
dropdown 2. mode detection display 3. manual mode override 4. folder
warnings 5. open/continue context summary

Primary actions: - select folder - override mode

Expected outcome: - auto-transition to Overview

\-\--

\### Page 2 --- Overview Sections: 1. selected CSV dropdown 2. summary
stats cards 3. statistical charts 4. preview table 5. spatial inspection
map 6. device inspection panel

Controls: - global filters panel - selected CSV - chart granularity if
needed later

Map behavior: - hover point -\> show cluster and minimal metadata

\-\--

\### Page 3 --- Calibration Sections: 1. calibration CSV dropdown 2. MAC
dropdown 3. GT mode selector 4. GT controls 5. calibration plot 6.
fit-quality panel 7. derived parameters panel 8. fallback presets panel

Primary actions: - run calibration - approve derived calibration -
choose fallback preset

\-\--

\### Page 4 --- Re-ID & Enrichment Sections: 1. scan CSV/artifact
dropdown 2. PCAP match status 3. official artifact detection 4.
enrichment controls 5. enrichment quality panel 6. Re-ID parameter panel
7. Re-ID run status 8. REID summary panel

Primary actions: - run enrichment - run re-id - activate existing
ENRICHED / REID artifact

\-\--

\### Page 5 --- Localization Sections: 1. active REID artifact selector
2. pre-localization filter panel 3. localization parameter panel 4.
bounds selection controls 5. run localization action 6. layered map view
7. cluster result summary table 8. warnings panel

Map layer controls: - show/hide heatmap - show/hide grid - show/hide
radii - show/hide peaks - show all / hide all / per-cluster visibility

\-\--

\### Page 6 --- Result Analysis Sections: 1. current result summary 2.
ground truth management panel 3. analysis metric panel 4. numeric score
panel 5. findings / warnings panel 6. rerun controls 7. advanced
parameter exposure (future/conditional) 8. analysis map

Map analysis tools: - add GT from map - inspect clusters - distance
measurement - show/hide GT - focus on selected cluster or GT point

\-\--

\## 4.3 User-Facing vs Research-Facing Separation Operational users
should mostly need: - folder selection - overview - calibration -
enrichment / re-id - localization

Research users additionally need: - result analysis - advanced rerun
controls - score tuning - future internal parameter tuning

The UI SHOULD make this distinction visible.

Suggested approach: - mark Result Analysis as \`Research / Tuning\` -
keep advanced controls collapsed by default

\-\--

\## 5. Suggested Backend / Frontend Skeleton

\## 5.1 Backend Suggested Structure \`\`\`text backend/ ├── app/ │ ├──
api/ │ ├── core/ │ ├── modules/ │ ├── models/ │ ├── services/ │ ├──
storage/ │ └── main.py ├── tests/ └── requirements.txt \`\`\`

\### Suggested substructure \`\`\`text backend/app/ ├── api/ │ ├──
sessions.py │ ├── inventory.py │ ├── overview.py │ ├── calibration.py │
├── enrichment.py │ ├── reid.py │ ├── localization.py │ ├──
result_analysis.py │ ├── saved_sessions.py │ └── executions.py ├──
modules/ │ ├── session_navigation/ │ ├── dataset_discovery/ │ ├──
normalization/ │ ├── global_filters/ │ ├── overview/ │ ├── calibration/
│ ├── enrichment/ │ ├── reid/ │ ├── localization/ │ ├──
spatial_presentation/ │ ├── result_analysis/ │ ├── artifact_management/
│ └── save_resume/ ├── models/ │ ├── canonical_models.py │ ├──
api_models.py │ └── parameter_models.py └── storage/ ├── data_paths.py
├── temp_storage.py └── saved_sessions.py \`\`\`

\-\--

\## 5.2 Frontend Suggested Structure \`\`\`text frontend/ ├── src/ │ ├──
app/ │ ├── pages/ │ ├── components/ │ ├── features/ │ ├── api/ │ ├──
state/ │ └── types/ ├── public/ └── package.json \`\`\`

\### Suggested page structure \`\`\`text frontend/src/pages/ ├──
SessionStartPage.tsx ├── OverviewPage.tsx ├── CalibrationPage.tsx ├──
ReIdEnrichmentPage.tsx ├── LocalizationPage.tsx └──
ResultAnalysisPage.tsx \`\`\`

\### Suggested shared components \`\`\`text frontend/src/components/ ├──
layout/ ├── tables/ ├── charts/ ├── maps/ ├── forms/ ├── filters/ ├──
status/ └── artifacts/ \`\`\`

\-\--

\## 6. Working with AI Coding Agents

\## 6.1 Core Rule Never ask the agent to implement the whole system at
once.

Always give: - one module or one vertical slice - source-of-truth docs -
explicit acceptance criteria - strict no-assumptions rule

\-\--

\## 6.2 Recommended Agent Workflow

\### Primary implementation agent Use one main agent for writing code.

\### Secondary review agent Optionally use a second agent only for: -
review - diff checking - spec compliance checking

Do \*\*not\*\* have two agents write the same module independently at
the same time.

\-\--

\## 6.3 Task Size Rule Each task should be small enough that you can
verify: - touched files - module boundary - tests - TODOs - assumptions
avoided

Good task size: - one module - or one page + one backend contract - or
one execution flow end-to-end

Bad task size: - the whole system - all backend - all frontend - "build
everything from spec"

\-\--

\## 6.4 Required Prompt Rules for Every Coding Task Always tell the
agent: - Part A and Part B are source of truth - do not add features not
specified - do not invent numeric defaults marked TBD - if something is
TBD, leave a clear TODO - list files to create/modify first - keep
module boundaries strict - include tests - explain any remaining
assumptions explicitly

\-\--

\## 7. Prompt Templates

\## 7.1 Repo Skeleton Prompt \`\`\`text Use Part A and Part B as the
source of truth.

Task: Create the backend/frontend skeleton only. Do not implement heavy
algorithms yet.

Requirements: - strict module boundaries - canonical models package -
session-aware API layout - execution model skeleton - frontend page
skeletons - tests only for skeleton viability

Before writing code: 1. list files you will create 2. explain how the
structure maps to the modules in Part A 3. identify every TODO you will
leave \`\`\`

\-\--

\## 7.2 Module Prompt \`\`\`text Use Part A and Part B as the source of
truth.

Task: Implement MOD-002 Dataset Discovery & Artifact Resolver.

Acceptance criteria: - list DATA subfolders - list CSV/PCAP/artifacts in
selected folder - classify raw/enriched/reid files - activate selected
artifact immediately - provide stage jump suggestions - include tests

Rules: - do not add behavior not in the spec - do not invent unsupported
file types - if a detail is TBD, leave TODO - list files before writing
code \`\`\`

\-\--

\## 7.3 Algorithm Prompt \`\`\`text Use Part A and Part B as the source
of truth.

Task: Implement the Enrichment Algorithm only.

Acceptance criteria: - parse matching PCAP - normalize extracted frame
fields - build searchable PCAP index - match CSV rows to PCAP frames -
write official ENRICHED artifact - preserve row-level diagnostics:  -
match_found  - match_delta_ms  - match_score  - match_method - include
tests

Rules: - no clustering - no localization - no UI logic - no extra fields
beyond approved schema unless marked TODO \`\`\`

\-\--

\## 7.4 Review Prompt \`\`\`text Review the attached implementation
against Part A and Part B.

Do not rewrite the code.

Return: 1. spec mismatches 2. hidden assumptions 3. module-boundary
violations 4. missing tests 5. risky TODOs 6. places where behavior
diverges from artifact lifecycle or rerun rules \`\`\`

\-\--

\## 8. First Recommended Coding Tasks

Recommended exact order for AI-assisted implementation:

1\. backend/frontend skeleton 2. canonical models + session state 3.
DATA inventory + artifact activation 4. Overview backend + Overview
frontend 5. Calibration backend + calibration page 6. Enrichment backend
7. Re-ID backend 8. Localization backend 9. Spatial presentation shared
map layer 10. Result Analysis backend + page 11. Save/resume 12.
hardening + regression comparisons

\-\--

\## 9. What Can Stay TODO Initially These should not block
implementation start: - exact legacy numeric defaults not yet
extracted - BLE starter defaults - exact score weights - full
advanced/internal parameter inventory - future live connectivity page -
future score submodels beyond current official score framework

These SHALL be marked clearly as TODO/TBD in code.

\-\--

\## 10. Definition of "Ready to Start Coding" The project is ready to
start coding when: - Part A is preserved - Part B is preserved -
implementation order is accepted - first coding task is scoped
narrowly - agent prompt is strict - acceptance criteria exist

This condition is now satisfied.
