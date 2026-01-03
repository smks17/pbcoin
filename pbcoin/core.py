from __future__ import annotations

import asyncio
from copy import deepcopy
import sys
from threading import Thread
from typing import  ClassVar, Optional

import pbcoin.config as conf
from pbcoin.block import Block
from pbcoin.db import DB
from pbcoin.mempool import Mempool
from pbcoin.cli_handler import CliServer
from pbcoin.trx import ALL_COINS_TYPE
from pbcoin.utils.netbase import Addr
from pbcoin.network import Node
from pbcoin.process_handler import ProcessingHandler
from pbcoin.wallet import Wallet
from pbcoin.blockchain import BlockChain
from pbcoin.mine import Mine
from pbcoin.logger import getLogger


logging = getLogger(__name__)


class Pbcoin:
    _instance: ClassVar["Pbcoin | None"] = None

    def __init__(
        self,
        blockchain: BlockChain,
        miner: Optional[Mine] = None,
        wallet: Optional[Wallet] = None,
        network: Optional[Node] = None,
        mempool: Optional[Mempool] = None,
        database: Optional[DB] = None,
        all_outputs: Optional[ALL_COINS_TYPE] = None
    ) -> None:
        self.blockchain = blockchain
        self.miner = miner
        self.wallet = wallet
        self.all_outputs = all_outputs if all_outputs is not None else ALL_COINS_TYPE(dict())
        self.network = network
        self.mempool = mempool
        self.database = database

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Pbcoin, cls).__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls) -> "Pbcoin":
        """Create the core objects"""
        all_outputs: ALL_COINS_TYPE = ALL_COINS_TYPE(dict())
        wallet = Wallet(unspent_coins=all_outputs)
        blockchain = BlockChain([])
        mempool = Mempool()
        miner = Mine(blockchain, wallet, mempool)
        # database = DB()
        # database.init()
        database = None  # TODO: Db has bug, It is better to use ORM
        addr = Addr(conf.settings.network.ip,
                conf.settings.network.port,
                pub_key=wallet.public_key)  # TODO: make a valid public key
        obj = Pbcoin(
            blockchain=blockchain,
            wallet=wallet,
            miner=miner,
            database=database,
            mempool=mempool,
            all_outputs=all_outputs
        )
        proc_handler = ProcessingHandler(obj)
        obj.network = Node(addr, proc_handler, None)
        return obj

    @classmethod
    def get_instance(cls) -> "Pbcoin":
        assert cls._instance, "Pbcoin is not initialized yet"
        return cls._instance


    async def mine_starter(self, how_many: Optional[int]=None):
        """Set up and start mining

            how_many: it determines how many blocks should be mined.If it doesn't pass
            then it is valued with infinity which means mining forever.
        """
        if conf.settings.glob.mining:
            assert self.miner
            self.blockchain.is_full_node = conf.settings.glob.full_node
            self.blockchain.cache = conf.settings.glob.cache * 1000  # to bytes
            assert self.all_outputs is not None
            assert self.wallet
            if how_many is None:
                while True:
                    try:
                        await self.miner.mine(
                            public_key=self.wallet.public_key,
                            unspent_coins=self.all_outputs,
                            node=self.network
                        )
                        # Block.update_outputs(deepcopy(self.miner.setup_block), self.all_outputs)
                    except Exception as e:
                        logging.critical("Error in mining", exc_info=e)
            else:
                for _ in range(how_many):
                    await self.miner.mine(public_key=self.wallet.public_key, unspent_coins=self.all_outputs, node=self.network)
                    # self.miner.setup_block.update_outputs(self.all_outputs)


    async def setup_network(self, has_cli, has_socket_network):
        """Set up network for connect other nodes and cli"""
        if self.wallet:
            logging.info(f"your public key is generated: {self.wallet.public_key}")
        handlers = []
        if has_socket_network and self.network:
            await self.network.start_up(conf.settings.network.seeds, all_output=self.all_outputs)
            handlers.append(self.network.listen())
        if has_cli:
            cli_server = CliServer(conf.settings.network.socket_path, self)
            handlers.append(cli_server.start())
        await asyncio.gather(*handlers)


    def run(self, raise_runtime_error=True, how_many_mine: Optional[int] = None, reset=True) -> None:
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
        getLogger("asyncio", False)  # for asyncio logging
        try:
            threads = []
            # network thread
            if conf.settings.glob.network:
                net_thread = Thread(
                    target=asyncio.run,
                    args=[
                        self.setup_network(
                            conf.settings.network.cli,
                            conf.settings.network.socket_network
                        )
                    ],
                    kwargs={"debug": conf.settings.glob.debug},
                    name="network",
                )
                net_thread.start()
                threads.append(net_thread)
                logging.debug(f"socket is made in {conf.settings.network.socket_path}")
            # mine thread
            if conf.settings.glob.mining:
                mine_thread = Thread(
                    target=asyncio.run,
                    args=[self.mine_starter(how_many_mine)],
                    kwargs={"debug": conf.settings.glob.debug},
                    name="mining"
                )
                mine_thread.start()
                threads.append(mine_thread)

            for t in threads:
                t.join()

        except KeyboardInterrupt:
            sys.exit(1)

        except Exception:
            logging.critical("app was suddenly stopped", exc_info=sys.exc_info())
