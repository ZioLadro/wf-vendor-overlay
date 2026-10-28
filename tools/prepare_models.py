"""Downloads (if missing) all the rapidocr OCR models, so that they end up in the exe."""
import pathlib

import numpy as np
import rapidocr
from PIL import Image, ImageDraw, ImageFont
from rapidocr import RapidOCR

im = Image.new("RGB", (700, 160), (20, 25, 35))
ImageDraw.Draw(im).text((20, 40), "MIRAGE PRIME BLUEPRINT", fill=(230, 230, 230),
                        font=ImageFont.load_default(size=44))
res = RapidOCR()(np.array(im)[:, :, ::-1].copy())   # runs all 3 stages: det, cls, rec
print("Test OCR:", res.txts)
models = sorted(p.name for p in (pathlib.Path(rapidocr.__file__).parent / "models").glob("*.onnx"))
print("Models present:", models)
assert len(models) >= 3, "OCR models are missing"
