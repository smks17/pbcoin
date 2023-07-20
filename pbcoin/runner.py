from __future__ import annotations

import asyncio
from copy import deepcopy
import sys
from math import inf
from threading import Thread
from typing import NewType, Union

import pbcoin.config as conf
from pbcoin.block import Block
from pbcoin.mempool import Mempool
from pbcoin.cli_handler import CliServer
from pbcoin.utils.netbase import Addr
from pbcoin.network import Node
from pbcoin.process_handler import ProcessingHandler
from pbcoin.wallet import Wallet
from pbcoin.blockchain import BlockChain
from pbcoin.mine import Mine
from pbcoin.logger import getLogger
import pbcoin.core as core


logging = getLogger(__name__)


def create_core():
    """Create the core objects"""
    core.WALLET = Wallet()
    core.BLOCK_CHAIN = BlockChain([])
    core.MEMPOOL = Mempool()
    core.MINER = Mine(core.BLOCK_CHAIN, core.WALLET, core.MEMPOOL, core.NETWORK)


inf_type = NewType("inf_type", float)


async def mine_starter(how_many: Union[inf_type, int]=inf):
    """Set up and start mining

        how_many: it determines how many blocks should be mined.If it doesn't pass
        then it is valued with infinity which means mining forever.
    """
    if conf.settings.glob.mining:
        core.BLOCK_CHAIN.is_full_node = conf.settings.glob.full_node
        core.BLOCK_CHAIN.cache = conf.settings.glob.cache * 1000  # to bytes
        if how_many == inf:
            while True:
                await core.MINER.mine()
                Block.update_outputs(deepcopy(core.MINER.setup_block), core.ALL_OUTPUTS)
        else:
            for _ in range(how_many):
                await core.MINER.mine()
                core.MINER.setup_block.update_outputs(core.ALL_OUTPUTS)


async def setup_network(has_cli, has_socket_network):
    """Set up network for connect other nodes and cli"""
    logging.info(f"your public key is generated: {core.WALLET.public_key}")
    handlers = []
    if has_socket_network:
        addr = Addr(conf.settings.network.ip,
                    conf.settings.network.port,
                    pub_key=core.WALLET.public_key)  # TODO: make a valid public key
        proc_handler = ProcessingHandler(core.BLOCK_CHAIN,
                                         core.ALL_OUTPUTS,
                                         core.WALLET,
                                         core.MEMPOOL)
        core.NETWORK = Node(addr, proc_handler, None)
        await core.NETWORK.start_up(conf.settings.network.seeds)
        core.MINER.node = core.NETWORK
        handlers.append(core.NETWORK.listen())
    if has_cli:
        cli_server = CliServer(conf.settings.network.socket_path)
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
                if this is True then exit and raise threads runtime error
                for example KeyboardInterrupt
            how_many_mine:  Union[inf_type, int] = inf
                it determines how many blocks should be mined.If it doesn't pass
                then it is valued with infinity which means mining forever.
    """
    if conf.settings.logger.do_logging:
        # Clear logfile
        with open(conf.settings.logger.log_filename, "w") as _:
            pass
    if reset:
        create_core()
    getLogger("asyncio", False)  # for asyncio logging
    try:
        net_thread = None
        mine_thread = None
        # network thread
        if conf.settings.glob.network:
            net_thread = Thread(target=asyncio.run,
                                args=(setup_network(conf.settings.network.cli,
                                                    conf.settings.network.socket_network),),
                                kwargs={"debug": conf.settings.glob.debug},
                                name="network",
                                daemon=True)
            net_thread.start()
            logging.debug(f"socket is made in {conf.settings.network.socket_path}")
        # mine thread
        if conf.settings.glob.mining:
            mine_thread = Thread(target=asyncio.run,
                                 args=(mine_starter(how_many_mine),),
                                 kwargs={"debug": conf.settings.glob.debug},
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

    except Exception:
        logging.critical("app was suddenly stopped", exc_info=sys.exc_info())
