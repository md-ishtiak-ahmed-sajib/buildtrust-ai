CREATE TABLE projects (
	id INTEGER NOT NULL, 
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	client VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	budget_minor INTEGER NOT NULL, 
	balance_minor INTEGER NOT NULL, 
	reserve_minor INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	run_id VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (balance_minor >= 0), 
	CHECK (reserve_minor >= 0), 
	UNIQUE (code)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);

CREATE TABLE audit_events (
	id INTEGER NOT NULL, 
	project_id INTEGER, 
	actor_id INTEGER, 
	actor_name VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	event_type VARCHAR NOT NULL, 
	entity_type VARCHAR NOT NULL, 
	entity_id VARCHAR NOT NULL, 
	details_json TEXT NOT NULL, 
	previous_hash VARCHAR NOT NULL, 
	event_hash VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE documents (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	document_type VARCHAR NOT NULL, 
	original_filename VARCHAR NOT NULL, 
	storage_name VARCHAR NOT NULL, 
	sha256 VARCHAR NOT NULL, 
	extraction_status VARCHAR NOT NULL, 
	extracted_json TEXT NOT NULL, 
	text TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	reviewed_by INTEGER, 
	confirmed_by INTEGER, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id), 
	FOREIGN KEY(confirmed_by) REFERENCES users (id)
);

CREATE INDEX ix_documents_project_id ON documents (project_id);

CREATE INDEX ix_documents_sha256 ON documents (sha256);

CREATE TABLE memberships (
	user_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	PRIMARY KEY (user_id, project_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE suppliers (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	approved BOOLEAN NOT NULL, 
	beneficiary_token VARCHAR NOT NULL, 
	beneficiary_fingerprint VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, code), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE boq_items (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	item_code VARCHAR NOT NULL, 
	description VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	quantity VARCHAR NOT NULL, 
	rate VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, item_code), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);

CREATE TABLE extraction_revisions (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	fields_json TEXT NOT NULL, 
	actor_id INTEGER, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id, version), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE purchase_orders (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	number VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	tax_percent VARCHAR NOT NULL, 
	retention_percent VARCHAR NOT NULL, 
	discount_minor INTEGER NOT NULL, 
	approved BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, number), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE goods_receipts (
	id INTEGER NOT NULL, 
	po_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	number VARCHAR NOT NULL, 
	approved_by INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (po_id, number), 
	FOREIGN KEY(po_id) REFERENCES purchase_orders (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE TABLE invoices (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	supplier_id INTEGER, 
	po_id INTEGER, 
	supplier_code VARCHAR NOT NULL, 
	number VARCHAR NOT NULL, 
	invoice_date VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	subtotal_minor INTEGER NOT NULL, 
	tax_minor INTEGER NOT NULL, 
	retention_minor INTEGER NOT NULL, 
	discount_minor INTEGER NOT NULL, 
	total_minor INTEGER NOT NULL, 
	beneficiary_fingerprint VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, supplier_code, number), 
	CHECK (total_minor > 0), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(po_id) REFERENCES purchase_orders (id)
);

CREATE TABLE purchase_order_lines (
	id INTEGER NOT NULL, 
	po_id INTEGER NOT NULL, 
	item_code VARCHAR NOT NULL, 
	description VARCHAR NOT NULL, 
	quantity VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	rate VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (po_id, item_code), 
	FOREIGN KEY(po_id) REFERENCES purchase_orders (id)
);

CREATE TABLE variations (
	id INTEGER NOT NULL, 
	boq_item_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	quantity VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	approved_by INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(boq_item_id) REFERENCES boq_items (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE TABLE cash_movements (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	kind VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	due_date VARCHAR NOT NULL, 
	description VARCHAR NOT NULL, 
	invoice_id INTEGER, 
	settled BOOLEAN NOT NULL, 
	cost_pressure BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_minor >= 0), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE invoice_lines (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	item_code VARCHAR NOT NULL, 
	description VARCHAR NOT NULL, 
	quantity VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	rate VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE payment_proposals (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	supplier_id INTEGER, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	beneficiary_fingerprint VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	requested_by INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	snapshot_hash VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_minor > 0), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id)
);

CREATE INDEX ix_payment_proposals_invoice_id ON payment_proposals (invoice_id);

CREATE UNIQUE INDEX uq_active_invoice_proposal ON payment_proposals (invoice_id) WHERE status IN ('PENDING_APPROVAL', 'APPROVED', 'EXECUTING', 'SETTLED');

CREATE TABLE receipt_lines (
	id INTEGER NOT NULL, 
	receipt_id INTEGER NOT NULL, 
	item_code VARCHAR NOT NULL, 
	quantity VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (receipt_id, item_code), 
	FOREIGN KEY(receipt_id) REFERENCES goods_receipts (id)
);

CREATE TABLE verification_results (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	report_json TEXT NOT NULL, 
	analyzed_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE INDEX ix_verification_results_invoice_id ON verification_results (invoice_id);

CREATE TABLE workflows (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	result_json TEXT NOT NULL, 
	error VARCHAR, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE approvals (
	id INTEGER NOT NULL, 
	proposal_id INTEGER NOT NULL, 
	approver_id INTEGER NOT NULL, 
	decision VARCHAR NOT NULL, 
	snapshot_hash VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(proposal_id) REFERENCES payment_proposals (id), 
	FOREIGN KEY(approver_id) REFERENCES users (id)
);

CREATE TABLE execution_attempts (
	id INTEGER NOT NULL, 
	proposal_id INTEGER NOT NULL, 
	idempotency_key VARCHAR NOT NULL, 
	request_hash VARCHAR NOT NULL, 
	status_code INTEGER NOT NULL, 
	response_json TEXT NOT NULL, 
	actor_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(proposal_id) REFERENCES payment_proposals (id), 
	UNIQUE (idempotency_key), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE payments (
	id INTEGER NOT NULL, 
	proposal_id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	mock_transaction_id VARCHAR NOT NULL, 
	idempotency_key VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	executed_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_minor > 0), 
	UNIQUE (proposal_id), 
	FOREIGN KEY(proposal_id) REFERENCES payment_proposals (id), 
	UNIQUE (invoice_id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	UNIQUE (mock_transaction_id), 
	UNIQUE (idempotency_key)
);

CREATE TABLE receipt_allocations (
	id INTEGER NOT NULL, 
	proposal_id INTEGER NOT NULL, 
	receipt_line_id INTEGER NOT NULL, 
	invoice_line_id INTEGER NOT NULL, 
	canonical_quantity VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (proposal_id, receipt_line_id, invoice_line_id), 
	FOREIGN KEY(proposal_id) REFERENCES payment_proposals (id), 
	FOREIGN KEY(receipt_line_id) REFERENCES receipt_lines (id), 
	FOREIGN KEY(invoice_line_id) REFERENCES invoice_lines (id)
);

CREATE TABLE reservations (
	id INTEGER NOT NULL, 
	proposal_id INTEGER NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	state VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (proposal_id), 
	FOREIGN KEY(proposal_id) REFERENCES payment_proposals (id)
);

CREATE TABLE workflow_steps (
	id INTEGER NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	tool VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	input_json TEXT NOT NULL, 
	output_json TEXT NOT NULL, 
	started_at VARCHAR NOT NULL, 
	finished_at VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflows (id)
);

CREATE TABLE ledger_entries (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	payment_id INTEGER NOT NULL, 
	account VARCHAR NOT NULL, 
	direction VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (payment_id, account), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(payment_id) REFERENCES payments (id)
);
