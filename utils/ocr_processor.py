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

                # 优先使用 3.x 的 device 参数；失败时回退到旧版 use_gpu 参数。
                try:
                    device = "gpu:0" if cfg.use_gpu else "cpu"
                    self._paddle = PaddleOCR(lang="ch", device=device)
                except TypeError:
                    self._paddle = PaddleOCR(lang="ch", use_gpu=cfg.use_gpu)
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

                # 3.x: 可能返回对象列表或 dict，字段可能是 rec_texts / rec_scores / rec_text
                if not lines and isinstance(raw, list):
                    for obj in raw:
                        rec_texts = getattr(obj, "rec_texts", None)
                        rec_scores = getattr(obj, "rec_scores", None)

                        if isinstance(obj, dict):
                            rec_texts = rec_texts or obj.get("rec_texts") or obj.get("rec_text")
                            rec_scores = rec_scores or obj.get("rec_scores") or obj.get("rec_score")

                        if rec_texts and not isinstance(rec_texts, list):
                            rec_texts = [rec_texts]
                        if rec_scores and not isinstance(rec_scores, list):
                            rec_scores = [rec_scores]

                        if rec_texts:
                            for i, txt in enumerate(rec_texts):
                                txt = str(txt).strip()
                                if txt:
                                    lines.append(txt)
                                    if rec_scores and i < len(rec_scores):
                                        scores.append(float(rec_scores[i]))

                avg = (sum(scores) / len(scores)) if scores else 0.0
                final_text = "\n".join(lines).strip()
                return {
                    "text": final_text,
                    "confidence": round(avg, 4),
                    "engine": "paddle",
                    "ok": bool(final_text),
                    "error": None if final_text else "no_text_extracted",
                }
            except Exception as e:
                return {"text": "", "confidence": 0.0, "engine": "paddle", "ok": False, "error": str(e)}

        return {"text": "", "confidence": 0.0, "engine": self.cfg.engine, "ok": False, "error": "unknown engine"}
