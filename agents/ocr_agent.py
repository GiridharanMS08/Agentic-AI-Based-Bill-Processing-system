from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import io
from PIL import Image, ImageOps, ImageEnhance
import fitz  # PyMuPDF
from rapidocr import RapidOCR


class OCRAgent:
    name = 'OCR Agent'

    def __init__(self, settings):
        self.settings = settings
        self.engine = RapidOCR()

    @staticmethod
    def _confidence(result) -> Decimal:
        scores = []
        txts = getattr(result, 'txts', None) or []
        probs = getattr(result, 'scores', None) or []
        for p in probs:
            try:
                scores.append(float(p) * 100)
            except (TypeError, ValueError):
                pass
        if not scores and txts:
            # Some RapidOCR versions expose no scores; use a neutral non-zero value.
            return Decimal('60.00')
        return Decimal(str(round(sum(scores) / len(scores), 2))) if scores else Decimal('0.00')

    def _run_image(self, image: Image.Image):
        image = ImageOps.exif_transpose(image).convert('RGB')
        image = ImageEnhance.Contrast(image).enhance(1.25)
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        import numpy as np
        arr = np.frombuffer(buf.getvalue(), dtype=np.uint8)
        import cv2
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        result = self.engine(frame)
        txts = getattr(result, 'txts', None) or []
        text = '\n'.join(str(x).strip() for x in txts if str(x).strip())
        return text, self._confidence(result)

    def run(self, filename, content):
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("Only JPG, JPEG and PNG bill photos are supported")

        image = Image.open(io.BytesIO(content))
        text, confidence = self._run_image(image)
        return text, confidence
