import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import create_app
from app.schemas import DocumentInput
from app.config import Settings

(ROOT / "docs").mkdir(exist_ok=True)
with TemporaryDirectory(prefix="buildtrust-contracts-") as temporary:
    application = create_app(Settings(data_dir=Path(temporary)), initialize=False)
    (ROOT / "docs" / "openapi.json").write_text(
        json.dumps(application.openapi(), indent=2), encoding="utf-8"
    )
    application.state.engine.dispose()
(ROOT / "demo" / "document.schema.json").write_text(
    json.dumps(DocumentInput.model_json_schema(), indent=2), encoding="utf-8"
)
print("Exported OpenAPI and document schema from actual application contracts")
