"""运行日志：把每次录制的关键决策写入文件，便于排查"声音丢在哪一步"。

v52：随录屏功能并入截屏助手，日志写到 snap-tool 目录下的 snap_recorder.log。
"""
from __future__ import annotations

import logging
import os

_LOG = None


def get_logger():
    global _LOG
    if _LOG is None:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snap_recorder.log")
        logger = logging.getLogger("snap_recorder")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(handler)
        logger.propagate = False
        _LOG = logger
    return _LOG


def log(message: str) -> None:
    try:
        get_logger().info(message)
    except Exception:  # noqa: BLE001 - 日志失败不影响录制
        pass
