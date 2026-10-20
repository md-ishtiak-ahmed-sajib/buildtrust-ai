"""Measure scripts needed by the built HTML; record actual gzip bytes."""

import gzip
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
dist = ROOT / "frontend" / "dist"
html = (dist / "index.html").read_text()
paths = set(re.findall(r'(?:src|href)="(/assets/[^\"]+\.js)"', html))
sizes = {
    path: len(gzip.compress((dist / path.lstrip("/")).read_bytes(), compresslevel=6, mtime=0))
    for path in paths
}
baseline = 232480
actual = sum(sizes.values())
source_maps=[p.relative_to(dist).as_posix() for p in dist.rglob('*.map')]
map_directives=[p.relative_to(dist).as_posix() for p in dist.rglob('*.js') if re.search(r'(?m)^\s*//#\s*sourceMappingURL=',p.read_text(encoding='utf-8'))]
result = {
    "baseline_gzip_bytes": baseline,
    "initial_javascript_gzip_bytes": actual,
    "reduction_percent": round((baseline - actual) / baseline * 100, 2),
    "scripts": sizes,
    "source_map_files": source_maps,
    "source_map_directives": map_directives,
    "passed": actual <= baseline * 0.75 and not source_maps and not map_directives,
}
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data" / "asset-budget.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
assert result["passed"], "Initial JavaScript did not meet the 25% reduction target"
