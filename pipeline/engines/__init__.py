"""Local-only OCR adapters. Initialization never downloads model weights."""
from importlib.metadata import version
from pathlib import Path
from typing import Protocol


class OCREngine(Protocol):
    name: str
    version: str
    device: str
    models: list[str]

    def read(self, image) -> list[dict]: ...


class RapidEngine:
    name = 'RapidOCR'
    device = 'CPU'

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.version = version('rapidocr-onnxruntime') + ' / PP-OCRv4'
        self.models = ['PP-OCRv4 detection', 'PP-OCRv4 recognition']
        self.engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)

    def read(self, image):
        result, _ = self.engine(image, use_cls=False)
        return [{'text': text, 'confidence': float(conf), 'box': box, 'lines': [text]}
                for box, text, conf in (result or [])]


class PaddleEngine:
    name = 'PaddleOCR'
    device = 'CPU'

    def __init__(self, cfg):
        from paddleocr import PaddleOCR
        from pipeline.common import ROOT
        paths = [ROOT / cfg[key] for key in ('ocr_det_dir', 'ocr_rec_dir')]
        if not all(p.is_dir() for p in paths):
            raise RuntimeError('PaddleOCR requires existing local detection and recognition directories')
        self.version = version('paddleocr')
        self.models = [str(p) for p in paths]
        self.engine = PaddleOCR(det_model_dir=str(paths[0]), rec_model_dir=str(paths[1]),
                                lang='en', use_angle_cls=False, use_gpu=False, show_log=False)

    def read(self, image):
        result = self.engine.ocr(image, cls=False)
        return [{'text': r[1][0], 'confidence': float(r[1][1]), 'box': r[0], 'lines': [r[1][0]]}
                for r in ((result[0] or []) if result else [])]


def select_engine(cfg):
    choice = cfg.get('engine', 'auto')
    candidates = []
    if choice == 'paddle' or (choice == 'auto' and all(cfg['plate'].get(k) for k in ('ocr_det_dir', 'ocr_rec_dir'))):
        candidates.append(lambda: PaddleEngine(cfg['plate']))
    if choice in ('auto', 'rapid'):
        candidates.append(RapidEngine)
    errors = []
    for factory in candidates:
        try:
            return factory()
        except Exception as error:
            errors.append(f'{type(error).__name__}: {error}')
    raise RuntimeError('; '.join(errors) or 'Unknown OCR engine setting')
