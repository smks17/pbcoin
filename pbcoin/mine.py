import logging
import pbcoin

class Mine:
    start_over = False # if true mining stop and then start over from last block
    mined_new = False

    @classmethod
    async def start(cls):
        block = pbcoin.BLOCK_CHAIN.setupNewBlock()
        cls.mined_new = False
        while(not cls.start_over):
            if int(block.calculateHash(), 16) <= pbcoin.DIFFICULTY:
                if cls.start_over:
                    break
                block.setMined()
                cls.mined_new = True
                break
            block.setNonce(block.nonce+1)
        logging.info(f"mined a block: {block.__hash__}")
        await pbcoin.NETWORK.sendMinedBlock(block)
        pbcoin.BLOCK_CHAIN.addNewBlock(block)
