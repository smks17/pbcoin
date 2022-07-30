from copy import copy
import logging

from ellipticcurve.ecdsa import Ecdsa

import pbcoin


class Mine:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_over = False # if true mining stop and then start over from last block
        self.mined_new = False # if true means find a new block is mined and declare to other
        self.stop_mining = False # stop mining until is False
        self.reset_nonce = False # if true reset nonce to 0 and continue mining
        self.mempool = []

    async def start(self):
        self.setupBlock = pbcoin.BLOCK_CHAIN.setupNewBlock()
        self.reset()
        logging.debug("start again mine")
        while(not self.start_over):
            if self.reset_nonce:
                self.setupBlock.setNonce(0)
            if self.start_over:
                break
            if self.stop_mining:
                continue
            if int(self.setupBlock.calculateHash(), 16) <= pbcoin.DIFFICULTY:
                if self.start_over:
                    break
                self.setupBlock.setMined()
                self.mined_new = True
                break
            self.setupBlock.setNonce(self.setupBlock.nonce+1)
        if self.mined_new:
            logging.info(f"mined a block: {self.setupBlock.getData(True, False)}")
            await pbcoin.NETWORK.sendMinedBlock(self.setupBlock)
            pbcoin.BLOCK_CHAIN.addNewBlock(self.setupBlock)

    def addTrxToMempool(self, _trx, sig, pubKey):
        if Ecdsa.verify(_trx.__hash__, sig, pubKey):
            self.mempool.append(copy(_trx))
            self.setupBlock.addTrx(copy(_trx))
            # self.reset_nonce = True
            return True
        else:
            return False