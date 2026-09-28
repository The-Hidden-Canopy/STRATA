"""Authoritative SQLite schema for STRATA projects."""

STRATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS strata_project (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_entity (
    entity_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_entity_alias (
    alias_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    alias TEXT NOT NULL,
    valid_time_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS strata_entity_relation (
    relation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    subject_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    relation_type TEXT NOT NULL,
    object_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    valid_time_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL,
    provenance_id TEXT
);
CREATE TABLE IF NOT EXISTS strata_state (
    state_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    valid_time_json TEXT NOT NULL,
    transaction_time_json TEXT NOT NULL,
    geometry_id TEXT,
    properties_json TEXT NOT NULL DEFAULT '{}',
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    geometry_class TEXT NOT NULL DEFAULT 'inferred',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_event (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    event_type TEXT NOT NULL,
    occurred_json TEXT NOT NULL,
    effects_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source (
    source_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    uri TEXT NOT NULL DEFAULT '',
    content_hash TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source_file (
    source_file_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    blob_hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    original_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source_region (
    region_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    page INTEGER,
    region_json TEXT NOT NULL DEFAULT '{}',
    label TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS strata_observation (
    observation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    region_id TEXT,
    entity_id TEXT,
    observed_json TEXT NOT NULL,
    extraction_json TEXT NOT NULL DEFAULT '{}',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_assertion (
    assertion_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    property_path TEXT NOT NULL,
    value_json TEXT NOT NULL,
    valid_time_json TEXT NOT NULL,
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_assertion_support (
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    observation_id TEXT NOT NULL REFERENCES strata_observation(observation_id),
    PRIMARY KEY(assertion_id, observation_id)
);
CREATE TABLE IF NOT EXISTS strata_assertion_conflict (
    conflict_id TEXT PRIMARY KEY,
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    conflicting_assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK(assertion_id <> conflicting_assertion_id)
);
CREATE TABLE IF NOT EXISTS strata_branch (
    branch_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    name TEXT NOT NULL,
    parent_branch_id TEXT REFERENCES strata_branch(branch_id),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name)
);
CREATE TABLE IF NOT EXISTS strata_branch_assertion (
    branch_id TEXT NOT NULL REFERENCES strata_branch(branch_id),
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected','unresolved')),
    PRIMARY KEY(branch_id, assertion_id)
);
CREATE TABLE IF NOT EXISTS strata_decision (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    branch_id TEXT NOT NULL REFERENCES strata_branch(branch_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    assertion_id TEXT REFERENCES strata_assertion(assertion_id),
    action TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_geometry (
    geometry_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    kind TEXT NOT NULL,
    content_hash TEXT,
    geometry_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_material (
    material_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    name TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_spatial_anchor (
    anchor_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    crs_json TEXT NOT NULL,
    coordinates_json TEXT NOT NULL,
    local_coordinates_json TEXT NOT NULL DEFAULT '{}',
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_provenance (
    provenance_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    inputs_json TEXT NOT NULL DEFAULT '[]',
    operation TEXT NOT NULL,
    tool TEXT NOT NULL,
    tool_version TEXT NOT NULL DEFAULT '',
    parameters_hash TEXT NOT NULL DEFAULT '',
    ai_model_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    output_hash TEXT
);
CREATE TABLE IF NOT EXISTS strata_import_job (
    import_job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    source_id TEXT,
    status TEXT NOT NULL,
    input_hash TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_export_job (
    export_job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    format TEXT NOT NULL,
    output_uri TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_tag (
    tag_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    label TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_timeline_marker (
    marker_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    label TEXT NOT NULL,
    time_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_user_note (
    note_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES strata_project(project_id),
    entity_id TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strata_entity_project ON strata_entity(project_id);
CREATE INDEX IF NOT EXISTS idx_strata_state_entity ON strata_state(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_source_project ON strata_source(project_id);
CREATE INDEX IF NOT EXISTS idx_strata_assertion_entity ON strata_assertion(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_event_entity ON strata_event(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_provenance_project ON strata_provenance(project_id);
"""
