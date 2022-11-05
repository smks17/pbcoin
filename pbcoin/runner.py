from __future__ import annotations

import asyncio
from copy import deepcopy
import sys
from math import inf
from threading import Thread
from typing import NewType, Union

from .block import Block
from .mempool import Mempool
from .config import GlobalCfg, NetworkCfg, LoggerCfg
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
    core.WALLET = Wallet()
    core.BLOCK_CHAIN = BlockChain([])
    core.MEMPOOL = Mempool()
    core.MINER = Mine(core.BLOCK_CHAIN, core.WALLET , core.MEMPOOL, core.NETWORK)

inf_type = NewType("inf_type", float)

async def mine_starter(how_many: Union[inf_type, int]=inf):
    """Set up and start mining

        how_many: it determines how many blocks should be mined.If it doesn't pass
        then it is valued with infinity which means mining forever.
    """
    core.WALLET.gen_key()
    logging.info(f"your public key is generated: {core.WALLET.public_key}")
    if GlobalCfg.mining:
        core.BLOCK_CHAIN.is_full_node = GlobalCfg.full_node
        core.BLOCK_CHAIN.cache = GlobalCfg.cache * 1000  # to bytes
        if how_many == inf:
            while True:
                await core.MINER.mine()
                Block.update_outputs(deepcopy(core.MINER.setup_block), core.ALL_OUTPUTS)
                core.WALLET.updateBalance(deepcopy(core.MINER.setup_block.transactions))
        else:
            for _ in range(how_many):
                await core.MINER.mine()
                core.MINER.setup_block.update_outputs(core.ALL_OUTPUTS)
                core.WALLET.updateBalance(deepcopy(core.MINER.setup_block.transactions))

async def setup_network(has_cli, has_socket_network):
    """Set up network for connect other nodes and cli"""
    handlers = []
    if has_socket_network:
        core.NETWORK = Node(core.BLOCK_CHAIN, core.WALLET, core.MEMPOOL, core.ALL_OUTPUTS, NetworkCfg.ip, NetworkCfg.port)
        await core.NETWORK.start_up(NetworkCfg.seeds)
        core.MINER.node = core.NETWORK
        handlers.append(core.NETWORK.listen())
    if has_cli:
        cli_server = CliServer(NetworkCfg.socket_path)
        handlers.append(cli_server.start())
    loop = asyncio.get_event_loop()
    all_net = await asyncio.gather(*handlers)
    loop.run_until_complete(all_net)


def run(raise_runtime_error=True, how_many_mine: Union[inf_type, int]=inf, reset=True) -> None:
    """Run and start the node with option that gets

        Note: this function doesn't configure app

        Parameters
        ----------
            raise_runtime_error: bool = True
                if this is True then exit and raise threads runtime error for example KeyboardInterrupt
            how_many_mine:  Union[inf_type, int] = inf
                it determines how many blocks should be mined.If it doesn't pass
                then it is valued with infinity which means mining forever.
    """
    if LoggerCfg.do_logging:
        # Clear logfile
        with open(LoggerCfg.log_filename, "w") as _:
            pass
    if reset:
        create_core()
    getLogger("asyncio", False) # for asyncio logging
    try:
        net_thread = None
        mine_thread = None
        # network thread
        if GlobalCfg.network:
            net_thread = Thread(target=asyncio.run,
                args=(setup_network(NetworkCfg.cli, NetworkCfg.socket_network),),
                kwargs={"debug": GlobalCfg.debug}, name="network", daemon=True)
            net_thread.start()
            logging.debug(f"socket is made in {NetworkCfg.socket_path}")
        # mine thread
        if GlobalCfg.mining:
            mine_thread = Thread(target=asyncio.run,
                                args=(mine_starter(how_many_mine),),
                                kwargs={"debug": GlobalCfg.debug},
                                name="mining", daemon=True)
            mine_thread.start()

        if raise_runtime_error:
            while True:
                if net_thread is not None and net_thread.is_alive():
                    net_thread.join(0.01)
                if mine_thread is not None and mine_thread.is_alive():
                    mine_thread.join(0.01)
        else:
            if net_thread is not None:
                net_thread.join()
            if mine_thread is not None:
                mine_thread.join()

    except KeyboardInterrupt:
        sys.exit(1)

    except Exception as exception:
        logging.critical("app was suddenly stopped", exc_info=sys.exc_info())
