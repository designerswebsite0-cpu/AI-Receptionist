from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    confidence: float | None
    engine: str
    # False when the OCR backend itself isn't reachable (e.g. no tesseract
    # binary on this machine) — distinct from a real scan that legitimately
    # found no text. The pipeline must branch on this, not on `text == ""`.
    available: bool


class OCRProvider:
    async def recognize(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError
