from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict

import schedule
import time
import yaml

from crawler.weibo_crawler import WeiboCrawler
from storage.storage_manager import StorageManager
from tracking.history_tracker import HistoryTracker
from utils.logger import setup_logger
from utils.ocr_processor import OCRConfig, OCRProcessor


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_runtime_overrides(cfg: dict, base_dir: str | None = None):
    if not base_dir:
        return cfg

    cfg.setdefault("storage", {})["base_dir"] = base_dir
    cfg["storage"]["db_path"] = str(Path(base_dir) / "history.db")
    cfg.setdefault("logging", {})["file"] = str(Path(base_dir) / "logs" / "weibo_crawler.log")

    if "ocr" in cfg:
        cfg["ocr"]["output_jsonl"] = "raw/ocr.jsonl"

    return cfg


def _infer_signal_asset(text: str) -> str:
    t = text.lower()
    if "btc" in t or "比特币" in t:
        return "BTC"
    if "eth" in t or "以太坊" in t:
        return "ETH"
    if "纳指" in t or "美股" in t or "spx" in t:
        return "US_EQ"
    if "美元" in t or "美联储" in t:
        return "MACRO"
    return "UNKNOWN"


def _next_consecutive_processed(
    consecutive_processed: int,
    already_processed: bool,
    reprocess_ocr: bool,
) -> int:
    if reprocess_ocr:
        return 0
    return consecutive_processed + 1 if already_processed else 0


def run_once(cfg: dict, reprocess_ocr: bool = False):
    logger = setup_logger(
        cfg["logging"]["file"],
        level=cfg["logging"].get("level", "INFO"),
        console=cfg["logging"].get("console", True),
    )

    crawler = WeiboCrawler(
        cookie=cfg["auth"]["cookie"],
        user_agent=cfg["network"]["user_agent"],
        delay_min=cfg["network"].get("delay_min", 3),
        delay_max=cfg["network"].get("delay_max", 8),
        timeout=cfg["network"].get("timeout", 10),
        max_retries=cfg["network"].get("max_retries", 3),
    )
    storage = StorageManager(cfg["storage"]["base_dir"])
    tracker = HistoryTracker(cfg["storage"]["db_path"])

    ocr_cfg = cfg.get("ocr", {})
    ocr = OCRProcessor(
        OCRConfig(
            enabled=ocr_cfg.get("enabled", False),
            engine=ocr_cfg.get("engine", "tesseract"),
            lang=ocr_cfg.get("lang", "chi_sim+eng"),
            use_gpu=ocr_cfg.get("use_gpu", False),
        )
    )
    ocr_jsonl = ocr_cfg.get("output_jsonl", "raw/ocr.jsonl")
    signals_jsonl = "curated/signals.jsonl"

    since_date = cfg["targets"].get("since_date")
    include_retweets = cfg["targets"].get("include_retweets", False)
    dl_images = cfg["download"].get("images", True)
    img_timeout = cfg["download"].get("image_timeout", 15)
    reprocess_download_images = ocr_cfg.get("reprocess_download_images", True)

    day_stats: Dict[str, Dict] = defaultdict(lambda: {"posts": 0, "images": 0, "uids": set(), "ocr_images": 0})

    for uid in cfg["targets"]["user_ids"]:
        logger.info(f"开始抓取 UID={uid}")

        stop_threshold = 10
        consecutive_processed = 0

        for page in range(1, 11):
            try:
                data = crawler.fetch_user_page(uid, page=page)
                cards = crawler.parse_cards(data, since_date=since_date, include_retweets=include_retweets)
            except Exception as e:
                logger.error(f"拉取失败 uid={uid} page={page}: {e}")
                continue

            if not cards:
                logger.info(f"uid={uid} page={page} 无可处理微博，结束该用户抓取")
                break

            new_count = 0
            for post in cards:
                already_processed = tracker.is_processed(post["id"])
                consecutive_processed = _next_consecutive_processed(
                    consecutive_processed=consecutive_processed,
                    already_processed=already_processed,
                    reprocess_ocr=reprocess_ocr,
                )
                if already_processed and not reprocess_ocr:
                    if consecutive_processed >= stop_threshold:
                        break
                    continue
                saved = storage.save_post(
                    post,
                    download_images=(reprocess_download_images if reprocess_ocr else dl_images),
                    image_timeout=img_timeout,
                    append_post_row=(not already_processed),
                )
                if not already_processed:
                    tracker.mark_processed(
                        saved["post_id"],
                        uid,
                        int(post["created_ts"]),
                        source_post_id=post["id"],
                    )
                    new_count += 1

                date_key = datetime.fromtimestamp(int(post["created_ts"])).strftime("%Y-%m-%d")
                day_stats[date_key]["posts"] += 1
                day_stats[date_key]["images"] += saved["images_saved"]
                day_stats[date_key]["uids"].add(uid)

                ocr_texts = []
                if ocr_cfg.get("enabled", False) and saved["image_paths"]:
                    for image_path in saved["image_paths"]:
                        img = Path(image_path)
                        result = ocr.extract(img)
                        if result.get("ok"):
                            day_stats[date_key]["ocr_images"] += 1
                        text = result.get("text", "")
                        if text:
                            ocr_texts.append(text)

                        storage.append_jsonl(
                            ocr_jsonl,
                            {
                                "post_id": saved["post_id"],
                                "source_post_id": saved.get("source_post_id"),
                                "image": str(img),
                                "image_sha256": storage.file_sha256(img),
                                "engine": result.get("engine"),
                                "ok": result.get("ok"),
                                "confidence": result.get("confidence", 0.0),
                                "text": text,
                                "error": result.get("error"),
                                "created_at": datetime.now().isoformat(),
                            },
                        )

                    if ocr_texts:
                        (Path(saved["image_dir"]) / "ocr.txt").write_text("\n\n".join(ocr_texts), encoding="utf-8")

                merged_text = (post.get("text", "") + "\n" + "\n".join(ocr_texts)).strip()
                if not already_processed:
                    storage.append_jsonl(
                        signals_jsonl,
                        {
                            "source_post_id": saved.get("source_post_id", saved["post_id"]),
                            "local_post_id": saved["post_id"],
                            "author": uid,
                            "published_at": post.get("created_at"),
                            "asset": _infer_signal_asset(merged_text),
                            "stance": "neutral",
                            "horizon": "unknown",
                            "confidence": "low",
                            "evidence_text": (merged_text[:280] if merged_text else post.get("text", "")[:280]),
                            "tags": [],
                            "ocr_used": bool(ocr_texts),
                        },
                    )

                logger.info(f"post={saved['post_id']} images={saved['images_saved']} saved={saved['image_dir']}")

            logger.info(f"uid={uid} page={page} 新增 {new_count} 条")

            if consecutive_processed >= stop_threshold:
                logger.info(f"uid={uid} 连续遇到 {consecutive_processed} 条已下载数据，触发提前终止策略。")
                break

    # 生成 curated/daily_summary.md（本轮）
    lines = ["# Daily Summary (This Run)", ""]
    for date_key in sorted(day_stats.keys()):
        st = day_stats[date_key]
        lines.extend(
            [
                f"## {date_key}",
                f"- posts: {st['posts']}",
                f"- images: {st['images']}",
                f"- ocr_images_ok: {st['ocr_images']}",
                f"- uids: {', '.join(sorted(st['uids']))}",
                "",
            ]
        )
    storage.write_daily_summary(datetime.now().strftime("%Y-%m-%d"), lines)

    weekly_path = Path(cfg["storage"]["base_dir"]) / "curated" / "weekly_summary.md"
    if not weekly_path.exists():
        weekly_path.write_text("# Weekly Summary\n\n(待生成)\n", encoding="utf-8")

    logger.info("本轮任务完成")


def main():
    parser = argparse.ArgumentParser(description="微博数据自动化采集与归档系统")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--mode", choices=["once", "daemon"], default=None)
    parser.add_argument("--base-dir", default=None, help="覆盖 storage.base_dir（例如 /mnt/weibo_data）")
    parser.add_argument("--reprocess-ocr", action="store_true", help="对已处理微博强制重下图片并重跑 OCR")
    parser.add_argument(
        "--run-full-ocr-after",
        action="store_true",
        help="本轮抓取完成后再执行一次全量 OCR（等价于追加一次 --reprocess-ocr）",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg = apply_runtime_overrides(cfg, base_dir=args.base_dir)
    mode = args.mode or cfg.get("task", {}).get("run_mode", "once")
    run_full_ocr_after = args.run_full_ocr_after or cfg.get("task", {}).get("run_full_ocr_after", False)

    if mode == "once":
        run_once(cfg, reprocess_ocr=args.reprocess_ocr)
        if run_full_ocr_after and not args.reprocess_ocr:
            print("[once] 抓取完成，开始执行全量 OCR 重处理...")
            run_once(cfg, reprocess_ocr=True)
        return

    def _run_cycle():
        run_once(cfg, reprocess_ocr=False)
        if run_full_ocr_after:
            print("[daemon] 本轮抓取完成，开始执行全量 OCR 重处理...")
            run_once(cfg, reprocess_ocr=True)

    run_at = cfg.get("task", {}).get("run_at", "00:05")
    schedule.every().day.at(run_at).do(_run_cycle)
    print(f"[daemon] 已启动，计划每天 {run_at} 执行。先执行一次初始化抓取...")
    _run_cycle()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
