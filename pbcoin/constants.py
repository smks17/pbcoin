from __future__ import annotations

import logging
import sys
import os
from pathlib import Path
from typing import (
    Final,
    List,
)
import warnings


#############General################
# For unix OS_TYPE = 'unix' and for Windows OS_TYPE = 'wim'
if (sys.platform == 'linux' or
    sys.platform == 'linux2' or
    sys.platform == 'cygwin' or
    sys.platform == 'darwin'):
    OS_TYPE: Final[str] = 'unix'
elif sys.platform == 'win32':
    OS_TYPE: Final[str] = 'win'
else:
    warnings.warn("Warnings: Your os is not supported or recognize", FutureWarning)
    OS_TYPE: Final[None] = None

# TODO: Could be replace by a absolute path
# Path of the root
BASE_PATH = Path(os.path.abspath('.'))

# Debug mode for logging more
DEBUG: bool = False

# set be miner or not
MINING: bool = True

# How much kb to use for in-memory
CACHE: float = 15

# Set to be full node or don't keep all blocks and gets
# blocks from a full node
FULL_NODE: bool = False

# Difficult level of hash block which should be less than
#                       256 bit 1   left first 23 bit set 0
#                     -----------------------------------
DIFFICULTY: int = (2 ** 256 - 1) >> (22)

# TODO: could be better it isn't constant
# the amount of miner prize for mine a block
SUBSIDY = 50


############Network###############
# networks(socket with other node + cli) api is run or not
HAS_NETWORKS = True

# Cli api is run or not which it uses for cli mode
HAS_CLI: bool = True
# Socket network api is run or not (for connect other nodes)
HAS_SOCKET_NETWORK: bool = True

# Host ip that deafault is local host for test
HOST: str = "127.0.0.1"

# Host ip that deafault is local host for test
PORT: int = 8989

# Seeds are uses for connet to blockchain network
# and its value format is <IP>:<PORT>
INIT_SEEDS: List[str] = []

# How many neighbors (nodes) connect to each node
TOTAL_NUMBER_CONNECTIONS: Final[int] = 2

# The size of the first data that get from other nodes that
# specifies the size of actual data
NETWORK_DATA_SIZE: Final[int] = 8

TIMEOUT = 1 * 60#s

PIPE_BUFFER_SIZE = 1024 * 4

# TODO: Could be replace from app args
# The name of socket(unix)/pipe(win) for using in cli
PIPE_SOCKET_NAME = 'node_socket'

PIPE_SOCKET_PATH = None
# Node socket path for cli api
# For unix it is a path to unix socket
# And for windows it is a path to pipe socket
if OS_TYPE == 'unix':
    PIPE_SOCKET_PATH: Path = BASE_PATH / (PIPE_SOCKET_NAME + '.s')
elif OS_TYPE == 'win':
    PIPE_SOCKET_PATH: str = r'\\.\pipe\\' + PIPE_SOCKET_NAME
else:
    warnings.warn("Warnings: Your os is not supported for cli mode", FutureWarning)

############Logging###############
# Print log or not
DO_LOGGING = True

# Logging format
LOGGING_FORMAT: str = "%(asctime)s |  %(name)-18s |  %(levelname)-10s: %(message)s"

LOGGING_DATE_FORMAT: str = "%Y-%m-%d %H:%M-%S"

# Change logging level if debug mode is True
LOGGING_LEVEL: int = logging.INFO

# File for write log
LOGGING_FILENAME = BASE_PATH / "pbcoin.log"

############Database###############
# Path to database
DB_PATH: str = r"./pbcoin.db"  # TODO: use absolute path

# Table name blocks in database
DB_BLOCKS_TABLE: str = "Blocks"

# Table name transactions in database
DB_TRX_TABLE: str = "Trx"

# Table name coins in database
DB_COINS_TABLE: str = "Coins"