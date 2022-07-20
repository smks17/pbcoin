import logging
import pbcoin

class Mine:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_over = False # if true mining stop and then start over from last block
        self.mined_new = False # if true means find a new block is mined and declare to other
        self.stop_mining = False # stop mining until is False
        self.reset_nonce = False # if true reset nonce to 0 and continue mining

    async def start(self):
        block = pbcoin.BLOCK_CHAIN.setupNewBlock()
        self.reset()
        logging.debug("start again mine")
        while(not self.start_over):
            if self.stop_mining:
                continue
            if self.reset_nonce:
                block.setNonce(0)
            if int(block.calculateHash(), 16) <= pbcoin.DIFFICULTY:
                if self.start_over:
                    break
                block.setMined()
                self.mined_new = True
                break
            block.setNonce(block.nonce+1)
        if self.mined_new:
            logging.info(f"mined a block: {block.getData(True, False)}")
            await pbcoin.NETWORK.sendMinedBlock(block)
            pbcoin.BLOCK_CHAIN.addNewBlock(block)
