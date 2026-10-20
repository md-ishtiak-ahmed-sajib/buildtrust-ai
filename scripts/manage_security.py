"""Run local-owner security tools from the repository root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.local_security import main

if __name__ == "__main__":
    main()
