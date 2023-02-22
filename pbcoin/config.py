from __future__ import annotations

import asyncio
import logging
from typing import (
    Any,
    Dict,
    List,
    Union
)

from .constants import *


class GlobalCfg:
    config = False
    debug: bool = True  # Logging more in debug mode and raise some exception
    mining: bool = True  # Set mining on or off
    cache: int = 15
    full_node: bool = False  # Set full node or not
    difficulty: int = DIFFICULTY
    network: bool = True  # networks(socket+cli) api is run or not

    @classmethod
    def update(cls, option: Dict[str, Union[bool, int]]):
        cls.debug = option.get("debug", False)
        cls.full_node = option.get("is_full_node", False)
        cls.cache = option.get("cache", CACHE)
        cls.mining = option.get("mining", True)
        cls.network = option.get("network", True)
        cls.difficulty = option.get("difficulty", DIFFICULTY)
        if cls.network:
            NetworkCfg.update(option)
        LoggerCfg.update(option)
        cls.config = True


# Configs that are related to connection other nodes and cli
class NetworkCfg():
    ip: str = HOST
    port: int = PORT
    seeds: List[str] = INIT_SEEDS
    socket_path: str = PIPE_SOCKET_PATH
    cli: bool = True  # cli api is run or not
    socket_network: bool = True  # socket network api is run or not (for connect other nodes)

    @classmethod
    def update(cls, option: Dict[str, Any]):
        cls.ip = option.get("ip", HOST)
        cls.port = option.get("port", PORT)
        cls.seeds = option.get("seeds", INIT_SEEDS)
        if OS_TYPE == 'unix':
            cls.socket_path = option.get("socket_path", PIPE_SOCKET_PATH)
        elif OS_TYPE == 'win':
            cls.socket_path = option.get("socket_path", PIPE_SOCKET_PATH)
        else:
            cls.socket_path = None
        cls.cli = option.get("cli", True)
        cls.socket_network = option.get("socket_network", True)

class LoggerCfg:
    do_logging: bool = True
    log_format: str = LOGGING_FORMAT
    log_level: int = LOGGING_LEVEL
    log_filename: str = LOGGING_FILENAME
    log_date_format: str = LOGGING_DATE_FORMAT

    @classmethod
    def update(cls, option: dict[str, Any]):
        cls.log_format = option.get("logging_format", LOGGING_FORMAT)
        if GlobalCfg.debug:
            cls.log_level = logging.DEBUG
        else:
            cls.log_level = LOGGING_LEVEL
        cls.log_filename = option.get("logging_filename", LOGGING_FILENAME)
        cls.log_date_format = option.get("logging_date_format", LOGGING_DATE_FORMAT)
        cls.do_logging = option.get("logging", True)


class Settings:
    def __init__(self):
        self.glob = GlobalCfg()
        self.network =  NetworkCfg()
        self.logger = LoggerCfg()
        if OS_TYPE == 'win':
            # do not error when close task in windows
            # TODO: maybe change close functions
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    def update(self, option: Dict[str, Any]):
        self.glob.update(option)

settings = Settings()
