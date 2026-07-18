"""pytesseract binding to the Tesseract OCR binary. Confirmed absent from
this dev machine (`where tesseract` found nothing) — recognize() reports
available=False rather than raising, so callers (the ingestion pipeline)
can record a real OCR_FAILED processing status instead of crashing or,
worse, silently treating a source as fully processed.
"""

import asyncio
import shutil
from io import BytesIO

import pytesseract
from PIL import Image

from app.config import get_settings
from app.knowledge.ocr.base import OCRProvider, OCRResult


class TesseractOCRProvider(OCRProvider):
    def __init__(self, tesseract_cmd: str | None = None):
        settings = get_settings()
        configured_cmd = tesseract_cmd or settings.tesseract_cmd
        if configured_cmd:
            pytesseract.pytesseract.tesseract_cmd = configured_cmd
        self._binary_path = shutil.which(configured_cmd or "tesseract")

    async def recognize(self, image_bytes: bytes) -> OCRResult:
        if not self._binary_path:
            return OCRResult(text="", confidence=None, engine="tesseract", available=False)
        return await asyncio.to_thread(self._recognize_sync, image_bytes)

    def _recognize_sync(self, image_bytes: bytes) -> OCRResult:
        image = Image.open(BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        words = [word for word in data["text"] if word.strip()]
        confidences = [
            float(conf) for conf, word in zip(data["conf"], data["text"], strict=True) if word.strip() and conf != "-1"
        ]
        text = " ".join(words)
        avg_confidence = sum(confidences) / len(confidences) if confidences else None

        return OCRResult(text=text, confidence=avg_confidence, engine="tesseract", available=True)
