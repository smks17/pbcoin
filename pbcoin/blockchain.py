from functools import reduce
from enum import Flag, auto
from operator import or_ as _or_

from pbcoin.block import Block

class BlockValidationLevel(Flag):
    Bad = 0
    DIFFICULTY = auto()
    TRX = auto()
    PREVIOUS_HASH = auto()

    @classmethod
    def ALL(cls):
        cls_name = cls.__name__
        if not len(cls):
            raise AttributeError('empty %s does not have an ALL value' % cls_name)
        value = cls(reduce(_or_, cls))
        cls._member_map_['ALL'] = value
        return value

class BlockChain:
    blocks : list[Block]
    def __init__(self):
        self.blocks = []

    def setupNewBlock(self):
        if len(self.blocks) == 0:
            # generic block
            preHash = ""
        else:
            preHash = self.last_block.__hash__
        block = Block(preHash, self.height + 1)
        return block

    def addNewBlock(self, _block: Block):
        validation = self.isValidBlock(_block)
        if validation == BlockValidationLevel.ALL():
            self.blocks.append(_block)
        else:
            return validation

    def resolve(self, new_blocks: list[Block]):
        if not BlockChain.validHashChain(new_blocks):
            return Exception
        
        for i in range(len(self.blocks)-1, -1, -1):
            if new_blocks[0].blocHeight > self.blocks[i].blocHeight:
                if self.blocks[i].__hash__ != new_blocks[0].__hash__:
                    return Exception
                del self.blocks[-i+1:]
                self.blocks += new_blocks

    def getLastBlocks(self, n = 1):
        if n > len(self.blocks): return None # bad request
        return self.blocks[-n:]

    def isValidBlock(self, _block: Block):
        valid = BlockValidationLevel.Bad
        from pbcoin import DIFFICULTY
        if int(_block.__hash__, 16) <= DIFFICULTY:
            valid |= BlockValidationLevel.DIFFICULTY
        valid |= BlockValidationLevel.TRX # TODO: check all trx
        if _block.previousHash == self.last_block.previousHash:
            valid |= BlockValidationLevel.PREVIOUS_HASH
        return valid

    def findHash(self, key_hash):
        """ search from last block to first for find block with key_hash """
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def getData(self, first_index, last_index = None):
        if last_index == None:
            last_index = len(self.blocks)
        return [block.getData() for block in self.blocks[first_index, last_index]]

    @staticmethod
    def validHashChain(_chain: list[Block]):
        for i in range(1, len(_chain)):
            if _chain[i].__hash__ != _chain[i-1].__hash__:
                return False
        return True

    @property
    def last_block(self):
        return self.blocks[-1]

    @property
    def height(self):
        if len(self.blocks) == 0:
            return 0
        return self.last_block.blockHeight