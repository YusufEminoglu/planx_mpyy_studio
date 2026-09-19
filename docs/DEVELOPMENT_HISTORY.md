# Previous technical checkpoints (through 2.5.1)

Archived developer reference. The current plugin interface is Turkish; see the current README and GUI architecture document. Language statements below describe earlier releases.

---

# PlanX MPYY Studio

## Workbench (2.5.1)

The dock has three pages: **Start**, **Tools** and **Activity**. Start follows the daily workspace, import, style, check and delivery workflow. Tools contains all 83 Processing algorithms and two dock utilities, grouped by task. Search accepts English descriptions and algorithm identifiers, ignoring accents.

All plugin-owned interface copy is English: tool names, help, parameters, options, messages, form tabs, aliases, constraints, legends, MapTips and generated report text. Display translations retain statutory catalog identities, stored codes, field names and user-supplied names. Native QGIS expressions keep translated lookup displays portable in saved projects.

Select a tool to see its purpose, required inputs and expected output. **Open tool** opens its configuration; a calculation is started from Processing. Existing lightweight forms are available through **Use compact form**, one form at a time. Back navigation retains entered values. Layer selections begin empty to make the target explicit.

Use **Ctrl+K** to search, arrow keys to select and **Enter** or **Alt+O** to open a tool. Tab moves between controls. Saved shortcuts persist in QGIS settings; recent tools belong to the current dock session. Full result messages are retained in the copyable Activity log.

The UI follows the QGIS application font and palette. Labels and buttons wrap in narrow docks; forms scroll vertically. See [GUI architecture](docs/GUI_ARCHITECTURE.md) for the review and reproducible visual checks.

MPYY spatial planning studio. MPYY/e-Plan is the default symbology engine;
local MPYY XML styles are selectable alternatives.

## Workspaces

The planning GeoPackage retains the hierarchy: spatial strategy plan (MSP),
environmental plan (CDP), master plan (NIP), implementation plan (UIP). Each level
has one polygon, line and notation layer set. The UIP polygon layer includes
MPYY identity, the function catalog, building arrangement, site coverage,
floor area ratio, height and setbacks in a conditional English attribute form.

Land use is a separate workspace: TUCBS land layers and parcel, building and road
survey tables remain separate from planning levels. Both workspaces can be loaded
into the same QGIS project.

`meri_1000_alan` and the old parallel UIP layers are no longer in the schema.
Source QML files are retained for comparison and traceability; primary layers
are created with programmatic MPYY forms.

The `planx_mpyy_studio` Processing provider contains 83 algorithms.
Advanced production tools introduced since 1.1.0 include:

- `optimize_parcel_subdivision`
- `export_official_zoning_atlas`
- `export_official_zoning_atlas_batch`
- `generate_procedural_3d_massing`
- `audit_municipal_bylaw_compliance`
- `preview_workspace_reconciliation`
- `reconcile_workspace_versions`
- `audit_msp_plan_requirements`
- `audit_cdp_plan_requirements`
- `audit_nip_plan_requirements`
- `audit_uip_plan_requirements`
- `audit_plan_hierarchy_consistency`
- `audit_plan_submission_dossier`
- `screen_mpyy_threshold_constraints`
- `audit_mpyy_road_plan_change`
- `audit_mpyy_density_height_change`
- `evaluate_msp_action_monitoring`
- `classify_cdp_revision_scope`
- `audit_nip_uip_active_mobility_network`
- `audit_mpyy_evidence_provenance`
- `audit_institution_opinion_register`
- `analyze_nip_uip_routed_accessibility`
- `audit_adjacent_plan_boundary_consistency`
- `audit_plan_fabric_topology`
- `audit_mpyy_plan_report_content`
- `audit_mpyy_article12_walking_distances`
- `audit_conservation_plan_dossier`
- `audit_integrated_coastal_plan_dossier`
- `audit_urban_design_project_prerequisites`
- `audit_mpyy_article8_research_dossier`
- `audit_mpyy_article10_official_legend`
- `audit_mpyy_article11_standards_context`
- `classify_mpyy_article25_plan_intervention`
- `consolidate_mpyy_audit_reports`
- `initialize_mpyy_plan_dossier`
- `audit_mpyy_dossier_completeness`
- `audit_mpyy_evidence_freshness`
- `audit_mpyy_mixed_use_details`
- `audit_mpyy_publication_objection_register`
- `audit_mpyy_participation_register`
- `audit_mpyy_cancelled_plan_evidence`
- `audit_mpyy_plan_component_consistency`
- `audit_mpyy_approval_sheet_register`
- `audit_mpyy_digital_delivery_package`
- `audit_mpyy_gpkg_schema_profile`
- `generate_mpyy_dossier_inventory`
- `audit_mpyy_plan_note_decision_links`
- `audit_mpyy_version_chain`
- `analyze_mpyy_multimodal_accessibility`

## 2.4.0 Profile identity verification and accessibility memory

`audit_mpyy_schema_profile_identity` checks a profile's canonical content SHA-256. Supply the optional source dictionary to verify its bytes and reconstruct the profile using its retained mapping. Supply an independently retained profile digest to detect changed content even if someone has recomputed the file's embedded digest. Identity reports explicitly state `issuer_authenticity: NOT_VERIFIED`. A matching checksum establishes content consistency; authenticating the issuing institution requires a trusted external reference.

GeoPackage schema audits automatically validate an embedded identity, and require it on imported profiles. An identity failure produces an incomplete report with zero inspected tables. Legacy profiles without an embedded digest or import mapping remain usable. Profile and import-mapping JSON reject duplicate keys and non-finite values.

Multimodal search stores shared immutable mode tails and renders mode text only for requested demand routes. Incoming arcs are built directly, and both scenario and standalone multimodal Processing tools check cancellation throughout the analysis. Route-mode output no longer has an 80-character field limit.

The synthetic benchmark uses two directed networks alternating walking/transit, 200 shared-origin demand features and one destination. Every output status, time, mode identity and facility ID matched the 2.3.0 reference. Single-run results for 6,000 edges per scenario:

| Runtime | Reference traced Python peak | 2.4 traced Python peak | Reference seconds | 2.4 seconds |
| --- | ---: | ---: | ---: | ---: |
| QGIS 3.44 LTR | 167.32 MB | 6.66 MB | 1.544 | 1.296 |
| QGIS 4.2 | 167.32 MB | 6.66 MB | 1.577 | 1.376 |

`tracemalloc` excludes native QGIS/GEOS allocations and adds timing overhead; these are fixture-specific measurements, not citywide runtime guarantees. Reproduce a current-engine run with `python-qgis-ltr.bat -m planx_mpyy_studio.tests.benchmark_accessibility_qgis --output scratch/benchmark.json` from the plugins root using a separate `QGIS_CUSTOM_CONFIG_PATH`. An optional `--reference-module` compares a retained previous engine. The local reference and raw reports are in `scratch/mpyy_240` at the plugins root.

## 2.3.0 Accessibility scenarios and schema dictionary import

`compare_mpyy_accessibility_scenarios` evaluates baseline and proposed networks and facility sets against one shared demand layer. Each output geometry retains its source demand feature ID, both access statuses, facility IDs, route modes, snap distances, travel times, and proposed-minus-baseline time change. Negative changes mean faster travel. Route gain, route loss, unchanged unreachable demand, and snap uncertainty have separate change categories; missing routes never receive a fabricated travel time. Both scenarios share the declared time threshold, operating speeds, transfer penalty, and snap settings. All inputs must use the same projected CRS in metres. Network intersections must be represented by shared vertices; snapping uses network vertices rather than points along edges.

`import_mpyy_gpkg_schema_profile` converts an administration-supplied UTF-8 CSV dictionary into the JSON contract accepted by `audit_mpyy_gpkg_schema_profile`. The explicit JSON mapping identifies table, field, SQLite type, and optional nullability, primary-key, geometry-type and SRS columns. Duplicate fields, malformed rows, ambiguous headers, invalid booleans and conflicting table geometry declarations are rejected. The output retains source institution, reference, version, source SHA-256, mapping and deterministic profile identity. The importer does not independently authenticate the issuing institution.

Use `resources/schema_dictionary.example.csv` with `resources/schema_import_mapping.example.json` to try the import workflow. Both are explicitly illustrative; replace them with the actual issuer's dictionary and metadata. Pass the resulting JSON profile to the existing read-only GeoPackage audit. The primary-key requirement is now enforced by that audit.

This milestone also documents the five existing urban analysis tools: building morphology, Spacematrix density, street network morphology, declared plan-metric scenario comparison, and population-weighted accessibility equity. These support analysis and report preparation without imposing statutory thresholds.

The multimodal routing engine now evaluates one-way travel from demand to facilities and reports mode sequences in that travel order. Regression coverage includes both direction aliases, segment-weighted explicit times, transfers, scenario output values, route loss/gain, CRS guards, dictionary identities, import input preservation and actual SQLite schema checks.

## 2.2.0 MPYY digital governance and multimodal access

The GeoPackage profile audit reads the dataset in SQLite read-only mode and applies a replaceable administration-supplied JSON contract for tables, fields, types, nullability, geometry registration, geometry types, and SRS identifiers. The plugin does not claim that its example is a Ministry schema. The dossier inventory records every file using a normalized relative path, byte size, and SHA-256 identity. Plan-note links reject unknown decision codes, while the version-chain audit detects forks, broken parent identities, duplicate content, and non-chronological revisions.

The multimodal engine runs a time-weighted, multi-source Dijkstra traversal across `WALK`, `BICYCLE`, and `TRANSIT` edges. It supports feature speeds, explicit travel times, one-way edges, transfer penalties, and walking access from demand or facility features to the network. Every travel-time threshold and operating speed is an explicit user input, not an invented MPYY limit.

Examples are available in `resources/gpkg_schema_profile.example.json`, `resources/plan_note_decision_links.example.json`, `resources/plan_version_chain.example.json`, and `resources/multimodal_network_fields.example.json`.

## 2.1.0 MPYY administrative integrity

The Article 7 participation register records the participation method, event evidence, stakeholder groups, outcomes, and how input was handled. MSP review additionally covers every stakeholder family named by Article 14/1-e. The cancelled-plan evidence tool records whether earlier institution opinions, analysis, and synthesis were reused, superseded, or rejected after explicit re-evaluation under Article 7/1-k.

The component-consistency tool keeps the same plan ID, version, level, and purpose across the plan sheet, official display, plan notes, and plan report. The approval-sheet register checks the Plan Transaction Number, approval date and number, stamp record, and SHA-256 identity on every sheet. The digital-delivery audit checks the Articles 34-35 component inventory, geological study, machine-readable geospatial data, declared Ministry profile, CRS, delivery receipt, Provincial Directorate destination, fifteen-day period, file containment, and checksums.

The dossier initializer creates editable manifests for all five workflows. Standalone examples are available in `resources/participation_register.example.json`, `resources/cancelled_plan_evidence.example.json`, `resources/plan_component_consistency.example.json`, `resources/approval_sheet_register.example.json`, and `resources/digital_delivery_manifest.example.json`.

## 2.0.0 MPYY dossier lifecycle

`initialize_mpyy_plan_dossier` creates a clean seven-part submission directory and editable manifests without overwriting a populated directory. `audit_mpyy_dossier_completeness` expands required file roles by plan level, purpose, lifecycle, and declared special context, then verifies path containment, file presence, and SHA-256 identity. This implements the dossier-wide unity and traceability workflow behind Articles 7 and 31-35 without claiming administrative approval.

`audit_mpyy_evidence_freshness` applies only validity dates or review intervals explicitly declared by the dossier owner. It deliberately does not invent a statutory age limit. `audit_mpyy_mixed_use_details` checks plan-report and plan-note detail at feature level and records the Article 21/10 residential maximum default of 0.30 when a ratio is absent. `audit_mpyy_publication_objection_register` checks simultaneous physical and web publication, minutes, local announcement, objection forwarding and decision chronology, and required republication after a plan change.

Editable inputs are provided in `resources/mpyy_dossier_manifest.example.json`, `resources/evidence_freshness_manifest.example.json`, `resources/publication_objection_manifest.example.json`, and `resources/mixed_use_fields.example.json`.

## 1.9.0 MPYY research, standards, legend, and intervention audits

The Article 8 dossier audit covers institutional inputs, digital delivery, National Geographic Information System portal review, research, threshold studies, and context-sensitive risk or conservation work. Under Article 8/2, expiry without a response is correctly recorded as `DEEMED_NO_NEGATIVE_OPINION`; it is not treated as a negative opinion or an automatic violation.

The Article 10 tool checks exact codes against the shipped e-Plan, MSP EK-1e, and 2026 supplemental catalogs. An unmatched code is marked `UNMAPPED_REVIEW` for Ministry-publication verification. The Article 11 tool covers EK-2, future needs, transport-informed parking, alternative standards, settled areas, conservation sites, and seasonal tourism housing. The Article 25 tool uses decision codes and geometry to distinguish revision, contiguous addition, and ordinary change review.

`consolidate_mpyy_audit_reports` verifies the SHA-256 identity of every JSON audit report and creates one status matrix. It does not average unlike findings into a misleading score. Editable Article 8 and Article 11 examples are provided in `resources/article8_research_manifest.example.json` and `resources/article11_standards_manifest.example.json`.

## 1.8.0 MPYY special-plan workflows

The Article 9 tool audits the declared plan-report structure, including mandatory plan-change rationale and mixed-use details. Sections that do not apply because of plan type, scale, scope, or characteristics can be excluded only with a recorded reason. The Article 12 tool selects the regulation's approximate walking-distance profile from the requested facility type, calculates routed pedestrian distance, and reports low-density, rural, or barrier-based paragraph-four cases separately as `EXCEPTION_REVIEW`.

Dedicated dossier tools now cover conservation plans under Article 27, integrated coastal area plans under Articles 28-29, and urban design projects under Article 30. They preserve paragraph-level references and produce reproducible SHA-256 reports, but do not replace professional assessment, protection-board decisions, commission decisions, or competent-authority approval. Editable examples are provided in `resources/mpyy_plan_report_manifest.example.json`, `resources/conservation_plan_manifest.example.json`, `resources/integrated_coastal_plan_manifest.example.json`, and `resources/urban_design_project_manifest.example.json`.

## 1.7.0 evidence provenance and routed accessibility

The evidence-provenance audit records the institution, date, version, CRS, scale or resolution, and SHA-256 identity of Article 22 inputs. Conditional coastal, basin, protection, and hazard contexts expand the required evidence set. Missing evidence produces an `INCOMPLETE` dossier result rather than an automatic legal decision about the plan. The institution-opinion register audits the initial and extended Article 8 periods without treating a missing response as an affirmative opinion. Ready-to-edit examples are available in `resources/evidence_provenance_manifest.example.json` and `resources/institution_opinion_register.example.json`.

Routed accessibility uses a vertex-snapped pedestrian or bicycle graph and a multi-source Dijkstra traversal from all facilities. Demand outputs distinguish accessible, over-threshold, disconnected, and unsnapped cases. Intersections are connected only where the input network contains a shared vertex, preserving grade-separated crossings. Adjacent-plan auditing measures seam coverage and decision-code conflicts. Plan-fabric auditing reports internal decision overlaps and emits uncovered boundary areas as a separate polygon layer.

## 1.6.0 MPYY evidence and plan-change audits

Article 22 threshold screening measures dissolved overlaps against six configurable evidence families and marks cases for specialist review without making an automatic legal suitability decision. Article 26 tools check road narrowing, lane reduction, minimum access dimensions, dead-end turning arrangements, facade separation, density impacts, silhouette evidence, and infrastructure balance documentation.

MSP monitoring evaluates weighted action-plan progress and overdue actions under Article 16. The CDP scope classifier detects decision-code changes even when the outer plan boundary is unchanged and separates declared whole-plan revision triggers from ordinary plan-change review. The NIP-UIP active-mobility audit builds an endpoint graph for pedestrian and bicycle lines, reports disconnected components, and screens center-to-network access. Metric tools require a projected common CRS.

## 1.5.0 MPYY plan-level audits

The four plan-level audit tools check identifiers, declared hierarchy, decision classification, geometry, configured scale, and level-specific content. MSP adds strategic-role and thematic coverage review; CDP checks region roles; NIP checks gross density and rejects parcel-level detail; UIP checks building order, intensity, height, and setbacks for buildable decisions. The hierarchy audit measures lower-plan coverage and explicit upper-group linkage. The submission dossier audit covers plan sheets, notes, reports, author evidence, Plan Transaction Number, approval, suspension, finalization, and digital delivery evidence under MPYY Articles 21 and 31-35.

New planning workspaces include `mpyy_2026_gosterim_katalogu`, sourced from the 22 January 2026 supplemental display registry. A valid dossier template is available at `resources/plan_submission_manifest.example.json`.

## 1.4.0 quality guarantees

Subdivision results include measured road contact, compactness, aspect ratio, legal-dimension, and area-balance diagnostics. Municipal by-law profiles are loaded from strictly validated, versioned JSON registries and may be replaced per audit. Workspace reconciliation can be previewed without writes through verified JSON impact reports. Official atlas layouts include a map-linked legend, CRS, scale identity, and explicit document verification URI. Procedural massing retains the finite-input, roof, floor-area, and FAR safeguards introduced in 1.3.0.

MSP symbology is generated from the Annex 1e PDF detail catalog in
`styles/msp_catalog.json`. Class, subclass, geometry, RGB, hatch and boundary rules
are converted to native QGIS symbols without a GeoServer runtime dependency.
E-Plan SLD files are supporting style sources.
