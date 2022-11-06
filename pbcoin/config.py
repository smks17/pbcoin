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
    DIFFICULTY,
    OS_TYPE,
)

__all__ = [
    "GlobalCfg",
    "NetworkCfg",
    "LoggerCfg",
]

class GlobalCfg:
    config = False
    debug: bool = False  # Logging more in debug mode
    mining: bool = True  # Set mining on or off
    cache: int = 15
    full_node: bool = False  # Set full node or not
    difficulty: int = DIFFICULTY
    network: bool = True  # networks(socket+cli) api is run or not

    @classmethod
    def update(cls, option: Dict[str, Union[bool, int]]):
        cls.debug = option.get("debug", False)
        cls.full_node = option.get("is_full_node", False)
        cls.cache = option.get("cache", DEFAULT_CACHE)
        cls.mining = option.get("mining", True)
        cls.network = option.get("network", True)
        cls.difficulty = option.get("difficulty", DIFFICULTY)
        if cls.network:
            NetworkCfg.update(option)
        LoggerCfg.update(option)
        cls.config = True


# Configs that are related to connection other nodes and cli
class NetworkCfg():
    ip: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    seeds: List[str] = DEFAULT_SEEDS
    socket_path: str = DEFAULT_SOCKET_PATH
    cli: bool = True  # cli api is run or not
    socket_network: bool = True  # socket network api is run or not (for connect other nodes)

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
        cls.cli = option.get("cli", True)
        cls.socket_network = option.get("socket_network", True)

class LoggerCfg:
    do_logging: bool = True
    log_format: str = DEFAULT_LOGGING_FORMAT
    log_level: int = DEFAULT_LOGGING_LEVEL
    log_filename: str = DEFAULT_LOGGING_FILENAME
    log_date_format: str = DEFAULT_LOGGING_DATE_FORMAT

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
