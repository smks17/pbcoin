from typing import Final
import sys
import logging

#############General################
# For unix OS_TYPE = 'unix' and for Windows OS_TYPE = 'wim'
if (sys.platform == 'linux' or
    sys.platform == 'linux2' or
    sys.platform == 'cygwin' or
    sys.platform == 'darwin'
    ):
    OS_TYPE: Final[str] = 'unix'
elif sys.platform == 'win32':
    OS_TYPE: Final[str] = 'win'
else:
    OS_TYPE: Final[None] = None

# How much nodes get themselves as mine reward
DEFAULT_SUBSIDY: Final[int] = 50
# Size of cache for keeping blockchain
DEFAULT_CACHE: Final[int] = 1500 # kb

# Difficult level
# TODO: change DIFFICULTY every n blocks was mined
#                       512 bit 1   left first 6 byte set 0
#                     -----------------------------------
DIFFICULTY: Final[int] = (2 ** 512 - 1) >> (6 * 4)


# Node socket path for cli api
# For unix it is a path to unix socket
# And for windows it is a path to pipe socket
if OS_TYPE == 'unix':
    DEFAULT_SOCKET_PATH: Final[str] = r'.\node_socket'
elif OS_TYPE == 'win':
    DEFAULT_SOCKET_PATH: Final[str] = r'\\.\pipe\node_socket'

############Network###############
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8989
# Seeds value is like <IP>:<PORT>
DEFAULT_SEEDS: Final[str] = []

# How many neighbors (nodes) connect to each node
TOTAL_NUMBER_CONNECTIONS: Final[int] = 2
# The size of the first data that get from other nodes that
# specifies the size of actual data
NETWORK_DATA_SIZE: Final[int] = 8

PIPE_BUFFER_SIZE = 1024 * 4

#############Logging################
DEFAULT_LOGGING_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(message)s"
# Change logging level if debug mode is True
DEFAULT_LOGGING_LEVEL: Final[int] = logging.INFO
# File for write log
DEFAULT_LOGGING_FILENAME = r".\pbcoin.log"

