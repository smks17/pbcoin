from __future__ import annotations

import asyncio
import sys
from threading import Thread
from typing import Dict

from .config import *
from .cli_handler import CliServer
from .net import Node
from .wallet import Wallet
from .blockchain import BlockChain
from .mine import Mine
from .logger import getLogger
import pbcoin.core as core


logging = getLogger(__name__)

def create_core():
    """Create the core objects"""
    core.MINER = Mine()
    core.WALLET = Wallet()
    core.BLOCK_CHAIN = BlockChain()

async def mine_starter():
    """Set up and start mining"""
    core.WALLET.gen_key()
    logging.info(f"your public key is generated: {core.WALLET.public_key}")
    if GlobalCfg.mining:
        core.BLOCK_CHAIN.is_full_node = GlobalCfg.full_node
        core.BLOCK_CHAIN.cache = GlobalCfg.cache * 1000  # to bytes
        while True:
            await core.MINER.start()

async def setup_network():
    """Set up network for connect other nodes and cli"""
    core.NETWORK = Node(NetworkCfg.ip, NetworkCfg.port)
    await core.NETWORK.start_up(NetworkCfg.seeds)
    cli_server = CliServer(NetworkCfg.socket_path)
    loop = asyncio.get_event_loop()
    all_net = await asyncio.gather(core.NETWORK.listen(), cli_server.start())
    loop.run_until_complete(all_net)

def run():
    """Run and start the node with option that gets"""

    # Clear logfile
    with open(LoggerCfg.log_filename, "w") as _: pass

    create_core()
    try:
        # network thread
        net_thread = Thread(target=asyncio.run, args=[setup_network()], name="network")
        # mine thread
        mine_thread = Thread(target=asyncio.run, args=[mine_starter()], name="mine")
        logging.debug(f"socket is made in {NetworkCfg.socket_path}")

        net_thread.daemon = True
        mine_thread.daemon = True

        net_thread.start()
        mine_thread.start()
        while net_thread.is_alive() and mine_thread.is_alive():
            net_thread.join(1)
            mine_thread.join(1)
    except KeyboardInterrupt:
        sys.exit(1)
