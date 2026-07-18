from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import ValidationErrorApp
from app.knowledge.extraction.base import ExtractedContent

# Decompression-bomb guard — a small file can still decode to an enormous
# pixel buffer (PIL raises its own DecompressionBombError past ~89
# megapixels by default; this is a slightly tighter, explicit cap so the
# failure is one of our own error codes, not a bare Pillow exception).
_MAX_MEGAPIXELS = 40_000_000


def extract_image_metadata(content: bytes) -> ExtractedContent:
    """No OCR here — image text extraction goes through app.knowledge.ocr
    explicitly, driven by the pipeline's OCR-required decision, not
    automatically for every image. This function only validates the image
    decodes cleanly and reports its dimensions/format for knowledge_media.
    """
    try:
        image = Image.open(BytesIO(content))
        image.verify()
    except UnidentifiedImageError as exc:
        raise ValidationErrorApp("File is not a valid image") from exc

    # verify() leaves the file object unusable for further reads; reopen.
    image = Image.open(BytesIO(content))
    width, height = image.size
    if width * height > _MAX_MEGAPIXELS:
        raise ValidationErrorApp(f"Image is {width}x{height}, exceeding the {_MAX_MEGAPIXELS} pixel safety limit")

    return ExtractedContent(
        raw_text="",
        extraction_method="pillow",
        metadata={"width": width, "height": height, "format": image.format},
    )
