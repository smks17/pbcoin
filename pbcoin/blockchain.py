from __future__ import annotations

import logging
from copy import deepcopy
from functools import reduce
from enum import Flag, auto
from operator import or_ as _or_
from sys import getsizeof
from typing import (
    Any,
    Dict,
    List,
    Optional
)

from .block import Block
from .constants import DIFFICULTY
from .trx import Trx
import pbcoin.core as core


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
            raise AttributeError(
                f'empty {cls_name} does not have an ALL value')
        value = cls(reduce(_or_, cls))
        cls._member_map_['ALL'] = value
        return value


class BlockChain:
    """
    An in-memory blocks data
    
    Attributes
    ----------
    blocks: List[Block]
        List of chain blocks are kept in memory
    is_full_node: bool
    cache: float
        how much keep blocks data in memory for non full nodes.
        (it is in kb)
    """

    def __init__(self, blockchain_=[]):
        self.blocks = blockchain_

    def setup_new_block(self, mempool: List[Trx] = []):
        """set up a new block in chain for mine"""
        if len(self.blocks) == 0:
            # TODO: check from other nodes because blockchain class delete blocks from large chain
            # generic block
            previous_hash = ""
            height = 1
        else:
            previous_hash = self.last_block.__hash__
            height = self.height + 1

        block = Block(previous_hash, height)

        # add remain transactions in mempool to next block
        for trx in mempool:
            block.add_trx(trx)
        return block

    def add_new_block(self, block_: Block) -> Optional[BlockValidationLevel]:
        validation = self.is_valid_block(block_)
        if validation == BlockValidationLevel.ALL():
            self.blocks.append(deepcopy(block_))
            Block.update_outputs(deepcopy(block_))
            logging.debug(f"new blockchain: {core.BLOCK_CHAIN.get_hashes()}")
            core.WALLET.updateBalance(deepcopy(block_.transactions))
        else:
            return validation

        if (not self.is_full_node) and (self.__sizeof__() >= self.cache):
            self.blocks.pop(0)

    def resolve(self, new_blocks: List[Block]) -> None:
        if not BlockChain.isValidHashChain(new_blocks):
            return Exception

        # TODO: update outputs coins
        for i in range(len(self.blocks)-1, -1, -1):
            if new_blocks[0].block_height > self.blocks[i].block_height:
                if self.blocks[i].__hash__ != new_blocks[0].__hash__:
                    return Exception
                self.blocks = self.blocks[:-i+1]
                self.blocks += new_blocks
                while (not self.is_full_node) and (self.__sizeof__() >= self.cache):
                    self.blocks.pop(0)

    def get_last_blocks(self, number=1) -> Optional[List[Block]]:
        """get last n blocks"""
        # TODO: get from full node if not exist
        if number > len(self.blocks):
            return None  # bad request
        return self.blocks[-number:]

    def is_valid_block(self, _block: Block) -> BlockValidationLevel:
        """checking validation and return validation level"""
        valid = BlockValidationLevel.Bad

        # difficulty level
        if int(_block.__hash__, 16) <= DIFFICULTY:
            valid = valid | BlockValidationLevel.DIFFICULTY

        # check all trx
        if _block.check_trx():
            valid = valid | BlockValidationLevel.TRX

        # check previous hash
        last_block = self.last_block
        if last_block:
            if _block.previous_hash == last_block.__hash__:
                valid = valid | BlockValidationLevel.PREVIOUS_HASH
        else:
            if _block.previous_hash == '':
                valid = valid | BlockValidationLevel.PREVIOUS_HASH

        return valid

    def search(self, key_hash) -> Optional[int]:
        """search from last block to first for find block with key_hash"""
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def get_data(self, first_index=0, last_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """get block data from first_index to last_index.
        (last_index = None means to end of blockchain)"""
        # TODO: if not exist get from full node
        if last_index == None:
            last_index = len(self.blocks)
        return [block.get_data() for block in self.blocks[first_index: last_index]]

    def get_hashes(self, first_index=0, last_index: Optional[int] = None) -> List[str]:
        """ get list of blocks hash in blockchain """
        # TODO: if not exist get from full node
        if last_index == None:
            last_index = len(self.blocks)
        if len(self.blocks) == 0:
            return []
        return [block.__hash__ for block in self.blocks[first_index: last_index]]

    @staticmethod
    def json_to_blockchain(blockchain_data: List[Dict[str, Any]]) -> BlockChain:
        blockchain = [Block.from_json_data_full(
            block) for block in blockchain_data]
        return BlockChain(blockchain)

    @property
    def last_block(self) -> Optional[Block]:
        if len(self.blocks) == 0:
            return None
        return self.blocks[-1]

    @property
    def height(self) -> int:
        if len(self.blocks) == 0:
            return 0
        return self.last_block.block_height

    def __sizeof__(self) -> int:
        size = 0
        for block in self.blocks:
            size += getsizeof(block)
        return size
