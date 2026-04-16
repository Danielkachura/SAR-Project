\# SAR Ground Station Spec --- Part A \## Core System Specification

\> This document is the preserved \*\*Part A\*\* of the Ground Station
specification. \> It contains the architectural and workflow core of the
system. \> Runtime logic, algorithms, parameters, and API contracts are
maintained separately in \*\*Part B\*\*.

\-\--

\## 1. Overview

\### 1.1 Purpose This specification defines the refactored Ground
Station system for the SAR RF scanning and localization project.

The refactor SHALL: - preserve required legacy capabilities - remove
duplication and unclear behavior - define one clear source of truth -
support gradual replacement of legacy logic using a strangler-style
migration

\### 1.2 Refactor Principles The refactor SHALL follow these
principles: - no blind rewrite - no undocumented assumptions - no
unauthorized feature additions - strict modularity - strict data and
interface contracts - explicit state ownership - explicit artifact
lifecycle - support for backend/frontend architecture

\### 1.3 System Purpose The Ground Station SHALL: - load scan folders
from \`DATA\` - detect or accept manual protocol mode (\`Wi-Fi\` /
\`BLE\`) - support lightweight Overview inspection - derive or select
calibration parameters - enrich scan CSV files using matching PCAP
files - run Re-ID on enriched artifacts - run localization on Re-ID
artifacts - present localization results as layered maps - support
Result Analysis for quality evaluation, rerun, and research workflows -
support save/resume of sessions

\### 1.4 User Groups The system SHALL support two usage profiles:

\#### End-User / Operational Usage Primarily intended for SAR teams and
operational users: - folder selection - overview - calibration -
enrichment - Re-ID - localization - map inspection

\#### Research / Tuning Usage Primarily intended for the development
team: - Result Analysis - ground-truth placement - rerun with
alternative filters/parameters - quality evaluation - future parameter
optimization workflows

\### 1.5 Scope Boundary This specification applies to the \*\*Ground
Station\*\* only.

The \*\*Air Unit / Airborne side\*\* is included only as reference
context: - file formats - export structure - naming expectations -
expected data content

The Air Unit SHALL NOT be modified as part of this refactor scope.

\-\--

\## 2. Feature Inventory

\### 2.1 Feature List - F-001 Scan Folder Discovery, Mode Detection &
Manual Override - F-002 Overview Dashboard - F-003 Calibration - F-004
Scan File Selection - F-005 Enrichment from Matching PCAP - F-006 Re-ID
Execution - F-007 Localization Filtering, Computation & Map
Presentation - F-008 Save Session - F-009 Result Analysis & Final-Stage
Re-Run

\-\--

\## 3. User Flows

\### UF-001 Select Scan Folder and Resolve Mode

\#### Actor User

\#### Goal Select one scan folder from \`DATA\` and enter the correct
mode context

\#### Entry Conditions - \`DATA\` directory is accessible - At least one
subfolder exists under \`DATA\`

\#### Steps 1. System lists all subfolders in \`DATA\` 2. User selects
one folder 3. System loads the selected folder immediately 4. System
detects mode from folder name 5. User MAY override mode manually 6.
System opens the Overview page automatically

\#### Exit Conditions - active scan folder exists - active mode exists -
Overview page is open

\#### Error Paths - If no valid CSV files exist in the selected folder,
system SHALL still enter Overview and display a warning

\#### Side Effects - active folder context created - active mode context
created

\-\--

\### UF-002 Review Basic Scan Data in Overview

\#### Actor User

\#### Goal Inspect basic scan data without advanced processing

\#### Entry Conditions - A scan folder has been selected - Mode has been
determined - Overview page is open

\#### Steps 1. System opens Overview after folder selection 2. System
displays no file-level outputs until a specific CSV file is selected 3.
User selects one CSV file 4. System loads the selected CSV in the
current mode context 5. System computes basic statistics 6. System
displays:  - summary statistics  - statistical charts  - file preview
table  - spatial map inspection  - device analysis section 7. User MAY
inspect the data without advanced processing

\#### Exit Conditions - selected CSV is inspected - user may proceed to
calibration

\#### Error Paths - If CSV data is partial or incomplete, system SHALL
display partial data and warning

\#### Side Effects - selected Overview CSV becomes part of current
UI/session context

\-\--

\### UF-003 Derive or Select Calibration Parameters

\#### Actor User

\#### Goal Generate or choose one session-level calibration parameter
set

\#### Entry Conditions - active scan folder exists - active mode exists

\#### Steps 1. User opens Calibration page 2. System displays dropdown
of all CSV files in active folder 3. User selects one calibration CSV 4.
System lists MAC addresses found in that file 5. User selects one MAC
address 6. System filters calibration processing to rows of that MAC
only 7. System derives calibration parameters 8. System displays
parameters for review 9. User approves derived parameters 10. If user
does not use derived calibration, system exposes fallback theoretical
parameter sets 11. User may choose one fallback set instead

\#### Exit Conditions - one active session calibration exists

\#### Error Paths - If calibration derivation fails, fallback parameter
sets SHALL remain available

\#### Side Effects - active \`SessionCalibration\` stored for the
selected scan-folder session

\-\--

\### UF-004 Select Scan CSV and Generate Enriched File

\#### Actor User

\#### Goal Select a scan CSV file and generate an enriched dataset using
a matching PCAP file

\#### Entry Conditions - active scan folder is selected - calibration
parameters exist OR fallback parameter sets are available

\#### Steps 1. User opens the Re-ID & Enrichment page 2. System displays
dropdown of all CSV files in the active folder 3. User selects a scan
CSV file 4. System searches for a PCAP file with identical basename 5.
If matching PCAP is found, system loads both CSV and PCAP 6. System
performs enrichment using PCAP data 7. System generates an enriched CSV
file 8. If enriched file already exists, system SHALL overwrite it

\#### Exit Conditions - official ENRICHED artifact exists - enriched
dataset becomes available for Re-ID

\#### Error Paths - If no matching PCAP file exists, system SHALL block
enrichment and display an error

\#### Side Effects - enriched artifact is created or overwritten -
enriched artifact becomes active

\-\--

\### UF-005 Run Re-ID and Produce Localization Input File

\#### Actor User

\#### Goal Run Re-ID on enriched dataset and generate a dataset for
localization

\#### Entry Conditions - enriched artifact exists

\#### Steps 1. User selects Re-ID parameters 2. User triggers Re-ID
execution 3. System loads the enriched artifact 4. System performs Re-ID
computation 5. System assigns \`cluster_id\` to each relevant record 6.
System generates a new REID artifact

\#### Exit Conditions - official REID artifact exists - file contains
\`cluster_id\` - file is active input for localization

\#### Error Paths - If enriched artifact does not exist, system SHALL
block execution and display an error

\#### Side Effects - REID artifact is created or overwritten - REID
artifact becomes active

\-\--

\### UF-006 Configure Localization Scope, Run Localization, and Render
Layered Map

\#### Actor User

\#### Goal Run localization on the full Re-ID dataset or a filtered
subset, then inspect the result through layered map rendering

\#### Entry Conditions - REID output file exists - Localization page is
available

\#### Steps 1. Localization page loads the current REID artifact as
default input 2. System defaults localization scope to the full REID
file 3. User MAY define pre-localization filters that reduce the rows
used for computation 4. User selects localization computation parameters
5. User triggers localization execution 6. System applies
pre-localization filters 7. System computes localization 8. System
produces a computed localization result 9. System renders a layered map
view over that result 10. User MAY apply post-localization view controls

\#### Exit Conditions - a computed localization result exists for the
current session state - layered map view is displayed

\#### Error Paths - If REID input is missing, system SHALL block
localization and display an error - If filters eliminate all usable
rows, system SHALL display an error and SHALL NOT produce a result

\#### Side Effects - current computed localization result becomes part
of session state - current localization parameters and view state become
available for save/resume

\-\--

\### UF-007 Save Current Session

\#### Actor User

\#### Goal Save the current session so it can be resumed later without
relying on TEMP

\#### Entry Conditions - a session exists

\#### Steps 1. User triggers Save Session 2. System collects current
session state 3. System collects current artifacts required for resume
4. System exports required artifacts into \`Saved Scans\` 5. System
writes saved-session state

\#### Exit Conditions - saved session exists under \`Saved Scans\`

\#### Error Paths - If required artifacts cannot be exported, save SHALL
fail and return an error

\#### Side Effects - persistent saved-session package created

\-\--

\### UF-008 Analyze Final Localization Result and Re-Run Final Stage
with Alternative Filtering Parameters

\#### Actor User

\#### Goal Analyze the final localization result, optionally compare it
against ground truth, and rerun required stages with alternative
parameters or filters

\#### Entry Conditions - a computed localization result exists - Result
Analysis page is available

\#### Steps 1. User opens Result Analysis after localization 2. System
loads current localization result and current map-layer state 3. User
MAY enter ground truth 4. User MAY change filters or parameters and
trigger rerun 5. If rerun is required, system reruns only the required
stages 6. User MAY change layer visibility and other view controls
without rerun 7. System displays final result through layered map
rendering and exposes current analysis outputs

\#### Exit Conditions - current final localization result is available
for inspection - current analysis state may be saved by the user as a
separate saved session

\#### Error Paths - If no localization result exists, system SHALL block
entry and display an error

\#### Side Effects - current localization result MAY be replaced by
rerun output - current result-analysis parameters and view state become
part of current session state

\-\--

\## 4. Architecture

\### 4.1 Architectural Style The system SHALL use a \*\*Frontend +
Backend\*\* architecture.

\### 4.2 High-Level Layers - UI / Frontend Layer - Workflow / Session
Orchestration Layer - Domain / Algorithm Layer - Artifact / Storage
Layer - Canonical Model / Schema Layer

\### 4.3 Key Separation Rules - page modules SHALL NOT own algorithmic
logic - algorithm engines SHALL NOT own rendering logic - rendering
SHALL NOT compute algorithmic results - session state SHALL NOT be
hidden inside page code - artifact handling SHALL be explicit -
save/resume SHALL NOT depend on implicit TEMP reconstruction

\### 4.4 Page / Landing Structure The current refactor scope includes: -
Folder Selection / Session Start - Overview - Calibration - Re-ID &
Enrichment - Localization - Result Analysis

\### 4.5 Future Page (Non-Binding) A future landing page MAY support: -
live connectivity with the ground unit - real-time display of incoming
small packets

This future page is recognized but remains out of current committed
refactor scope.

\-\--

\## 5. Data Models

\### 5.1 Model Inventory - M-001 ScanRecord - M-002 EnrichedScanRecord -
M-003 ReIDRecord - M-004 SessionCalibration - M-005 SavedSessionState

\-\--

\### M-001 ScanRecord

\#### Purpose Represent one raw scan row loaded from a selected scan CSV
file.

\#### Fields - \`timestamp_utc\`: string --- REQUIRED - \`frame_type\`:
string --- REQUIRED - \`src_mac\`: string --- REQUIRED - \`dst_mac\`:
string --- OPTIONAL - \`bssid\`: string --- OPTIONAL - \`ssid\`: string
--- OPTIONAL - \`rssi_dbm\`: number --- REQUIRED - \`channel\`: number
--- OPTIONAL - \`freq_mhz\`: number --- OPTIONAL - \`gps_lat\`: number
--- REQUIRED - \`gps_lon\`: number --- REQUIRED - \`gps_alt_m\`: number
--- OPTIONAL - \`gps_fix\`: string \| number --- OPTIONAL -
\`gps_num_sats\`: number --- OPTIONAL - \`gps_hdop\`: number ---
OPTIONAL - \`gps_age_ms\`: number --- OPTIONAL

\#### Validation Rules - \`timestamp_utc\`, \`src_mac\`, \`rssi_dbm\`,
\`gps_lat\`, and \`gps_lon\` SHALL exist

\#### Invariants - each instance represents exactly one CSV row - GPS
data is part of the row model

\-\--

\### M-002 EnrichedScanRecord

\#### Purpose Represent one enriched scan row after combining scan CSV
data with matching PCAP-derived metadata.

\#### Fields All fields from \`ScanRecord\`, plus: - \`src_vendor\`:
string --- OPTIONAL - \`dst_mac_pcap\`: string --- OPTIONAL -
\`bssid_pcap\`: string --- OPTIONAL - \`seq_ctl\`: number \| string ---
OPTIONAL - \`frame_len\`: number --- OPTIONAL - \`ie_ids\`: string ---
OPTIONAL - \`ie_fingerprint\`: string --- OPTIONAL - \`ie_vendor_ouis\`:
string --- OPTIONAL - \`match_found\`: boolean --- OPTIONAL -
\`match_delta_ms\`: number --- OPTIONAL - \`match_score\`: number ---
OPTIONAL - \`match_method\`: string --- OPTIONAL

\#### Validation Rules - all ScanRecord rules remain applicable -
enrichment fields MAY be empty if PCAP information is unavailable

\#### Invariants - all base scan fields are preserved - schema is fixed
even when values are null

\-\--

\### M-003 ReIDRecord

\#### Purpose Represent one row after Re-ID processing, including
cluster assignment.

\#### Fields All fields from \`EnrichedScanRecord\`, plus: -
\`\_match_delta_ms\`: number --- OPTIONAL - \`dst_vendor_pcap\`: string
--- OPTIONAL - \`bssid_vendor_pcap\`: string --- OPTIONAL - \`seq_num\`:
number --- OPTIONAL - \`cluster_id\`: string \| number --- REQUIRED -
\`cluster_type\`: string --- REQUIRED (\`static\` or \`dynamic\`)

\#### Validation Rules - all EnrichedScanRecord rules remain
applicable - \`cluster_id\` and \`cluster_type\` SHALL exist in every
persisted REID output row

\#### Invariants - output retains enriched schema and adds Re-ID fields

\-\--

\### M-004 SessionCalibration

\#### Purpose Represent the active calibration parameter set for one
selected scan-folder session.

\#### Fields - \`scan_folder_id\`: string --- REQUIRED -
\`calibration_csv_file\`: string --- OPTIONAL -
\`calibration_mac_address\`: string --- OPTIONAL -
\`parameter_set_name\`: string --- OPTIONAL - \`parameter_source\`:
string --- REQUIRED (\`derived\` or \`theoretical\`) - \`parameters\`:
object --- REQUIRED - \`approved\`: boolean --- REQUIRED

\#### Validation Rules - \`scan_folder_id\`, \`parameter_source\`,
\`parameters\`, and \`approved\` SHALL exist

\#### Invariants - at most one active calibration parameter set SHALL be
used at a time for one selected scan-folder session - supports both
derived and fallback theoretical parameters

\-\--

\### M-005 SavedSessionState

\#### Purpose Represent a saved application state that can be resumed
later.

\#### Fields - \`scan_folder_id\`: string --- REQUIRED - \`mode\`:
string --- REQUIRED - \`selected_calibration_csv\`: string ---
OPTIONAL - \`selected_calibration_mac\`: string --- OPTIONAL -
\`session_calibration\`: object --- OPTIONAL - \`selected_scan_csv\`:
string --- OPTIONAL - \`temp_enriched_csv_path\`: string --- OPTIONAL -
\`temp_reid_csv_path\`: string --- OPTIONAL -
\`computed_localization_result_path\`: string --- OPTIONAL -
\`localization_parameters\`: object --- OPTIONAL - \`view_state\`:
object --- OPTIONAL - \`final_analysis_parameters\`: object ---
OPTIONAL - \`saved_artifacts\`: object \| array --- REQUIRED -
\`saved_at_utc\`: string --- REQUIRED - \`ground_truth_state\`: object
--- OPTIONAL

\#### Validation Rules - \`scan_folder_id\`, \`mode\`,
\`saved_artifacts\`, and \`saved_at_utc\` SHALL exist

\#### Invariants - saved session state includes current computed result
and current parameter/state data required for resume - resume SHALL NOT
depend on reconstructing missing TEMP artifacts - separate saved
sessions are used instead of internal variant history

\-\--

\## 6. Rules & Constraints

\### 6.1 General Rules - no implicit behavior that changes pipeline
semantics - no hidden stage skipping except through explicit official
artifact activation - all cross-module data contracts SHALL use
canonical schema definitions - all protocol-specific differences SHALL
live under a shared high-level workflow

\### 6.2 Artifact Lifecycle & Persistence Rules - \`TEMP\` SHALL be a
global runtime storage area for the Ground Station application -
\`TEMP\` SHALL be non-persistent working storage and MAY be overwritten
or cleared between sessions - \`Saved Scans\` SHALL be separate
persistent storage for explicit save/resume - saved sessions SHALL NOT
rely on \`TEMP\` paths as their sole durable source - existing
\`\*\_ENRICHED.csv\` and \`\*\_REID.csv\` files discovered in a scan
folder SHALL be treated as official scan artifacts - existing official
artifacts SHALL appear in relevant dropdown selections - when a user
selects an existing official artifact, that artifact SHALL become active
immediately - when an existing enriched artifact is selected, the system
SHALL offer immediate transition to the Re-ID stage - when an existing
REID artifact is selected, the system SHALL offer immediate transition
to the Localization stage - enrichment output SHALL use original
filename plus the \`ENRICHED\` suffix - REID output SHALL use original
filename plus the \`REID\` suffix - enrichment output generation SHALL
overwrite an existing enriched artifact silently - REID output
generation SHALL overwrite an existing REID artifact silently - current
computed localization result SHALL be treated as current session output
during active use - current computed localization result SHALL be
persisted as a durable artifact when the user performs Save Session -
Save Session SHALL store the current result and current state data in
\`Saved Scans\` - Save Session SHALL copy or export all required
artifacts into persistent saved-session storage so resume SHALL NOT
depend on reconstructing data from \`TEMP\`

\### 6.3 Ground Truth Rules - Ground Truth SHALL exist only inside
Result Analysis - Ground truth SHALL be represented as points only - one
point SHALL represent one real emitter - Ground Truth SHALL NOT be a
separate top-level page in the refactored system

\### 6.4 View Control Rules - layer visibility controls SHALL be
view-only controls - view-only controls SHALL NOT trigger rerun - map
rendering SHALL NOT compute algorithmic results

\### 6.5 Testing Constraints - every module SHALL have unit tests -
every API contract SHALL have contract tests - every user flow SHALL
have integration coverage - regression tests SHALL exist for preserved
legacy behavior

\-\--

\## 7. Folder Structure

\### 7.1 Runtime Storage Areas \`\`\`text \[runtime-storage\]/ ├── DATA/
│ └── \[scan-folders\]/ ├── TEMP/ └── Saved Scans/ \`\`\`

\#### Runtime storage rules - \`DATA/\` SHALL contain scan folders and
their official scan artifacts - \`TEMP/\` SHALL contain global
non-persistent working artifacts for the active application runtime -
\`Saved Scans/\` SHALL contain persistent saved-session artifacts

\### 7.2 Repository Root (Proposed) \`\`\`text \[repo-root\]/ ├── docs/
├── configs/ ├── scripts/ ├── src/ ├── tests/ ├── tools/ └── README.md
\`\`\`

\-\--

\## 8. Modules

\### 8.1 Module Inventory - MOD-001 App Session & Navigation - MOD-002
Dataset Discovery & Artifact Resolver - MOD-003 Protocol & Schema
Normalization - MOD-004 Global Filter Engine - MOD-005 Overview Module -
MOD-006 Calibration Module - MOD-007 Enrichment Module - MOD-008 Re-ID
Engine - MOD-009 Localization Engine - MOD-010 Spatial Presentation
Module - MOD-011 Result Analysis Module - MOD-012 Artifact Management -
MOD-013 Save / Resume Module - MOD-014 Canonical Models & Schema Module

\-\--

\### MOD-001 App Session & Navigation

\#### Responsibility Manage current application session state and page
navigation without performing domain computation.

\#### Owned State - active scan folder - active mode - active Overview
CSV - active calibration selection - active scan CSV - active enriched
artifact - active REID artifact - current localization result
reference - current view state - current page or stage - current
warnings and readiness state

\#### Allowed Dependencies - MOD-002 Dataset Discovery & Artifact
Resolver - MOD-013 Save / Resume Module

\#### Forbidden Dependencies - MOD-007 Enrichment Module - MOD-008 Re-ID
Engine - MOD-009 Localization Engine - MOD-010 Spatial Presentation
Module

\-\--

\### MOD-002 Dataset Discovery & Artifact Resolver

\#### Responsibility Discover dataset folders and files, resolve
official artifacts, match CSV files with PCAP files, and provide
stage-continuation suggestions.

\#### Public Behavior - list scan folders - list CSV files in active
folder - list PCAP files in active folder - find matching PCAP for
selected CSV - find existing ENRICHED artifact for selected CSV - find
existing REID artifact for selected CSV - resolve folder artifact
inventory - provide stage jump suggestion for selected artifact

\#### Internal Notes - existing \`\*\_ENRICHED.csv\` and
\`\*\_REID.csv\` are official artifacts - selecting an official artifact
activates it immediately

\-\--

\### MOD-003 Protocol & Schema Normalization

\#### Responsibility Convert protocol-specific raw input data into
canonical schema representations used consistently across the Ground
Station system.

\#### Internal Notes - includes hooks for vendor/OUI resolution -
includes hooks for randomized-MAC classification - includes hooks for
heartbeat extraction - normalizes raw input into canonical
representations - SHALL NOT perform PCAP enrichment

\-\--

\### MOD-004 Global Filter Engine

\#### Responsibility Define and apply protocol-aware global filters
consistently across all application pages.

\#### Internal Notes - global filter semantics are defined once and
reused across pages - page modules MAY define additional page-specific
filters - page modules SHALL NOT redefine semantics of global filters -
post-localization layer visibility controls are NOT global filters

\-\--

\### MOD-005 Overview Module

\#### Responsibility Orchestrate CSV-level inspection of one selected
file in the active folder and present Overview sections without advanced
processing.

\#### Internal Notes - Overview opens automatically after folder
selection - displays no file-level outputs until a specific CSV is
selected - uses Spatial Presentation Module for map sections - SHALL NOT
implement map rendering directly

\-\--

\### MOD-006 Calibration Module

\#### Responsibility Manage calibration-file selection, calibration-MAC
selection, parameter derivation, approval, and fallback theoretical
parameter-set availability.

\#### Internal Notes - operates on one selected CSV and one selected MAC
address only - saves one active calibration parameter set for the
selected scan-folder session - fallback theoretical sets remain
available if derived calibration is skipped or fails

\-\--

\### MOD-007 Enrichment Module

\#### Responsibility Generate an official enriched artifact from one
selected scan CSV and its matching PCAP file.

\#### Internal Notes - requires matching PCAP with identical basename -
overwrites existing ENRICHED artifact silently - activates generated
ENRICHED artifact immediately

\-\--

\### MOD-008 Re-ID Engine

\#### Responsibility Run Re-ID over an active enriched artifact and
generate an official REID artifact with cluster assignment.

\#### Internal Notes - operates only on enriched data - generates output
containing \`cluster_id\` - implemented as one engine with
protocol-specific strategies rather than separate top-level Wi-Fi and
BLE engines

\-\--

\### MOD-009 Localization Engine

\#### Responsibility Compute multi-target localization from an active
REID artifact by applying protocol-specific pre-localization filters and
localization computation parameters, and produce computed per-cluster
localization results.

\#### Internal Notes - operates on REID artifact only - supports
protocol-specific pre-localization filters - UI-only browsing controls
such as sort order are NOT localization-engine inputs - if one cluster
fails, remaining clusters continue - layer visibility, grid-line
display, heatmap display, uncertainty display, and cluster visibility
selection are NOT owned by this module

\-\--

\### MOD-010 Spatial Presentation Module

\#### Responsibility Provide a shared map-based spatial rendering layer
for Overview, Localization, and Result Analysis.

\#### Supports - basemap control - spatial overlays - per-cluster
visibility control - hover-detail inspection - Result-Analysis-only
tools such as ground-truth interaction and distance measurement

\#### Internal Notes - renders spatial information - SHALL NOT perform
localization computation - supports showing all clusters, showing none,
and showing/hiding each cluster individually - ground-truth point
interaction and distance-measurement tools are enabled only in Result
Analysis context

\-\--

\### MOD-011 Result Analysis Module

\#### Responsibility Analyze the final scan result using ground truth
and defined quality metrics, compute an overall numeric scan-quality
score, and orchestrate reruns of required stages when relevant filters
or parameters are changed.

\#### Internal Notes - Ground Truth is managed only in Result Analysis -
Ground Truth is points only, one point per real emitter - supports
import from file, insertion from map, deletion, and clear - evaluates
scan quality using metrics such as containment, uncertainty-radius size,
detected-emitter count correctness, and Euclidean distance - includes
overall numeric scan-quality score as a formal capability - score
formulas/weights/submodels remain TBD - acts as rerun orchestrator -
reruns only required stages - supports future exposure of advanced
internal parameters for research and tuning - view-only changes do not
trigger rerun

\-\--

\### MOD-012 Artifact Management

\#### Responsibility Manage artifact naming, classification, storage,
overwrite behavior, activation references, and export of required
artifacts into persistent saved-session storage.

\#### Internal Notes - \`\*\_ENRICHED.csv\` and \`\*\_REID.csv\` are
official artifacts - uses original filename plus suffix naming -
overwrite is silent - supports export of required artifacts into \`Saved
Scans\` during Save Session

\-\--

\### MOD-013 Save / Resume Module

\#### Responsibility Save and restore complete analysis sessions using
persistent saved-session storage without relying on implicit
reconstruction from TEMP artifacts.

\#### Internal Notes - Save Session SHALL NOT depend on \`TEMP\` as the
sole durable source - Save Session SHALL export or copy all required
artifacts into \`Saved Scans\` - Resume SHALL restore current result and
current state without implicit recomputation - Ground-truth state SHALL
be part of the saved session when present - separate saved sessions are
used instead of internal variant history

\-\--

\### MOD-014 Canonical Models & Schema Module

\#### Responsibility Provide the single canonical source of truth for
internal data models, field contracts, invariants, and schema validation
rules used across Ground Station modules.

\#### Internal Notes - every cross-module data contract SHALL refer to
canonical models defined here - protocol normalization SHALL map raw
inputs into these canonical schemas or approved derivatives - generated
artifacts SHALL conform to appropriate canonical model definitions

\-\--

\## 9. Future Extensions (Non-Binding / Out of Current Refactor Scope)

The following items are recognized as possible future extensions and
SHALL NOT be treated as committed implementation scope for the current
Ground Station refactor:

\- a future landing page for live connectivity with the ground unit,
intended to support real-time display of small incoming packet updates
from the field system - future Result Analysis submodels that consume
localization output and compute a numeric overall scan-quality score for
the full scan session

\-\--

\## 10. Preservation Note This Part A is intended to preserve the
\*\*core architectural source of truth\*\*. Part B continues with: -
filters and parameters - algorithms - rerun rules - API contracts
