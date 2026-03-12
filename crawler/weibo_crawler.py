from __future__ import annotations

import html
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


class WeiboCrawler:
    """微博数据采集引擎（基于 m.weibo.cn 接口）。"""

    BASE_URL = "https://m.weibo.cn/api/container/getIndex"

    def __init__(
        self,
        cookie: str,
        user_agent: str,
        delay_min: int = 3,
        delay_max: int = 8,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        self.cookie = cookie
        self.user_agent = user_agent
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Cookie": cookie,
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://m.weibo.cn/",
        }

    def _sleep(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
    def fetch_user_page(self, uid: str, page: int = 1) -> Dict[str, Any]:
        params = {
            "type": "uid",
            "value": uid,
            "containerid": f"107603{uid}",
            "page": page,
        }
        resp = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self._sleep()
        return data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
    def fetch_long_text(self, post_id: str) -> Optional[str]:
        url = "https://m.weibo.cn/statuses/show"
        resp = requests.get(url, params={"id": post_id}, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self._sleep()
        if data.get("ok") != 1:
            return None
        d = data.get("data", {})
        return d.get("longTextContent") or d.get("text")

    def parse_cards(
        self,
        api_data: Dict[str, Any],
        since_date: Optional[str] = None,
        include_retweets: bool = False,
    ) -> List[Dict[str, Any]]:
        cards = api_data.get("data", {}).get("cards", [])
        out: List[Dict[str, Any]] = []
        since_ts = 0
        if since_date:
            since_ts = int(datetime.strptime(since_date, "%Y-%m-%d").timestamp())

        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog") or {}
            if not mblog:
                continue

            if mblog.get("retweeted_status") and not include_retweets:
                continue

            post_id = str(mblog.get("id"))
            created_ts = self._parse_weibo_time(mblog.get("created_at", ""))
            if created_ts < since_ts:
                continue

            text = self._clean_html_text(mblog.get("text", ""))
            if mblog.get("isLongText"):
                long_text = self.fetch_long_text(post_id)
                if long_text:
                    text = self._clean_html_text(long_text)

            pics = self._extract_original_pics(mblog)

            out.append(
                {
                    "id": post_id,
                    "user_id": str((mblog.get("user") or {}).get("id", "")),
                    "created_ts": created_ts,
                    "created_at": mblog.get("created_at", ""),
                    "text": text,
                    "pics": pics,
                    "source": mblog.get("source", ""),
                }
            )
        return out

    @staticmethod
    def _extract_original_pics(mblog: Dict[str, Any]) -> List[str]:
        pics = []
        for p in mblog.get("pics", []) or []:
            if isinstance(p, dict):
                if p.get("large", {}).get("url"):
                    pics.append(p["large"]["url"])
                elif p.get("url"):
                    pics.append(p["url"])
        if not pics and mblog.get("pic_ids"):
            for pid in mblog.get("pic_ids", []):
                pics.append(f"https://wx1.sinaimg.cn/large/{pid}.jpg")
        return pics

    @staticmethod
    def _clean_html_text(text: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text).strip()

    @staticmethod
    def _parse_weibo_time(ts: str) -> int:
        # 标准格式: Thu Mar 12 20:08:00 +0800 2026
        try:
            return int(datetime.strptime(ts, "%a %b %d %H:%M:%S %z %Y").timestamp())
        except Exception:
            pass

        now = datetime.now()
        if "分钟前" in ts:
            n = int(ts.replace("分钟前", "").strip())
            return int((now.timestamp() - n * 60))
        if "小时前" in ts:
            n = int(ts.replace("小时前", "").strip())
            return int((now.timestamp() - n * 3600))
        if "今天" in ts:
            h, m = ts.replace("今天", "").strip().split(":")
            d = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            return int(d.timestamp())
        if "昨天" in ts:
            h, m = ts.replace("昨天", "").strip().split(":")
            d = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            return int(d.timestamp() - 86400)
        # fallback
        return int(now.timestamp())
