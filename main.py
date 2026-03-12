from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import schedule
import time
import yaml

from crawler.weibo_crawler import WeiboCrawler
from storage.storage_manager import StorageManager
from tracking.history_tracker import HistoryTracker
from utils.logger import setup_logger


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_once(cfg: dict):
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

    since_date = cfg["targets"].get("since_date")
    include_retweets = cfg["targets"].get("include_retweets", False)
    dl_images = cfg["download"].get("images", True)
    img_timeout = cfg["download"].get("image_timeout", 15)

    day_stats: Dict[str, Dict] = defaultdict(lambda: {"posts": 0, "images": 0, "uids": set()})

    for uid in cfg["targets"]["user_ids"]:
        logger.info(f"开始抓取 UID={uid}")
        for page in range(1, 11):
            try:
                data = crawler.fetch_user_page(uid, page=page)
                cards = crawler.parse_cards(data, since_date=since_date, include_retweets=include_retweets)
            except Exception as e:
                logger.error(f"拉取失败 uid={uid} page={page}: {e}")
                break

            if not cards:
                logger.info(f"uid={uid} page={page} 无可处理微博，结束该用户抓取")
                break

            new_count = 0
            for post in cards:
                if tracker.is_processed(post["id"]):
                    continue
                saved = storage.save_post(post, download_images=dl_images, image_timeout=img_timeout)
                tracker.mark_processed(post["id"], uid, int(post["created_ts"]))
                new_count += 1

                date_key = datetime.fromtimestamp(int(post["created_ts"])).strftime("%Y-%m-%d")
                day_stats[date_key]["posts"] += 1
                day_stats[date_key]["images"] += saved["images_saved"]
                day_stats[date_key]["uids"].add(uid)

            logger.info(f"uid={uid} page={page} 新增 {new_count} 条")

    # 写 summary.json
    for date_key, st in day_stats.items():
        date_dir = os.path.join(cfg["storage"]["base_dir"], date_key)
        summary = {
            "date": date_key,
            "posts": st["posts"],
            "images": st["images"],
            "uids": sorted(list(st["uids"])),
            "generated_at": datetime.now().isoformat(),
        }
        storage.write_summary(date_dir, summary)

    logger.info("本轮任务完成")


def main():
    parser = argparse.ArgumentParser(description="微博数据自动化采集与归档系统")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--mode", choices=["once", "daemon"], default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    mode = args.mode or cfg.get("task", {}).get("run_mode", "once")

    if mode == "once":
        run_once(cfg)
        return

    run_at = cfg.get("task", {}).get("run_at", "00:05")
    schedule.every().day.at(run_at).do(lambda: run_once(cfg))
    print(f"[daemon] 已启动，计划每天 {run_at} 执行")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
