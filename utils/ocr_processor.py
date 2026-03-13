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

                self._paddle = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    use_gpu=cfg.use_gpu,
                    show_log=False,
                )
            except Exception as e:
                raise RuntimeError(
                    "OCR engine=paddle 但未安装 paddleocr 或环境不满足，请先安装后重试"
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
                result = self._paddle.ocr(p, cls=True) if self._paddle else None
                lines = []
                scores = []
                for block in result or []:
                    for item in block or []:
                        txt = item[1][0]
                        score = float(item[1][1])
                        lines.append(txt)
                        scores.append(score)
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
