from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import requests


def download_batch(
    urls_and_paths: List[Tuple[str, Path]],
    max_workers: int = 3,
    timeout: int = 15,
) -> dict:
    """并发下载一组图片。

    Args:
        urls_and_paths: List of (url, Path) tuples.
        max_workers: 最大并发数。
        timeout: 单个请求超时秒数。

    Returns:
        {"success": [成功数], "failed": [失败数], "details": [...]}
    """
    results = {"success": 0, "failed": 0, "details": []}

    def _download_one(url: str, path: Path) -> bool:
        try:
            r = requests.get(url, timeout=timeout, stream=True)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_download_one, url, path): (url, path) for url, path in urls_and_paths}

        for future in as_completed(futures):
            url, path = futures[future]
            ok = future.result()
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"url": url, "path": str(path), "ok": ok})

    return results
