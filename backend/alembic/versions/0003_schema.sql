
CREATE TABLE measurement_profiles (
	id INTEGER NOT NULL, 
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	edition VARCHAR NOT NULL, 
	source_url VARCHAR NOT NULL, 
	rules_json TEXT NOT NULL, 
	verification_status VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
)

;

CREATE TABLE estimate_versions (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	estimate_key VARCHAR NOT NULL, 
	revision INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	parent_id INTEGER, 
	name VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	fields_json TEXT NOT NULL, 
	calculated_json TEXT NOT NULL, 
	total_minor INTEGER NOT NULL, 
	prepared_by INTEGER NOT NULL, 
	checked_by INTEGER, 
	approved_by INTEGER, 
	snapshot_hash VARCHAR, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, estimate_key, revision), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(parent_id) REFERENCES estimate_versions (id), 
	FOREIGN KEY(prepared_by) REFERENCES users (id), 
	FOREIGN KEY(checked_by) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;

CREATE TABLE exchange_rate_observations (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	base VARCHAR NOT NULL, 
	quote VARCHAR NOT NULL, 
	factor VARCHAR NOT NULL, 
	source VARCHAR NOT NULL, 
	observed_date VARCHAR NOT NULL, 
	actor_id INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;

CREATE TABLE materials (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	specification_json TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE TABLE takeoff_sheets (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	profile_id INTEGER NOT NULL, 
	fields_json TEXT NOT NULL, 
	result_json TEXT NOT NULL, 
	prepared_by INTEGER NOT NULL, 
	checked_by INTEGER, 
	status VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(profile_id) REFERENCES measurement_profiles (id), 
	FOREIGN KEY(prepared_by) REFERENCES users (id), 
	FOREIGN KEY(checked_by) REFERENCES users (id)
)

;

CREATE TABLE budget_baselines (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	estimate_id INTEGER NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	snapshot_hash VARCHAR NOT NULL, 
	approved_by INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	UNIQUE (estimate_id), 
	FOREIGN KEY(estimate_id) REFERENCES estimate_versions (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;

CREATE TABLE price_searches (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	fingerprint VARCHAR NOT NULL, 
	request_json TEXT NOT NULL, 
	states_json TEXT NOT NULL, 
	status VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(material_id) REFERENCES materials (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;

CREATE TABLE supplier_quotations (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	fields_json TEXT NOT NULL, 
	status VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	prepared_by INTEGER NOT NULL, 
	verified_by INTEGER, 
	storage_name VARCHAR, 
	original_filename VARCHAR, 
	attachment_hash VARCHAR, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(material_id) REFERENCES materials (id), 
	FOREIGN KEY(prepared_by) REFERENCES users (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id)
)

;

CREATE TABLE price_observations (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	search_id INTEGER, 
	quotation_id INTEGER, 
	provider VARCHAR NOT NULL, 
	source_type VARCHAR NOT NULL, 
	payload_json TEXT NOT NULL, 
	evidence_hash VARCHAR NOT NULL, 
	retrieved_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(material_id) REFERENCES materials (id), 
	FOREIGN KEY(search_id) REFERENCES price_searches (id), 
	FOREIGN KEY(quotation_id) REFERENCES supplier_quotations (id)
)

;

CREATE TABLE material_equivalents (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	observation_id INTEGER NOT NULL, 
	approved_by INTEGER NOT NULL, 
	reason VARCHAR NOT NULL, 
	material_version INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(material_id) REFERENCES materials (id), 
	UNIQUE (observation_id), 
	FOREIGN KEY(observation_id) REFERENCES price_observations (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;

CREATE TABLE price_selections (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	estimate_id INTEGER NOT NULL, 
	observation_id INTEGER NOT NULL, 
	line_id VARCHAR NOT NULL, 
	component_id VARCHAR NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	snapshot_hash VARCHAR NOT NULL, 
	reason VARCHAR NOT NULL, 
	actor_id INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(estimate_id) REFERENCES estimate_versions (id), 
	FOREIGN KEY(observation_id) REFERENCES price_observations (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
CREATE INDEX ix_estimate_versions_project_id ON estimate_versions (project_id);
CREATE INDEX ix_materials_project_id ON materials (project_id);
CREATE INDEX ix_takeoff_sheets_project_id ON takeoff_sheets (project_id);
CREATE INDEX ix_budget_baselines_project_id ON budget_baselines (project_id);
CREATE INDEX ix_price_searches_fingerprint ON price_searches (fingerprint);
CREATE INDEX ix_price_searches_project_id ON price_searches (project_id);
CREATE INDEX ix_supplier_quotations_project_id ON supplier_quotations (project_id);
CREATE INDEX ix_price_observations_project_id ON price_observations (project_id);
