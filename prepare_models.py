"""Scarica (se mancano) tutti i modelli OCR di rapidocr, cosi' finiscono nell'exe."""
import pathlib

import numpy as np
import rapidocr
from PIL import Image, ImageDraw, ImageFont
from rapidocr import RapidOCR

im = Image.new("RGB", (700, 160), (20, 25, 35))
ImageDraw.Draw(im).text((20, 40), "MIRAGE PRIME BLUEPRINT", fill=(230, 230, 230),
                        font=ImageFont.load_default(size=44))
res = RapidOCR()(np.array(im)[:, :, ::-1].copy())   # tutte e 3 le fasi: det, cls, rec
print("OCR di prova:", res.txts)
models = sorted(p.name for p in (pathlib.Path(rapidocr.__file__).parent / "models").glob("*.onnx"))
print("Modelli presenti:", models)
assert len(models) >= 3, "Mancano dei modelli OCR"
