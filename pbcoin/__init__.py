from __future__ import annotations

import asyncio
import logging
import sys
import threading
from dataclasses import dataclass

import pbcoin.blockchain as blockchain
import pbcoin.wallet as wallet
import pbcoin.net as net
import pbcoin.mine as mine
import pbcoin.cli_handler as cls

# TODO: put these in config.py
OS_TYPE = None
if (sys.platform == 'Linux' or
    sys.platform == 'Linux2' or
    sys.platform == 'cygwin' or
    sys.platform == 'darwin'
):
    OS_TYPE = 'unix'
elif sys.platform == 'win32':
    OS_TYPE = 'win'
DIFFICULTY = (2 ** 512 - 1) >> (21) # difficulty level
BLOCK_CHAIN = blockchain.BlockChain()
NETWORK: net.Node = None
MINER = mine.Mine()
WALLET = wallet.Wallet()
ALL_OUTPUTS = dict() # TODO: move the better place and file
if OS_TYPE == 'unix':
    SOCKET_PATH = r'.\node_socket'
elif OS_TYPE == 'win':
    PIPE_PATH = r'\\.\pipe\node_socket'

@dataclass
class argvOption:
    ip = "127.0.0.1"
    port = 8989
    seeds = []
    debug = False
    is_full_node = False
    cache = 1500#kb
    mining = True
    socket_path = SOCKET_PATH if OS_TYPE == 'unix' else PIPE_PATH # TODO: better

LOGGING_FORMAT = "%(asctime)s %(levelname)s %(message)s"

def run(option: argvOption):
    # logging
    LOGGING_LEVEL = logging.DEBUG if option.debug else logging.INFO
    LOGGING_FILENAME = f"node-{option.ip}.log"
    logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL,
                        filename=LOGGING_FILENAME, filemode="w")

    try:
        # network
        _net_thread = threading.Thread(
            target=asyncio.run, args=[setupNet(option)])
        # mine 
        _mine_thread = threading.Thread(
            target=asyncio.run, args=[mine_starter(option)])
        # cli network
        SOCKET_PATH = option.socket_path
        cli_server = cls.CliServer(SOCKET_PATH)
        _cli_thread = threading.Thread(
            target=asyncio.run, args=[cli_server.start()])
        _net_thread.daemon = True
        _mine_thread.daemon = True
        _net_thread.start()
        _mine_thread.start()
        _cli_thread.start()
        while _net_thread.is_alive() and _mine_thread.is_alive():
            _net_thread.join(1)
            _mine_thread.join(1)
            _cli_thread.join(1)
    except KeyboardInterrupt:
        sys.exit(1)


async def mine_starter(option):
    WALLET.gen_key()
    logging.info(f"your public key is generated: {WALLET.public_key}")
    if option.mining:
        BLOCK_CHAIN.is_full_node = option.is_full_node
        BLOCK_CHAIN.cache = option.cache * 1000 # to bytes
        while True:
            await MINER.start()

async def setupNet(option):
    global NETWORK
    NETWORK = net.Node(option.ip, option.port)
    await NETWORK.start_up(option.seeds)
    await NETWORK.listen()
