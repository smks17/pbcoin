from copy import deepcopy
from typing import Dict, List, Optional, Union

import pbcoin.config as conf
import pbcoin.core as core
from pbcoin.block import Block
from pbcoin.blockchain import BlockChain
from pbcoin.logger import getLogger
from pbcoin.mempool import Mempool
from pbcoin.network import Node
from pbcoin.trx import Coin, Trx
from pbcoin.wallet import Wallet

logging = getLogger(__name__)


class Mine:
    """
    Attributes
    ----------
        start_over: bool = False
            if true then mining stops and start over from the last block
        mined_new: bool = False
            if true means a new block was mined and it should declare to other
        stop_mining: bool = False
            stop mining until it is False
        reset_nonce: bool = False
            if true it changes the nonce value to 0 and then starts to continue mining
        blockchain: BlockChain
            a Blockchain object (often from core.py)
        wallet: Wallet
            a Wallet object for save your balance and stuff
        node: Node
            a Node object from net.py
        mempool: Mempool
            the Mempool object that is a list of transactions that should has been mined
    """
    def __init__(
        self,
        blockchain: Union[BlockChain, List],
        wallet: Optional[Wallet],
        mempool: Mempool,
        node: Optional[Node] = None,
    ):
        self.blockchain = blockchain
        self.node = node
        self.mempool = mempool
        self.wallet = wallet
        self.reset()

    def reset(self):
        """reset mine parameter for start again mining for next block"""
        self.start_over = False
        self.mined_new = False
        self.stop_mining = False
        self.reset_nonce = False

    async def mine(
        self,
        setup_block: Optional[Block] = None,
        unspent_coins: Optional[Dict[str, List[Coin]]] = None,  # almost just for unittest
        add_block = True,
        difficulty: Optional[int] = None,  # almost just for unittest
        send_network: Optional[bool] = None  # almost just for unittest
    ) -> None:
        """Start mining for new block and send to other nodes
        from network if it is setup

        Args
        ----
        setup_block: Optional[Block] = None
            the specific block to find its nonce and
            send to other nodes. If it is None then get
            from blockchain object
        unspent_coins: Optional[Dict[str, List[Coin]]] = None
            all the output coins
        add_block: bool = True
            if True then add the mined block to the blockchain
        difficulty: int
            mine for what difficulty
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        if send_network is None:
            send_network = conf.settings.glob.network
        if unspent_coins is None:
            unspent_coins = core.ALL_OUTPUTS

        if setup_block is not None:
            self.setup_block = setup_block
        elif type(self.blockchain) is BlockChain:
            subsidy = Trx(self.blockchain.height, core.WALLET.public_key)
            self.setup_block = self.blockchain.setup_new_block(
                mempool=self.mempool, subsidy=subsidy)
        else:
            raise Exception("Mine needs to setup block")
        self.reset()
        if isinstance(self.blockchain, List):
            last_n = len(self.blockchain)
        else:
            last_n = self.blockchain.height
        logging.debug("start again mine")
        transactions_mining = deepcopy(self.setup_block.transactions)
        if self.setup_block.has_subsidy:
            transactions_mining.pop(0)  # pop subsidy
        while not self.check_add_block(last_n):
            if self.start_over:
                break
            if self.reset_nonce:
                self.setup_block.set_nonce(0)
            if self.stop_mining:
                continue
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
            self.setup_block.set_nonce(self.setup_block.nonce+1)
        if self.mined_new:
            logging.info("A Block was mined")
            logging.debug(f"minded block info: {self.setup_block.get_data(True, False)}")
            if send_network and self.node is not None:
                await self.node.send_mined_block(self.setup_block)
            if add_block and type(self.blockchain) is BlockChain:
                self.blockchain.add_new_block(self.setup_block,
                                              ignore_validation=True,
                                              unspent_coins=unspent_coins,
                                              difficulty=difficulty)
                logging.debug(f"New blockchain: {self.blockchain.get_hashes()}")
            elif add_block:
                self.blockchain.append(self.setup_block)
                logging.debug("New blockchain: ",
                              [block.__hash__ for block in self.blockchain])
            self.mempool.remove_transactions(self.setup_block.hash_list_trx)

    def check_add_block(self, last_n: int):
        """check now blockchain height with last_n"""
        if isinstance(self.blockchain, List):
            height = len(self.blockchain)
        else:
            height = self.blockchain.height
        return height > last_n
