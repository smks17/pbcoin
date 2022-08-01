import asyncio
import logging
from dataclasses import dataclass
import sys
import threading

import pbcoin.blockchain as blockchain
import pbcoin.wallet as wallet
import pbcoin.net as net
import pbcoin.mine as mine

DIFFICULTY = (2 ** 512 - 1) >> (4*6) # difficulty level
BLOCK_CHAIN = blockchain.BlockChain()
NETWORK: net.Node = None
MINER = mine.Mine()
wallet = wallet.Wallet()
ALL_OUTPUTS = dict() # TODO: move the better place and file

@dataclass
class argvOption:
    ip = "127.0.0.1"
    port = 8989
    seeds = []
    debug = False
    is_fullNode = False
    cache = 1500#kb
    mining = True

LOGGING_FORMAT = "%(asctime)s %(levelname)s %(message)s"

def setup(option: argvOption):
    # logging
    LOGGING_LEVEL = logging.DEBUG if option.debug else logging.INFO
    LOGGING_FILENAME = f"node-{option.ip}.log"
    logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL,
                        filename=LOGGING_FILENAME, filemode="w")

    try:
        _net_thread = threading.Thread(
            target=asyncio.run, args=[setupNet(option)])
        _mine_thread = threading.Thread(
            target=asyncio.run, args=[mine_starter(option)])
        _net_thread.daemon = True
        _mine_thread.daemon = True
        _net_thread.start()
        _mine_thread.start()
        while _net_thread.is_alive() and _mine_thread.is_alive():
            _net_thread.join(1)
            _mine_thread.join(1)
    except KeyboardInterrupt:
        sys.exit(1)


async def mine_starter(option):
    wallet.genKey()
    logging.info(f"your public key is generated: {wallet.walletKey.publicKey().toString()}")
    if option.mining:
        BLOCK_CHAIN.is_fullNode = option.is_fullNode
        BLOCK_CHAIN.cache = option.cache * 1000 # to bytes
        while True:
            await MINER.start()

async def setupNet(option):
    global NETWORK
    NETWORK = net.Node(option.ip, option.port)
    await NETWORK.startUp(option.seeds)
    await NETWORK.listen()