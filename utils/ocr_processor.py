from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any


@dataclass
class OCRConfig:
    enabled: bool = False
    engine: str = "tesseract"  # tesseract | paddle
    lang: str = "chi_sim+eng"
    use_gpu: bool = False


class OCRProcessor:
    """本地 OCR 处理器。

    - 默认仅使用本地资源，不走任何云 API。
    - 支持 tesseract / paddle（按需安装依赖）。
    """

    def __init__(self, cfg: OCRConfig):
        self.cfg = cfg
        self._paddle = None
        if not cfg.enabled:
            return

        if cfg.engine == "paddle":
            try:
                from paddleocr import PaddleOCR  # type: ignore

                # PaddleOCR 3.x 参数已变更，不再接受 use_gpu。
                # 这里使用默认设备策略（CPU），保持兼容。
                self._paddle = PaddleOCR(lang="ch")
            except Exception as e:
                raise RuntimeError(
                    f"OCR engine=paddle 初始化失败，请检查 paddleocr 版本/环境：{e}"
                ) from e

    def extract(self, image_path: str | Path) -> Dict[str, Any]:
        p = str(image_path)
        if not self.cfg.enabled:
            return {"text": "", "confidence": 0.0, "engine": "off", "ok": False, "error": "ocr disabled"}

        if self.cfg.engine == "tesseract":
            try:
                import pytesseract  # type: ignore
                from PIL import Image  # type: ignore

                text = pytesseract.image_to_string(Image.open(p), lang=self.cfg.lang)
                return {"text": text.strip(), "confidence": 0.0, "engine": "tesseract", "ok": True}
            except Exception as e:
                return {"text": "", "confidence": 0.0, "engine": "tesseract", "ok": False, "error": str(e)}

        if self.cfg.engine == "paddle":
            try:
                if not self._paddle:
                    return {"text": "", "confidence": 0.0, "engine": "paddle", "ok": False, "error": "paddle not initialized"}

                # 兼容 paddleocr 2.x / 3.x
                try:
                    raw = self._paddle.ocr(p, cls=True)
                except TypeError:
                    raw = self._paddle.predict(p)

                lines = []
                scores = []

                # 2.x: [[ [box, [text, score]], ... ]]
                if isinstance(raw, list):
                    for block in raw:
                        if isinstance(block, list):
                            for item in block:
                                if isinstance(item, (list, tuple)) and len(item) >= 2:
                                    rec = item[1]
                                    if isinstance(rec, (list, tuple)) and len(rec) >= 2:
                                        txt = str(rec[0]).strip()
                                        sc = float(rec[1])
                                        if txt:
                                            lines.append(txt)
                                            scores.append(sc)

                # 3.x: 可能返回对象列表，含 rec_texts / rec_scores
                if not lines and isinstance(raw, list):
                    for obj in raw:
                        rec_texts = getattr(obj, "rec_texts", None)
                        rec_scores = getattr(obj, "rec_scores", None)
                        if rec_texts:
                            for i, txt in enumerate(rec_texts):
                                txt = str(txt).strip()
                                if txt:
                                    lines.append(txt)
                                    if rec_scores and i < len(rec_scores):
                                        scores.append(float(rec_scores[i]))

                avg = (sum(scores) / len(scores)) if scores else 0.0
                return {
                    "text": "\n".join(lines).strip(),
                    "confidence": round(avg, 4),
                    "engine": "paddle",
                    "ok": True,
                }
            except Exception as e:
                return {"text": "", "confidence": 0.0, "engine": "paddle", "ok": False, "error": str(e)}

        return {"text": "", "confidence": 0.0, "engine": self.cfg.engine, "ok": False, "error": "unknown engine"}
