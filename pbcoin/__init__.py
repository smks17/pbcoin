import asyncio
import logging
from dataclasses import dataclass
import sys
import threading

import pbcoin.blockchain as blockchain
import pbcoin.key as key
import pbcoin.net as net
import pbcoin.mine as mine

DIFFICULTY = (2 ** 512 - 1) >> (4*6) # difficulty level
BLOCK_CHAIN = blockchain.BlockChain()
NETWORK: net.Node = None
MINER = mine.Mine()
addrKey = key.Key()

@dataclass
class argvOption:
    ip = "127.0.0.1"
    port = 8989
    seeds = []
    debug = False

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
    addrKey.genPrivateKey(option.ip)
    addrKey.genPublicKey()
    logging.info(f"your compress public key is generated: {addrKey.compressedPublic}")
    while True:
        await MINER.start()

async def setupNet(option):
    global NETWORK
    NETWORK = net.Node(option.ip, option.port)
    await NETWORK.startUp(option.seeds)
    await NETWORK.listen()