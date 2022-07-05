from pbcoin import BLOCK_CHAIN, DIFFICULTY, NETWORK
from pbcoin.block import Block

class Mine:
    start_over = False # if true mining stop and then start over from last block
    mined_new = False

    @classmethod
    async def start(cls):
        block = BLOCK_CHAIN.setupNewBlock()
        cls.mined_new = False
        while(not cls.start_over):
            if int(block.calculateHash(), 16) <= DIFFICULTY:
                if cls.start_over:
                    break
                cls.mined_new = True
                break
            block.setNonce(block.nonce+1)
        
        await NETWORK.sendMinedBlock(block)
        BLOCK_CHAIN.addNewBlock(block)
