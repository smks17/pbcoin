import logging
from copy import copy

from ellipticcurve.ecdsa import Ecdsa
from ellipticcurve.publicKey import PublicKey
from ellipticcurve.signature import Signature

from .constants import DIFFICULTY
from .trx import Trx
import pbcoin.core as core


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
        mempool: list[Trx]
            the list of transactions that should has been mined
    """
    def __init__(self):
        self.reset()

    def reset(self):
        """reset mine parameter for start again mining for next block"""
        self.start_over = False
        self.mined_new = False
        self.stop_mining = False
        self.reset_nonce = False
        self.mempool = []

    async def start(self):
        self.setup_block = core.BLOCK_CHAIN.setup_new_block()
        self.reset()
        logging.debug("start again mine")
        while(not self.start_over):
            if self.start_over:
                break
            if self.reset_nonce:
                self.setup_block.set_nonce(0)
            if self.stop_mining:
                continue
            # calculate hash and check difficulty
            if int(self.setup_block.calculate_hash(), 16) <= DIFFICULTY:
                if self.start_over:
                    break
                self.setup_block.set_mined()
                self.mined_new = True
                break
            self.setup_block.set_nonce(self.setup_block.nonce+1)
        if self.mined_new:
            logging.info(
                f"mined a block: {self.setup_block.get_data(True, False)}")
            await core.NETWORK.send_mined_block(self.setup_block)
            core.BLOCK_CHAIN.add_new_block(self.setup_block)

    def add_trx_to_mempool(self, trx_: Trx, sig: Signature, pub_key_: PublicKey):
        # first check sign of senders
        if Ecdsa.verify(trx_.__hash__, sig, pub_key_):
            self.mempool.append(copy(trx_))
            self.setup_block.add_trx(copy(trx_))
            # self.reset_nonce = True
            return True
        else:
            return False
