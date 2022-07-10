import logging
import pbcoin

class Mine:
    start_over = False # if true mining stop and then start over from last block
    mined_new = False
    stop_mining = False # stop mining until is False

    @classmethod
    async def start(cls):
        block = pbcoin.BLOCK_CHAIN.setupNewBlock()
        cls.mined_new = False
        cls.start_over = False
        cls.stop_mining = False
        logging.debug("start again mine")
        while(not cls.start_over):
            if cls.stop_mining:
                continue
            if int(block.calculateHash(), 16) <= pbcoin.DIFFICULTY:
                if cls.start_over:
                    break
                block.setMined()
                cls.mined_new = True
                break
            block.setNonce(block.nonce+1)
        if cls.mined_new:
            logging.info(f"mined a block: {block.getData(False, False)}")
            await pbcoin.NETWORK.sendMinedBlock(block)
            pbcoin.BLOCK_CHAIN.addNewBlock(block)
