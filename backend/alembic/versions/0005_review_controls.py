"""Retained authorship and explicit commitment coverage; historical evidence unchanged."""
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql("""CREATE TABLE record_contributors (
      id INTEGER PRIMARY KEY, entity_type VARCHAR NOT NULL, entity_id INTEGER NOT NULL,
      actor_id INTEGER NOT NULL REFERENCES users(id), evidence VARCHAR NOT NULL,
      created_at VARCHAR NOT NULL, UNIQUE(entity_type, entity_id, actor_id))""")
    db.exec_driver_sql("""CREATE TABLE commitment_coverage (
      id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
      boq_item_id INTEGER NOT NULL REFERENCES boq_items(id),
      po_line_id INTEGER NOT NULL UNIQUE REFERENCES purchase_order_lines(id),
      source_hash VARCHAR NOT NULL, quantity VARCHAR NOT NULL, unit VARCHAR NOT NULL,
      method VARCHAR NOT NULL, created_at VARCHAR NOT NULL)""")
    # Retain original approvals/audit. Authorship reconstruction only adds evidence.
    for table, kind in (("estimate_versions", "estimate"), ("supplier_quotations", "quotation")):
        db.exec_driver_sql(f"""INSERT OR IGNORE INTO record_contributors
            (entity_type, entity_id, actor_id, evidence, created_at)
            SELECT '{kind}', id, prepared_by, 'legacy preparer', created_at FROM {table}""")
    db.exec_driver_sql("""INSERT OR IGNORE INTO record_contributors
      (entity_type, entity_id, actor_id, evidence, created_at)
      SELECT entity_type, CAST(entity_id AS INTEGER), actor_id, 'audit:' || id, created_at
      FROM audit_events WHERE actor_id IS NOT NULL AND
      event_type IN ('ESTIMATE_CREATED','ESTIMATE_UPDATED','ESTIMATE_REVISED',
        'ESTIMATE_BOQ_IMPORTED','PRICE_SELECTED','QUOTATION_DRAFTED','QUOTATION_CREATED','QUOTATION_CORRECTED')""")
    db.exec_driver_sql("""WITH RECURSIVE lineage(child, ancestor) AS (
        SELECT id, parent_id FROM estimate_versions WHERE parent_id IS NOT NULL
        UNION ALL SELECT lineage.child, e.parent_id FROM lineage
        JOIN estimate_versions e ON e.id=lineage.ancestor WHERE e.parent_id IS NOT NULL)
        INSERT OR IGNORE INTO record_contributors(entity_type,entity_id,actor_id,evidence,created_at)
        SELECT 'estimate', l.child, c.actor_id, 'retained legacy ancestor:' || l.ancestor, c.created_at
        FROM lineage l JOIN record_contributors c ON c.entity_type='estimate' AND c.entity_id=l.ancestor""")
    # Pending submissions predate contributor-bound snapshots and must be revised.
    # Approved versions are intentionally not rewritten.
    db.exec_driver_sql("""UPDATE estimate_versions SET status='SUPERSEDED', version=version+1
        WHERE status IN ('SUBMITTED','CHECKED')""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
