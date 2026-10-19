CREATE TABLE control_records (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	kind VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	parent_id INTEGER, 
	payload_json TEXT NOT NULL, 
	calculated_json TEXT NOT NULL, 
	contributors_json VARCHAR NOT NULL, 
	prepared_by INTEGER NOT NULL, 
	checked_by INTEGER, 
	approved_by INTEGER, 
	snapshot_hash VARCHAR, 
	snapshot_json TEXT, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(parent_id) REFERENCES control_records (id), 
	FOREIGN KEY(prepared_by) REFERENCES users (id), 
	FOREIGN KEY(checked_by) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);
CREATE INDEX ix_control_records_project_id ON control_records (project_id);
CREATE TABLE cost_codes (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, code), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);
CREATE TABLE accounting_journals (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	source_key VARCHAR NOT NULL, 
	record_id INTEGER, 
	business_date VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	evidence_json TEXT NOT NULL, 
	snapshot_hash VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, source_key), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(record_id) REFERENCES control_records (id)
);
CREATE INDEX ix_accounting_journals_project_id ON accounting_journals (project_id);
CREATE TABLE cost_code_links (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	cost_code_id INTEGER NOT NULL, 
	source_type VARCHAR NOT NULL, 
	source_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_type, source_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(cost_code_id) REFERENCES cost_codes (id)
);
CREATE TABLE receivable_balances (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	certificate_id INTEGER NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	received_minor INTEGER NOT NULL, 
	retention_minor INTEGER NOT NULL, 
	due_date VARCHAR, 
	currency VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (received_minor >= 0 AND received_minor <= amount_minor), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	UNIQUE (certificate_id), 
	FOREIGN KEY(certificate_id) REFERENCES control_records (id)
);
CREATE TABLE accounting_journal_lines (
	id INTEGER NOT NULL, 
	journal_id INTEGER NOT NULL, 
	account VARCHAR NOT NULL, 
	debit_minor INTEGER NOT NULL, 
	credit_minor INTEGER NOT NULL, 
	cost_code_id INTEGER, 
	PRIMARY KEY (id), 
	CHECK (debit_minor >= 0 AND credit_minor >= 0 AND NOT (debit_minor > 0 AND credit_minor > 0)), 
	FOREIGN KEY(journal_id) REFERENCES accounting_journals (id), 
	FOREIGN KEY(cost_code_id) REFERENCES cost_codes (id)
);
CREATE INDEX ix_accounting_journal_lines_journal_id ON accounting_journal_lines (journal_id);
CREATE TABLE payable_balances (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	invoice_id INTEGER, 
	record_id INTEGER NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	paid_minor INTEGER NOT NULL, 
	credit_minor INTEGER NOT NULL, 
	retention_minor INTEGER NOT NULL, 
	retention_released_minor INTEGER NOT NULL, 
	supplier_credit_minor INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	due_date VARCHAR, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (paid_minor >= 0 AND credit_minor >= 0 AND paid_minor+credit_minor <= amount_minor), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	UNIQUE (invoice_id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	UNIQUE (record_id), 
	FOREIGN KEY(record_id) REFERENCES control_records (id)
);
CREATE INDEX ix_payable_balances_project_id ON payable_balances (project_id);
CREATE TABLE cost_recognitions (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	record_id INTEGER NOT NULL, 
	receipt_line_id INTEGER NOT NULL, 
	cost_code_id INTEGER NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	quantity VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	invoice_id INTEGER, 
	source_hash VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	UNIQUE (record_id), 
	FOREIGN KEY(record_id) REFERENCES control_records (id), 
	UNIQUE (receipt_line_id), 
	FOREIGN KEY(receipt_line_id) REFERENCES receipt_lines (id), 
	FOREIGN KEY(cost_code_id) REFERENCES cost_codes (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);
