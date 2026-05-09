"""统一内容抓取链：weixin → jina → defuddle"""

import subprocess
import urllib.request
import re
from pathlib import Path

try:
    from logger import get_logger
except ModuleNotFoundError:
    from tools.logger import get_logger

log = get_logger("fetcher")


def fetch(url: str) -> str | None:
    """抓取 URL 内容为 Markdown，按优先级尝试多种方式"""
    log.info("fetch start", extra={"url": url})

    if "mp.weixin.qq.com" in url:
        content = _try_weixin(url)
        if content:
            log.info("fetched via weixin", extra={"length": len(content)})
            return content
        log.warning("weixin failed, trying jina")

    content = _try_jina(url)
    if content:
        log.info("fetched via jina", extra={"length": len(content)})
        return content
    log.warning("jina failed, trying defuddle")

    content = _try_defuddle(url)
    if content:
        log.info("fetched via defuddle", extra={"length": len(content)})
    else:
        log.error("all fetch methods failed", extra={"url": url})
    return content


def _try_weixin(url: str) -> str | None:
    """Playwright 抓取公众号文章"""
    script = Path(__file__).parent.parent / "content-fetch" / "fetch_weixin.py"
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            ["python3", str(script), url],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout
        if output and output.startswith("---"):
            return output
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _try_jina(url: str) -> str | None:
    """Jina Reader 代理抓取"""
    try:
        req = urllib.request.Request(
            f"https://r.jina.ai/{url}",
            headers={"User-Agent": "msgflow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        if re.search(r"captcha|验证|环境异常", content, re.IGNORECASE):
            return None
        return content if content.strip() else None
    except Exception:
        return None


def _try_defuddle(url: str) -> str | None:
    """Defuddle 代理抓取"""
    try:
        req = urllib.request.Request(
            f"https://defuddle.md/{url}",
            headers={"User-Agent": "msgflow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        return content if content.strip() else None
    except Exception:
        return None
