"""结构化 JSON 日志 — GitHub Actions 友好，与 Worker lib/log.js 格式一致"""

import logging
import json
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": round(record.created, 3),
            "level": record.levelname.lower(),
            "module": record.name.replace("aipulse.", ""),
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            entry.update(extra)
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED_RECORD_FIELDS:
                continue
            entry[key] = value
        return json.dumps(entry, ensure_ascii=False)


_initialized = False
_RESERVED_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "asctime",
    "extra",
}


def get_logger(name: str) -> logging.Logger:
    """获取带 JSON 格式化的 logger，自动加 aipulse. 前缀"""
    global _initialized
    logger = logging.getLogger(f"aipulse.{name}")
    if not _initialized:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        root = logging.getLogger("aipulse")
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        _initialized = True
    return logger
