from copy import deepcopy
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import pbcoin.config as conf
from pbcoin.blockchain import BlockChain
from pbcoin.logger import getLogger
from pbcoin.mempool import Mempool
from pbcoin.trx import ALL_COINS_TYPE, Trx

if TYPE_CHECKING:
    from pbcoin.block import Block
    from pbcoin.db import DB
    from pbcoin.network import Node
    from pbcoin.trx import Coin
    from pbcoin.wallet import Wallet

logging = getLogger(__name__)


class Mine:
    """ The class to mine blocks

    Attributes
    ----------
        start_over: bool = False
            Determines mining stops or start over again from the new last block.
        mined_new: bool = False
            Determines a new block was mined and it should be added to blockchain and
            declare to other nodes.
        stop_mining: bool = False
            Determines mining stops until it becomes False.
        reset_nonce: bool = False
            It changes the nonce value to 0 and then starts to continue mining.
        blockchain: BlockChain | List[Block]
            A Blockchain object or a List of blocks. Recommend Blockchain object because
            List of Blocks just uses in unittest.
        wallet: Wallet
            A Wallet object for save your balance and stuff.
        mempool: Mempool
            A Mempool object that is a list of transactions should has been mined
        node: Optional[Node]
            A Node object for declare other nodes
    """

    stop_mining: bool = False

    def __init__(
        self,
        blockchain: BlockChain | List["Block"],
        wallet: Optional["Wallet"],
        mempool: Mempool,
    ):
        """Initializes object attribute"""
        self.blockchain = blockchain
        self.mempool = mempool
        self.wallet = wallet
        self.reset()

    def reset(self):
        """Reset mine attributes for start again mining for next block"""
        self.start_over = False
        self.mined_new = False
        self.stop_mining = False
        self.reset_nonce = False

    async def mine(
        self,
        public_key: str,
        unspent_coins: ALL_COINS_TYPE,
        setup_block: Optional["Block"] = None,
        add_block = True,
        difficulty: Optional[int] = None,  # almost just for unittest
        node: Optional["Node"] = None,
        db: Optional["DB"] = None
    ) -> None:
        """(async) Start mining for a new block

        This method first setup a new block if has not been provided for it
        then start mining until finds a nonce that the block hash is less than difficulty.
        Even when the blockchain update gets out of the loop.

        After a block has been mined then added to the blockchain if
        the parameter add_block is True and then send to other nodes from
        the network if send_network is True.

        Args
        ----
        setup_block: Optional[Block] = None
            The specific block to find its nonce less than difficulty.
            If it's passed None, then get from `blockchain.setup_new_block()`
        unspent_coins: Optional[Dict[str, List[Coin]]] = None
            The coins that have not been spent yet. It's used to check
            the validation block (transactions) and update that when
            the block is added to the blockchain..
            If it's passed None, it gets that from `core.py` file.
        add_block: bool = True
            If True then the mined block will be added to the blockchain.
        difficulty: Optional[int] = None
            The difficulty in which the block hash should be less (equal) than.
            The difficulty should be an unsigned int and less than 2^256.
            If it's passed None, it gets that from configs.
        node: Optional[Node] = None
            If it is provided, then after mining, The mined block will be sent
            to other nodes from the networks.

        Return
        ------
        nothing
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        # setup block
        if setup_block is not None:
            self.setup_block = setup_block
        elif isinstance(self.blockchain, BlockChain):
            subsidy = Trx(self.blockchain.height, public_key)
            self.setup_block = self.blockchain.setup_new_block(
                mempool=self.mempool, subsidy=subsidy)
        else:
            raise Exception("Mine needs to setup block")
        # reset mine parameters
        self.reset()
        # get mining transaction to check later for added new transaction
        transactions_mining = deepcopy(self.setup_block.transactions)
        if self.setup_block.has_subsidy:
            transactions_mining.pop(0)  # pop subsidy
        if isinstance(self.blockchain, List):
            last_n = len(self.blockchain)
        else:
            last_n = self.blockchain.height
        logging.debug("start again mine")
        while not self.check_add_block(last_n):
            if self.start_over:
                break
            if self.reset_nonce:
                self.setup_block.set_nonce(0)
            if self.stop_mining:
                continue
            # check for new transaction has been added
            if transactions_mining != self.mempool == 0:
                for trx in self.mempool:
                    if trx not in transactions_mining:
                        self.setup_block.add_trx(trx)
                transactions_mining = self.setup_block.transactions
                transactions_mining.pop(0)  # pop subsidy
            self.setup_block.set_mined()
            # calculate hash and check difficulty
            if int(self.setup_block.calculate_hash(), 16) <= difficulty:
                if self.start_over:
                    break
                self.mined_new = True
                break
            # set new nonce
            self.setup_block.set_nonce(self.setup_block.nonce+1)
        if self.mined_new:
            logging.info("A Block was mined")
            logging.debug(f"minded block info: {self.setup_block.get_data(True, False)}")
            if add_block and isinstance(self.blockchain, BlockChain):
                # add new blocks to other
                self.blockchain.add_new_block(self.setup_block,
                                              ignore_validation=True,
                                              unspent_coins=unspent_coins,
                                              difficulty=difficulty,
                                              db=db)
                logging.debug(f"New blockchain: {self.blockchain.get_hashes()}")
            # if blockchian in just a List type
            elif add_block and isinstance(self.blockchain, list):
                self.blockchain.append(self.setup_block)
                logging.debug("New blockchain: ",
                              [block.__hash__ for block in self.blockchain])
                logging.debug(f"New blockchain: {[b.__hash__ for b in self.blockchain]}")
            if node is not None:
                # send mine block to other node
                # TODO: Check result
                await node.send_mined_block(self.setup_block)
            # remove mined transactions
            self.mempool.remove_transactions(self.setup_block.hash_list_trx)
            # TODO: returns the result of mining

    def check_add_block(self, last_n: int):
        """check the blockchain height with last_n
        to figure out blockchain is update or not
        """
        if isinstance(self.blockchain, List):
            height = len(self.blockchain)
        else:
            height = self.blockchain.height
        return height > last_n

    @classmethod
    def interrupt_mining(cls):
        @wraps
        async def decorator(func: Callable, *args: Any, **kwargs: Any):
            cls.stop_mining = True
            try:
                await func(*args, **kwargs)
            finally:
                cls.stop_mining = False
        return decorator
