from __future__ import annotations

import logging
from typing import (
    Any,
    Dict,
    List,
    Union
)

from .constants import (
    DEFAULT_CACHE,
    DEFAULT_HOST,
    DEFAULT_LOGGING_DATE_FORMAT,
    DEFAULT_LOGGING_FILENAME,
    DEFAULT_LOGGING_FORMAT,
    DEFAULT_LOGGING_LEVEL,
    DEFAULT_PORT,
    DEFAULT_SEEDS,
    DEFAULT_SOCKET_PATH,
    OS_TYPE,
)

__all__ = [
    "GlobalCfg",
    "NetworkCfg",
    "LoggerCfg",
]

class GlobalCfg:
    debug: bool  # Logging more in debug mode
    mining: bool  # Set mining on or off
    cache: int
    full_node: bool  # Set full node or not

    @classmethod
    def update(cls, option: Dict[str, Union[bool, int]]):
        cls.debug = option.get("debug", False)
        cls.full_node = option.get("is_full_node", False)
        cls.cache = option.get("cache", DEFAULT_CACHE)
        cls.mining = option.get("mining", True)
        NetworkCfg.update(option)
        LoggerCfg.update(option)


# Configs that are related to connection other nodes and cli
class NetworkCfg():
    ip: str
    port: int
    seeds: List[str]
    socket_path: str

    @classmethod
    def update(cls, option: Dict[str, Any]):
        cls.ip = option.get("ip", DEFAULT_HOST)
        cls.port = option.get("port", DEFAULT_PORT)
        cls.seeds = option.get("seeds", DEFAULT_SEEDS)
        if OS_TYPE == 'unix':
            cls.socket_path = option.get("socket_path", DEFAULT_SOCKET_PATH)
        elif OS_TYPE == 'win':
            cls.socket_path = option.get("socket_path", DEFAULT_SOCKET_PATH)
        else:
            cls.socket_path = None


class LoggerCfg:
    do_logging: bool
    log_format: str
    log_level: int
    log_filename: str
    log_date_format: str

    @classmethod
    def update(cls, option: dict[str, Any]):
        cls.log_format = option.get("logging_format", DEFAULT_LOGGING_FORMAT)
        if GlobalCfg.debug:
            cls.log_level = logging.DEBUG
        else:
            cls.log_level = DEFAULT_LOGGING_LEVEL
        cls.log_filename = option.get("logging_filename", DEFAULT_LOGGING_FILENAME)
        cls.log_date_format = option.get("logging_date_format", DEFAULT_LOGGING_DATE_FORMAT)
        cls.do_logging = option.get("logging", True)
