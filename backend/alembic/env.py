from alembic import context
from app.models import Base
from app import advanced_models  # noqa: F401 - register additive tables for metadata tooling
from app import review_models  # noqa: F401
from app import operations_models  # noqa: F401
from app import control_models  # noqa: F401
from app import commercial_models  # noqa: F401

connection = context.config.attributes.get("connection")
if connection is None:
    from app.config import get_settings
    from app.database import make_engine

    engine = make_engine(get_settings().data_dir / "buildtrust.db")
    connection = engine.connect()
context.configure(
    connection=connection, target_metadata=Base.metadata, render_as_batch=True
)
with context.begin_transaction():
    context.run_migrations()
