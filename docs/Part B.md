\# SAR Ground Station Spec --- Part B

\## Algorithms, Parameters, APIs

\> This document is a continuation split of the main Ground Station
specification. \> The original canvas remains preserved and unchanged as
the archive source. \> This Part B collects the runtime logic,
algorithmic specifications, parameter inventory, rerun rules, and API
contracts so work can continue without risking the size limit of the
original canvas.

\-\--

\## 1. Scope of Part B

This part contains:

\* Filter and parameter taxonomy \* Parameter inventory \* Rerun
propagation rules \* Calibration algorithm \* Enrichment algorithm \*
Re-ID algorithm \* Localization algorithm \* API contracts

This part does \*\*not\*\* replace the original full spec. It is a
structured continuation for implementation work.

\-\--

\## 2. Filter and Parameter Taxonomy

\### 2.1 Global Filters

Global filters are defined once in the Global Filter Engine and apply
consistently across all pages.

\#### Wi-Fi Global Filters

\* RSSI range \* frame types \* channels \* MAC privacy mode \* SSID
visibility mode \* minimum packets \* MAC filter mode \* selected or
excluded MAC addresses

\#### BLE Global Filters

\* RSSI range \* advertising or event types \* MAC privacy mode \*
minimum packets \* selected or excluded device addresses \* manufacturer
filter \* service UUID filter \* local name mode

\### 2.2 Stage-Specific Input Filters

These affect only the input dataset of a specific stage.

\#### Calibration Input Filters

\* selected calibration CSV \* selected calibration MAC address

\#### Localization Pre-Computation Filters

Treated as stage-specific input filters, not as view controls.

\### 2.3 Stage-Specific Computation Parameters

These affect how a stage computes its result.

\#### Calibration

\* derived calibration parameters \* fallback theoretical parameter sets

\#### Re-ID

\* clustering thresholds \* similarity thresholds \* conflict-resolution
parameters \* protocol-specific strategy parameters \* advanced internal
feature weights (TBD inventory)

\#### Localization

\* path loss n \* RSSI at 1 meter \* sigma \* grid resolution \* dynamic
sigma alpha \* confidence cutoff \* enable RANSAC \* RANSAC threshold \*
RANSAC iterations \* uncertainty target mass q

\### 2.4 View-Only Controls

These do not trigger rerun.

\* show grid lines \* show or hide heatmaps \* show or hide uncertainty
radii \* show or hide peak points \* show all clusters \* show no
clusters \* show or hide specific clusters \* basemap switch \* focus or
zoom to cluster

\### 2.5 Analysis Controls

Belong to Result Analysis and support evaluation and rerun.

\* ground-truth import \* ground-truth insertion from map \*
ground-truth deletion and clear \* rerun overrides \* score
configuration when approved

\### 2.6 Advanced or Internal Parameters

Reserved for research/tuning.

\* internal algorithm weights \* heuristic coefficients \* hidden
thresholds \* score-model weights \* advanced tuning parameters for
Calibration, Re-ID, Localization, Result Analysis

\### 2.7 UI Browsing and Selection Helpers

These are not true filters.

\* sort MACs by \* list ordering controls \* search helpers \*
non-semantic selection convenience controls

\-\--

\## 3. Parameter Inventory

\### 3.1 Global Filter Parameters

\#### Wi-Fi

\* \`GF-WIFI-01 rssi_min_dbm\` --- range \`\[-120,0\]\` --- default
\`-100\` \* \`GF-WIFI-02 rssi_max_dbm\` --- range \`\[-120,0\]\` ---
default \`0\` \* \`GF-WIFI-03 frame_types\` --- multiselect --- default
\`all\` \* \`GF-WIFI-04 channels\` --- multiselect --- default \`all\`
\* \`GF-WIFI-05 mac_privacy_mode\` --- \`{all, randomized_only,
fixed_only}\` --- default \`all\` \* \`GF-WIFI-06 ssid_visibility_mode\`
--- \`{all, named_only, hidden_or_empty_only}\` --- default \`all\` \*
\`GF-WIFI-07 min_packets\` --- integer, minimum \`1\` --- default \`1\`
\* \`GF-WIFI-08 mac_filter_mode\` --- \`{include, exclude}\` --- default
\`include\` \* \`GF-WIFI-09 selected_mac_addresses\` --- list ---
default empty

\#### BLE

\* \`GF-BLE-01 rssi_min_dbm\` --- range \`\[-120,0\]\` --- default
\`-100\` \* \`GF-BLE-02 rssi_max_dbm\` --- range \`\[-120,0\]\` ---
default \`0\` \* \`GF-BLE-03 event_types\` --- multiselect --- default
\`all\` \* \`GF-BLE-04 mac_privacy_mode\` --- \`{all, randomized_only,
fixed_only}\` --- default \`all\` \* \`GF-BLE-05 min_packets\` ---
integer, minimum \`1\` --- default \`1\` \* \`GF-BLE-06
selected_device_addresses\` --- list --- default empty \* \`GF-BLE-07
manufacturer_filter\` --- multiselect --- default \`all\` \* \`GF-BLE-08
service_uuid_filter\` --- multiselect --- default \`all\` \* \`GF-BLE-09
local_name_mode\` --- \`{all, named_only, unnamed_only}\` --- default
\`all\`

\### 3.2 Calibration Parameters

\* \`CAL-01 gt_mode\` --- \`{manual_map_click, first_sample,
mean_first_k}\` --- default \`mean_first_k\` \* \`CAL-02 gt_first_k\`
--- \`\[1,20\]\` --- default \`5\` \* \`CAL-03 enable_ransac\` ---
boolean --- default \`true\` \* \`CAL-04 ransac_residual_threshold_db\`
--- \`\[1,15\]\` --- default \`4\` \* \`CAL-05 ransac_iterations\` ---
\`\[10,1000\]\` --- default \`100\` \* \`CAL-06 distance_floor_m\` ---
\`\[0.5,5\]\` --- default \`1\` \* \`CAL-07 fit_warning_min_samples\`
--- \`TBD\` \* \`CAL-08 fit_warning_min_inlier_ratio\` --- \`TBD\`

\### 3.3 Enrichment Parameters

\* \`ENR-01 match_threshold\` --- protocol-global default \* \`ENR-02
match_time_window_ms\` --- protocol-global default \* \`ENR-03
time_score_weight\` \* \`ENR-04 identity_score_weight\` \* \`ENR-05
wifi_context_weight\` \* \`ENR-06 ble_context_weight\`

\### 3.4 Re-ID Parameters

\#### Shared

\* \`REID-01 association_threshold\` \* \`REID-02
conflict_resolution_mode = greedy_best_valid_match\`

\#### Wi-Fi

\* \`REID-WIFI-01 seq_gap_threshold\` --- default \`legacy default\` \*
\`REID-WIFI-02 max_rotation_time_window_ms\` --- default \`legacy
default\` \* \`REID-WIFI-03 time_gap_weight\` --- default \`legacy
default\` \* \`REID-WIFI-04 seq_gap_weight\` --- default \`legacy
default\` \* \`REID-WIFI-05 ie_similarity_weight\` --- default \`legacy
default\` \* \`REID-WIFI-06 fingerprint_similarity_weight\` --- default
\`legacy default\` \* \`REID-WIFI-07 rssi_continuity_weight\` ---
default \`legacy default\` \* \`REID-WIFI-08 frame_length_weight\` ---
default \`legacy default\` \* \`REID-WIFI-09 vendor_consistency_weight\`
--- default \`legacy default\` \* \`REID-WIFI-10
spatial_continuity_weight\` --- default \`legacy default\`

\#### BLE

\* \`REID-BLE-01 time_gap_weight\` \* \`REID-BLE-02
address_rotation_timing_weight\` \* \`REID-BLE-03
advertising_interval_weight\` \* \`REID-BLE-04
manufacturer_data_weight\` \* \`REID-BLE-05 service_uuid_weight\` \*
\`REID-BLE-06 local_name_weight\` \* \`REID-BLE-07 tx_power_weight\` \*
\`REID-BLE-08 rssi_continuity_weight\` \* \`REID-BLE-09
spatial_continuity_weight\` \* \`REID-BLE-10 vendor_consistency_weight\`

\### 3.5 Localization Parameters

\* \`LOC-01 bounds_mode\` --- \`{manual_rectangle,
auto_track_plus_buffer}\` --- default \`auto_track_plus_buffer\` \*
\`LOC-02 search_area_buffer_m\` --- default \`20\` \* \`LOC-03
path_loss_n\` --- default from calibration/fallback \* \`LOC-04
rssi_at_1m\` --- default from calibration/fallback \* \`LOC-05 sigma\`
--- default from calibration/fallback \* \`LOC-06 grid_resolution_m\` \*
\`LOC-07 dynamic_sigma_alpha\` \* \`LOC-08 confidence_cutoff\` \*
\`LOC-09 enable_ransac\` \* \`LOC-10 ransac_thresh_db\` \* \`LOC-11
ransac_iters\` \* \`LOC-12 uncertainty_target_mass_q\` --- default
\`0.68\` \* \`LOC-13 min_samples_per_cluster\` --- default \`3\`

\### 3.6 View Controls

\* \`VIEW-01 show_grid_lines\` \* \`VIEW-02 show_heatmap\` \* \`VIEW-03
show_uncertainty_radii\` \* \`VIEW-04 show_peak_points\` \* \`VIEW-05
show_all_clusters\` \* \`VIEW-06 hide_all_clusters\` \* \`VIEW-07
selected_visible_clusters\` \* \`VIEW-08 basemap_type\` \* \`VIEW-09
zoom_to_cluster\`

\### 3.7 Result Analysis / Advanced Parameters

\* \`RA-01 gt_import_mode\` --- \`{file, map}\` \* \`RA-02
gt_matching_mode\` --- \`TBD\` \* \`RA-03 score_enable_numeric\` ---
default \`true\` \* \`RA-04 score_weight_containment\` --- \`TBD\` \*
\`RA-05 score_weight_radius_size\` --- \`TBD\` \* \`RA-06
score_weight_emitter_count\` --- \`TBD\` \* \`RA-07
score_weight_euclidean_distance\` --- \`TBD\` \* \`RA-08
advanced_internal_parameter_exposure\` --- default \`false\` \* \`RA-09
advanced_internal_parameter_set\` --- \`TBD\`

\-\--

\## 4. Rerun Propagation Rules

\* changing a Global Filter reruns from the first downstream stage that
consumes filtered data \* changing a Calibration Parameter reruns
calibration → localization → result analysis \* changing an Enrichment
Parameter reruns enrichment → re-id → localization → result analysis \*
changing a Re-ID Parameter reruns re-id → localization → result analysis
\* changing a Localization Parameter reruns localization → result
analysis \* changing a View-Only Control triggers no rerun \* changing a
Result Analysis score parameter recomputes result analysis only \*
changing an Advanced Internal Parameter reruns according to the owner
stage

\-\--

\## 5. Algorithm Specifications

\### 5.1 Localization Algorithm

\#### Goal

Compute a multi-target localization result from an active REID artifact
by producing per-cluster peak estimates, grid/heatmap results, and
one-to-three reported uncertainty regions.

\#### Required Inputs

\* active REID artifact \* active protocol \* localization computation
parameters \* protocol-specific pre-localization filters \* search-area
bounds \* active calibration parameters or fallback theoretical
parameters

\#### Preconditions

\* active REID artifact exists \* required fields include cluster
identifier, GPS position, and RSSI \* search-area bounds are defined \*
computation parameters are valid \* each cluster has at least 3 usable
samples

\#### Search-Area Bounds Resolution

\* manual map selection of a rectangular area \* or automatic bounds
from scan trajectory extrema plus configurable buffer \* automatic
bounds default buffer = \`20m\`

\#### Step 0 --- Validate Input

Validate REID artifact, schema, cluster identifier, GPS/RSSI,
parameters, and bounds. If invalid, block localization.

\#### Step 1 --- Apply Pre-Localization Filters

Apply protocol-specific filters. If no usable rows remain, block
localization.

\#### Step 2 --- Partition by Cluster

Partition filtered rows by \`cluster_id\`.

\#### Step 3 --- Cluster Validation

Require valid GPS, RSSI, and at least 3 usable rows. Failed clusters
emit warnings while others continue.

\#### Step 4 --- Optional RANSAC Pre-Cleaning

If enabled, apply RANSAC before grid computation using RSSI residual
consistency. If fewer than 3 usable inliers remain, the cluster fails.

\#### Step 5 --- Build Computational Grid

Construct a computational grid over the search area using configured
grid resolution.

\#### Step 6 --- Compute Per-Sample Contribution to Every Grid Cell

For each sample \`i\` and grid cell \`j\`:

1\. compute distance between sample and cell center 2. compute expected
RSSI: \`mu_ij = rssi_at_1m - 10 \* path_loss_n \* log10(d_ij)\` 3.
compute effective sigma:

\* fixed sigma, or \* dynamic sigma: \`sigma_ij = sigma \* (1 + alpha \*
log10(max(d_ij, 1)))\` 4. compute Gaussian-like likelihood contribution
from the RSSI residual 5. accumulate contributions across all samples
into a cluster score map

\#### Step 7 --- Build Posterior Heatmap

Convert score map into normalized posterior-like heatmap for peak
detection and uncertainty estimation.

\#### Step 8 --- Detect and Retain Candidate Peaks

Detect local maxima, filter by \`confidence_cutoff\`, retain at most 3
candidate peaks, and mark the strongest as the default displayed point.

\#### Step 9 --- Build Local Uncertainty Radii per Candidate Peak

For each retained peak, define a local basin and derive a local
uncertainty radius capturing target probability mass \`q\`.

\* default \`q = 0.68\` \* \`q\` is rerun-adjustable

\#### Step 10 --- Merge or Preserve Candidate Peaks into Reported
Uncertainty Regions

Transform candidate peaks into 1--3 reported uncertainty regions:

\* \*\*dominant-peak case\*\*: one strong peak dominates or contains the
others → report one region \* \*\*merged multi-peak case\*\*: several
strong peaks occupy the same area → merge into one larger region \*
\*\*separated multi-peak case\*\*: strong peaks are spatially separated
→ report separate regions

\#### Step 11 --- Build Per-Cluster Result Object

Each successful cluster returns:

\* cluster identifier \* primary peak point \* retained candidate peaks
\* grid/heatmap data \* uncertainty metadata \* one-to-three reported
uncertainty regions \* status \* warnings \* parameter snapshot

Failed clusters return failed status plus warnings.

\#### Step 12 --- Build Full Localization Result

Aggregate all cluster results into one computed localization result
consumed by Spatial Presentation and Result Analysis.

\#### Failure Behavior

\* full failure if REID/schema/filters/bounds/parameters invalid \*
partial failure if some clusters fail while at least one succeeds

\#### Output Contract

Each successful cluster outputs:

\* one primary displayed peak \* up to 3 retained candidate peaks \*
one-to-three reported uncertainty regions \* heatmap/grid result data \*
ambiguity and warning metadata

\#### Integration Constraints

Localization requires:

\* active calibration or fallback theoretical parameters \* REID output
with valid \`cluster_id\` \* canonical GPS and RSSI fields

Localization does not own:

\* map rendering \* layer visibility \* ground-truth interaction \*
numeric score computation \* rerun-scope decisions

\-\--

\### 5.2 Re-ID Algorithm

\#### Goal

Compute logical device identities from an active ENRICHED artifact by
assigning each relevant row to a \`cluster_id\`, while bypassing
non-dynamic MAC addresses directly into stable clusters and applying
protocol-specific association logic for dynamic identities.

\#### Preconditions

\* active ENRICHED artifact exists \* required Re-ID fields are present
\* protocol context known \* parameters valid

\#### Required Inputs for Wi-Fi

When available:

\* timestamp \* source MAC or device identifier \* RSSI \* GPS position
\* sequence-related field \* IE-related identifiers/fingerprint fields
\* frame-length information \* vendor-related metadata

\#### Step 0 --- Validate and Prepare Enriched Input

Validate artifact/schema/protocol/parameters and prepare ordered
internal representation.

\#### Step 1 --- Privacy Classification and Static Bypass

Classify identities into:

\* \`dynamic\` \* \`static\`

Static identities bypass dynamic association, each gets one stable
cluster:

\* \`cluster_type = static\`

Only dynamic identities enter pairing/scoring/clustering.

\#### Step 2 --- Build Base Observation Units

\* \*\*Wi-Fi\*\*: use minimal observation units suitable for sparse
rapidly changing MAC behavior; do not depend on long trails \*
\*\*BLE\*\*: may use more stable short segments when address persistence
supports them

\#### Step 3 --- Candidate Generation by Time Proximity

Dynamic observation units generate candidate association pairs primarily
by temporal proximity.

\* Wi-Fi: time-gap gating is primary \* BLE: same framework, but
candidate construction may use more stable grouping

\#### Step 4 --- Build Feature Vector per Candidate Pair

\##### Wi-Fi feature families

Reuse legacy feature families and default feature weights by default:

\* time-gap feature \* sequence-gap feature \* IE similarity feature \*
fingerprint similarity feature \* RSSI continuity feature \*
frame-length similarity feature \* vendor-consistency feature \* spatial
continuity feature when available

These weights remain adjustable in rerun workflows.

\##### BLE feature families

Use same Re-ID framework with protocol-specific feature strategy:

\* time-gap feature \* address-rotation timing feature \*
advertising-interval consistency feature \* manufacturer-data similarity
feature \* service-UUID similarity feature \* local-name similarity
feature \* TX-power similarity feature when available \* RSSI continuity
feature \* spatial continuity feature \* vendor-consistency feature

\#### Step 5 --- Weighted Association Scoring

Compute weighted similarity score from the feature vector.

\* Wi-Fi default implementation may use logistic-style scoring \* formal
contract is weighted feature similarity association scoring \* advanced
internal feature weights are official Re-ID parameters, inventory TBD

\#### Step 6 --- Thresholding

Retain only candidate associations above configured association
threshold.

\#### Step 7 --- Conflict Resolution

Use greedy best-valid-match conflict resolution:

\* choose best surviving candidate above threshold \* preserve time
consistency \* prevent contradictory assignments

\#### Step 8 --- Build Dynamic Clusters

Surviving valid associations connect dynamic observation units into
logical dynamic clusters:

\* \`cluster_type = dynamic\`

\#### Step 9 --- Merge Static and Dynamic Cluster Results

Final result combines:

\* static clusters \* dynamic clusters

Every relevant row receives:

\* \`cluster_id\` \* \`cluster_type\`

\#### Step 10 --- Build REID Artifact

Write official REID artifact conforming to \`ReIDRecord\` with upstream
retained fields plus \`cluster_id\` and \`cluster_type\`.

\#### Failure Behavior

\* full failure if no enriched artifact / bad schema / missing required
fields / invalid parameters \* partial failure allowed when some units
cannot be matched; unmatched rows may remain singleton clusters

\#### Output Contract

Every relevant output row guarantees:

\* \`cluster_id\` \* \`cluster_type\` where \`cluster_type ∈ {static,
dynamic}\`

\#### Integration Constraints

Re-ID consumes official output of Enrichment and produces cluster
assignments suitable for Localization.

\-\--

\### 5.3 Enrichment Algorithm

\#### Goal

Generate an official ENRICHED artifact from one selected scan CSV and
its matching PCAP by attaching protocol-specific PCAP-derived metadata
and row-level match diagnostics to each CSV row.

\#### Preconditions

\* selected scan CSV exists \* matching PCAP exists \* both files
readable \* protocol context known \* enrichment parameters valid

\#### Step 0 --- Validate Inputs

Validate CSV, matching PCAP, protocol context, parameters.

\#### Step 1 --- Parse PCAP into Frame-Feature Table

\##### Wi-Fi extraction

When available:

\* timestamp \* source/destination MAC metadata \* BSSID metadata \*
channel/frequency metadata \* sequence-related fields \* frame length \*
IE identifiers \* IE fingerprint \* IE vendor OUIs \* vendor-related
metadata

\##### BLE extraction

Implemented immediately and includes when available:

\* timestamp \* advertiser/device address metadata \* advertising/event
type \* manufacturer-data digest \* service-UUID digest/list \*
local-name digest/value \* TX-power metadata \* flags/advertising
metadata \* vendor-related metadata

\#### Step 2 --- Normalize Extracted PCAP Fields

Normalize formatting, timestamps, protocol field mapping, and null
handling.

\#### Step 3 --- Build Searchable PCAP Index

Build searchable index using:

\* time buckets \* identity-related keys \* protocol-type keys \* Wi-Fi
context fields such as BSSID/channel when available \* BLE context
fields when available

\#### Step 4 --- Generate Candidate PCAP Matches per CSV Row

For each CSV row:

1\. derive row-level matching context 2. retrieve candidate frames from
index 3. filter by time proximity first 4. apply identity/context
constraints

Official philosophy:

\* time-first matching \* followed by protocol-specific identity/context
constraints

\#### Step 5 --- Score Candidate Matches and Choose Best Match

Compute \`match_score\` for each candidate.

Primary driver: time proximity. May include protocol-specific
compatibility signals.

Wi-Fi scoring may include:

\* source/destination consistency \* BSSID compatibility \* channel
compatibility \* frame-type compatibility

BLE scoring may include:

\* advertiser-identity compatibility \* event-type compatibility \*
manufacturer-data compatibility \* service-UUID compatibility \*
local-name compatibility

Choose best-scoring candidate only if it passes protocol-global
\`match_threshold\`.

\#### Step 6 --- Build Enriched Row

Each output row preserves all original scan fields.

\##### Wi-Fi enrichment fields

Include when available:

\* source vendor \* destination MAC from PCAP \* BSSID from PCAP \*
sequence-related field \* frame length \* IE identifiers \* IE
fingerprint \* IE vendor OUIs

\##### BLE enrichment fields

Part of official schema even when missing values:

\* advertiser/device metadata from PCAP \* event type \*
manufacturer-data digest \* service-UUID information \* local-name
information \* TX-power metadata \* vendor-related metadata

\##### Match diagnostics fields

Every enriched row includes:

\* \`match_found\` \* \`match_delta_ms\` \* \`match_score\` \*
\`match_method\`

\`match_method\` supports at least:

\* \`time_identity_best_match\` \* \`time_only_match\` \* \`no_match\`

If no valid candidate passes threshold, row is still preserved with null
enrichment values and diagnostics showing no match.

\#### Step 7 --- Write Official ENRICHED Artifact

Write official ENRICHED artifact using original filename plus
\`ENRICHED\` suffix. Overwrite silently if already exists. Result
becomes active input for Re-ID.

\#### Failure Behavior

\* full failure if no matching PCAP / unreadable CSV / unreadable PCAP /
invalid protocol / invalid parameters \* row-level partial failure
allowed when no valid PCAP frame can be matched

\#### Output Contract

ENRICHED output guarantees:

\* preservation of original scan fields \* existence of approved
enrichment schema columns \* existence of row-level match diagnostics
fields

\#### Enrichment Quality Signals

Preserve row-level match quality so downstream stages may use it.
Aggregate quality stats may also be computed on demand.

\#### Integration Constraints

Provides richer per-row metadata to Re-ID, including protocol-specific
signature fields and row-level match quality signals. Does not perform
clustering, localization, map rendering, GT handling, or scoring.

\-\--

\### 5.4 Calibration Algorithm

\#### Goal

Derive session-level calibration parameters from one selected
calibration CSV, one selected MAC address, and one selected ground-truth
definition, while preserving the option to fall back to theoretical
presets.

\#### Supported Ground-Truth Modes

\* manual map selection \* first sample as GT \* mean of first K samples
as GT

Expose all supported GT modes. Default sensible values:

\* default GT mode = \`mean_first_k\` \* default \`K = 5\` \* default
RANSAC = enabled \* default RANSAC residual threshold = \`4 dB\` \*
default RANSAC iterations = \`100\` \* default minimum distance floor =
\`1 meter\`

\#### Preconditions

\* selected calibration CSV exists \* selected MAC exists in that CSV \*
usable rows exist \* RSSI and GPS available \* enough usable samples
remain for regression fitting

\#### Step 0 --- Validate Calibration Input

Validate selected CSV, MAC, sample availability, RSSI/GPS availability,
and calibration parameters. If invalid, do not produce derived
calibration.

\#### Step 1 --- Filter to Selected MAC

Filter calibration CSV to rows associated with selected MAC only.

\#### Step 2 --- Resolve Ground-Truth Point

Resolve one GT point using selected mode.

\* manual map click \* first usable sample \* mean of first K usable
samples

\#### Step 3 --- Build Distance-RSSI Calibration Dataset

For each usable calibration row compute distance to GT point and
construct:

\* \`x = log10(distance)\` \* \`y = RSSI\` using minimum distance floor
before logarithm.

\#### Step 4 --- Display Calibration Scatter Plot

Display scatter plot with:

\* x-axis = \`log10(distance)\` \* y-axis = \`RSSI\`

\#### Step 5 --- Optional RANSAC Cleaning

If enabled, run RANSAC linear regression over scatter points before
final fit:

1\. sample provisional subsets 2. fit provisional linear models 3.
compute residuals 4. classify inliers using residual threshold 5.
iterate configured number of times 6. retain best inlier set

If too few samples remain, derived calibration fails.

\#### Step 6 --- Final Linear Regression

Fit linear model:

\* \`y = a + b\*x\` where \`x = log10(distance)\` and \`y = RSSI\`

\#### Step 7 --- Derive Calibration Parameters from the Linear Fit

\* \`rssi_at_1m = a\` \* \`path_loss_n = -b / 10\`

The system explains that this is the linearized form of the log-distance
path-loss model.

\#### Step 8 --- Estimate Sigma

Compute sigma from residual standard deviation, preferably over inliers
when RANSAC is enabled.

\#### Step 9 --- Compute Fit-Quality Diagnostics

May include:

\* sample count \* inlier count \* inlier ratio \* distance span \*
\`R²\` \* sigma

\#### Step 10 --- Present Derived Calibration Result

Show scatter plot, fitted line, inliers/outliers when available, derived
parameters, and fit diagnostics.

\#### Step 11 --- Warning and Approval Behavior

If fit appears weak/noisy, warn the user but still allow manual
approval. Do not auto-reject solely for low fit quality.

If approved, store session calibration as:

\* \`parameter_source = derived\` \* \`approved = true\`

\#### Step 12 --- Fallback Theoretical Parameter Sets

If derived calibration unavailable/skipped/not approved, expose 2--3
presets such as:

\* urban \* open field \* mixed outdoor

Each fallback preset provides same downstream schema.

\#### Failure Behavior

Derived calibration fails if no usable rows, missing GPS/RSSI, too few
samples, or selected GT mode cannot produce usable GT point. Fallback
remains available.

\#### Output Contract

Outputs either:

\* derived session calibration containing \`rssi_at_1m\`,
\`path_loss_n\`, \`sigma\` \* or theoretical fallback parameter set
using same schema

\#### Integration Constraints

Provides session-level parameters required by Localization. Does not
perform enrichment, Re-ID, GT quality evaluation, or scoring.

\-\--

\## 6. API Contracts

\### 6.1 API Design Principles

\* session-centric \* all user-facing workflow operations execute in
context of active \`session_id\` \* long-running operations use
\`execution_id\` \* result-analysis operations remain under one unified
namespace \* frontend can retrieve current session state in one request

\### 6.2 Session and Folder APIs

\* \`GET /api/scan-folders\` \* \`POST /api/sessions\` \* \`PATCH
/api/sessions/{session_id}/mode\` \* \`GET
/api/sessions/{session_id}/state\`

\### 6.3 Inventory and Artifact APIs

\* \`GET /api/sessions/{session_id}/inventory\` \* \`POST
/api/sessions/{session_id}/artifacts/activate\`

\### 6.4 Overview API

\* \`POST /api/sessions/{session_id}/overview\`

\### 6.5 Calibration APIs

\* \`POST /api/sessions/{session_id}/calibration/candidates\` \* \`POST
/api/sessions/{session_id}/calibration/run\` \* \`POST
/api/sessions/{session_id}/calibration/approve\` \* \`POST
/api/sessions/{session_id}/calibration/fallback\`

\### 6.6 Execution Model

Long-running operations using \`execution_id\`:

\* enrichment \* re-id \* localization \* result-analysis rerun

Status endpoint:

\* \`GET /api/executions/{execution_id}\`

\### 6.7 Enrichment API

\* \`POST /api/sessions/{session_id}/enrichment/run\`

\### 6.8 Re-ID API

\* \`POST /api/sessions/{session_id}/reid/run\`

\### 6.9 Localization API

\* \`POST /api/sessions/{session_id}/localization/run\`

\### 6.10 Result Analysis APIs

\* \`GET /api/sessions/{session_id}/result-analysis\` \* \`POST
/api/sessions/{session_id}/result-analysis/ground-truth/import\` \*
\`POST /api/sessions/{session_id}/result-analysis/ground-truth\` \*
\`DELETE
/api/sessions/{session_id}/result-analysis/ground-truth/{gt_id}\` \*
\`POST /api/sessions/{session_id}/result-analysis/ground-truth/clear\`
\* \`POST /api/sessions/{session_id}/result-analysis/evaluate\` \*
\`POST /api/sessions/{session_id}/result-analysis/rerun\`

\### 6.11 Save and Resume APIs

\* \`POST /api/sessions/{session_id}/save\` \* \`GET
/api/saved-sessions\` \* \`POST
/api/saved-sessions/{saved_session_id}/resume\`

\### 6.12 API Contract Constraints

\* APIs expose only top-level workflow actions \* public workflow APIs
align with canonical models and approved session state \* long-running
execution endpoints report stage, status, warnings, result metadata \*
result-analysis APIs remain under one unified namespace \* view-only
control changes do not require execution endpoints
