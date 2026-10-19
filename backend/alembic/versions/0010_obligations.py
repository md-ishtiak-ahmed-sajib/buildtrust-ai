from alembic import op
revision="0010"
down_revision="0009"


def upgrade():
    db=op.get_bind()
    db.exec_driver_sql("""CREATE TABLE obligations (
        id INTEGER PRIMARY KEY,project_id INTEGER NOT NULL REFERENCES projects(id),
        source_type VARCHAR NOT NULL,source_id INTEGER NOT NULL,category VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),
        currency VARCHAR NOT NULL,due_date VARCHAR,cash_movement_id INTEGER UNIQUE REFERENCES cash_movements(id),
        version INTEGER NOT NULL,UNIQUE(project_id,source_type,source_id))""")
    db.exec_driver_sql("CREATE INDEX ix_obligations_project_id ON obligations(project_id)")
    db.exec_driver_sql("""INSERT INTO obligations(project_id,source_type,source_id,category,direction,amount_minor,currency,due_date,cash_movement_id,version)
        SELECT project_id,'LEGACY_MOVEMENT',id,'OTHER',kind,CASE WHEN settled=1 THEN 0 ELSE amount_minor END,currency,due_date,id,1 FROM cash_movements""")


def downgrade():
    raise RuntimeError("Restore consistent backup; destructive downgrade disabled.")
