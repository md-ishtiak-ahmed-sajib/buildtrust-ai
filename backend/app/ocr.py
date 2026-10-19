"""Explicit local model configuration. Application runtime never downloads models."""


def worker_args(settings):
    if not settings or not settings.ocr_enabled:
        return []
    return ["--ocr", str(settings.ocr_tessdata_dir or ""), settings.ocr_languages]
