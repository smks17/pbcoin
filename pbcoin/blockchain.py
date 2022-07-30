from copy import deepcopy
from functools import reduce
from enum import Flag, auto
import logging
from operator import or_ as _or_
from sys import getsizeof

from pbcoin.block import Block
import pbcoin

class BlockValidationLevel(Flag):
    Bad = 0
    DIFFICULTY = auto()
    TRX = auto()
    PREVIOUS_HASH = auto()

    @classmethod
    def ALL(cls):
        """ get variable with all flag for checking validation """
        cls_name = cls.__name__
        if not len(cls):
            raise AttributeError(f'empty {cls_name} does not have an ALL value')
        value = cls(reduce(_or_, cls))
        cls._member_map_['ALL'] = value
        return value

class BlockChain:
    blocks : list[Block]
    is_fullNode: bool
    # if is_fullNode is True then have cache for keep blocks
    cache: float
    def __init__(self, _blockchain = []):
        self.blocks = _blockchain

    def setupNewBlock(self, mempool = []):
        if len(self.blocks) == 0:
            # generic block
            preHash = ""
            height = 1
        else:
            preHash = self.last_block.__hash__
            height = self.height + 1
        block = Block(preHash, height)
        for trx in mempool:
            block.addTrx(trx)
        return block

    def addNewBlock(self, _block: Block):
        validation = self.isValidBlock(_block)
        if validation == BlockValidationLevel.ALL():
            self.blocks.append(deepcopy(_block))
            Block.updateOutputs(deepcopy(_block))
            logging.debug(f"new blockchain: {pbcoin.BLOCK_CHAIN.getHashes()}")
            pbcoin.wallet.updateBalance(deepcopy(_block.trxList))
        else:
            return validation


        if (not self.is_fullNode) and (self.__sizeof__()>= self.cache):
            self.blocks.pop(0)

    def resolve(self, new_blocks: list[Block]):
        if not BlockChain.isValidHashChain(new_blocks):
            return Exception

        # TODO: update outputs coins
        for i in range(len(self.blocks)-1, -1, -1):
            if new_blocks[0].blocHeight > self.blocks[i].blocHeight:
                if self.blocks[i].__hash__ != new_blocks[0].__hash__:
                    return Exception
                self.blocks = self.blocks[:-i+1]
                self.blocks += new_blocks
                while (not self.is_fullNode) and (self.__sizeof__()>= self.cache):
                    self.blocks.pop(0)


    def getLastBlocks(self, n = 1):
        # TODO: get from full node if not exist
        if n > len(self.blocks): return None # bad request
        return self.blocks[-n:]

    def isValidBlock(self, _block: Block):
        valid = BlockValidationLevel.Bad
        if int(_block.__hash__, 16) <= pbcoin.DIFFICULTY:
            valid = valid | BlockValidationLevel.DIFFICULTY
        if _block.checkTrx():
            valid = valid | BlockValidationLevel.TRX
        last_block = self.last_block
        if last_block:
            if _block.previousHash == last_block.__hash__:
                valid = valid | BlockValidationLevel.PREVIOUS_HASH
        else:
            if _block.previousHash == '':
                valid = valid | BlockValidationLevel.PREVIOUS_HASH

        return valid

    def search(self, key_hash):
        """ search from last block to first for find block with key_hash """
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def getData(self, first_index = 0, last_index = None):
        if last_index == None:
            last_index = len(self.blocks)
        return [block.getData() for block in self.blocks[first_index : last_index]]

    def getHashes(self, first_index = 0, last_index = None):
        if last_index == None:
            last_index = len(self.blocks)
        if len(self.blocks) == 0: return ''
        return [block.__hash__ for block in self.blocks[first_index : last_index]]

    @staticmethod
    def jsonToBlockchain(blockchainData: list[dict[str, any]]) -> 'Blockchain':
        blockchain = [Block.fromJsonDataFull(block) for block in blockchainData]
        return BlockChain(blockchain)

    @staticmethod
    def isValidHashChain(_chain: list[Block]):
        for i in range(1, len(_chain)):
            if _chain[i].__hash__ != _chain[i-1].__hash__:
                return False
        return True

    @property
    def last_block(self):
        if len(self.blocks) == 0:
            return None
        return self.blocks[-1]

    @property
    def height(self):
        if len(self.blocks) == 0:
            return 0
        return self.last_block.blocHeight

    def __sizeof__(self) -> int:
        size = 0
        for block in self.blocks:
            size += getsizeof(block)
        return size