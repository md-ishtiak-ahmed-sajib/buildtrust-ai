"""Run in a bounded child process; stdout is machine-readable extraction only."""

import json
import sys
import contextlib
import base64
from pathlib import Path
import hashlib


if __name__ == "__main__":
    from parser_limits import constrain
    resource_limits = constrain()
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    with contextlib.redirect_stdout(sys.stderr):
        document = pymupdf.open(sys.argv[1])
        if document.needs_pass or len(document) > 50:
            raise ValueError("Encrypted or over-length PDF")
        if any(page.rect.width * page.rect.height > 25000000 for page in document):
            raise ValueError("PDF page dimensions exceed processing bounds")
        if len(sys.argv) > 2 and sys.argv[2] == "--preview":
            page = document[int(sys.argv[3]) - 1]
            scale = min(1.3, 2000 / page.rect.width, 2000 / page.rect.height)
            result = {
                "png": base64.b64encode(
                    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")
                ).decode("ascii")
            }
        else:
            ocr_status = "DISABLED"
            languages, tessdata, ocr_pages = [], None, 0
            if "--ocr" in sys.argv:
                index = sys.argv.index("--ocr")
                tessdata = Path(sys.argv[index + 1]).resolve()
                languages = sys.argv[index + 2].split("+")
                manifest = json.loads(
                    (
                        Path(__file__).resolve().parents[2]
                        / "docs"
                        / "ocr-models.lock.json"
                    ).read_text()
                )
                available = all(
                    language in manifest["models"]
                    and (tessdata / f"{language}.traineddata").is_file()
                    and hashlib.sha256(
                        (tessdata / f"{language}.traineddata").read_bytes()
                    ).hexdigest()
                    == manifest["models"][language]["sha256"]
                    for language in languages
                )
                ocr_status = "READY" if available else "MISSING_OR_UNVERIFIED_MODELS"
            pages, total = [], 0
            page_evidence = []
            for page in document:
                if any(
                    image[2] * image[3] > 25000000
                    for image in page.get_images(full=True)
                ):
                    raise ValueError("Embedded image exceeds decompression bounds")
                text = page.get_text(sort=True)
                method = "PDF_TEXT"
                if (
                    not text.strip()
                    and ocr_status in ("READY", "COMPLETED")
                    and ocr_pages < 5
                ):
                    if page.rect.width * page.rect.height * (150 / 72) ** 2 > 12000000:
                        raise ValueError("OCR raster exceeds pixel bounds")
                    textpage = page.get_textpage_ocr(
                        language="+".join(languages),
                        dpi=150,
                        full=True,
                        tessdata=str(tessdata),
                    )
                    text = page.get_text(textpage=textpage, sort=True)
                    method, ocr_status = "LOCAL_TESSERACT_OCR", "COMPLETED"
                    ocr_pages += 1
                page_evidence.append(
                    {
                        "page": page.number + 1,
                        "method": method,
                        "confidence": None,
                        "review_required": True,
                    }
                )
                total += len(text)
                if total > 250000:
                    raise ValueError("Extracted PDF text exceeds output bounds")
                pages.append(text)
            tables = []
            for page in document:
                for table in page.find_tables().tables:
                    tables.append({"page": page.number + 1, "rows": table.extract()})
                    if len(tables) > 500 or len(json.dumps(tables)) > 1000000:
                        raise ValueError("PDF table output exceeds bounds")
            result = {
                "pages": pages,
                "tables": tables,
                "page_evidence": page_evidence,
                "ocr": {
                    "status": ocr_status,
                    "languages": languages,
                    "pages_processed": ocr_pages,
                    "max_pages": 5,
                },
            }
    result["resource_limits"] = resource_limits
    print(json.dumps(result))
