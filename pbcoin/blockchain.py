from __future__ import annotations

from copy import copy, deepcopy
from sys import getsizeof
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from .block import Block, BlockValidationLevel
from .config import GlobalCfg
from .mempool import Mempool
from .trx import Coin, Trx


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

    def __init__(self, blocks = [], full_node = True):
        self.blocks = blocks
        self.is_full_node = full_node
        if not self.is_full_node:
            self.cache = GlobalCfg.cache

    def setup_new_block(self, subsidy: Trx, mempool: Mempool):
        """set up a new block in chain for mine"""
        # TODO: checking from other nodes if this node is not a full node
        previous_hash = self.last_block_hash
        height = self.height + 1
        block = Block(previous_hash, height, subsidy=subsidy)

        # add remain transactions in mempool to next block
        for trx in mempool:
            block.add_trx(trx)
        return block

    def add_new_block(
        self, block_: Block, unspent_coins: Optional[Dict[str, Coin]]=None , ignore_validation=False
    ) -> Optional[BlockValidationLevel]:
        if not ignore_validation:
            validation = block_.is_valid_block(unspent_coins, pre_hash=self.last_block_hash)
        else:
            validation = BlockValidationLevel.ALL()
        if validation == BlockValidationLevel.ALL():
            self.blocks.append(deepcopy(block_))
        if (not self.is_full_node) and (self.__sizeof__() >= self.cache):
            self.blocks.pop(0)
        return validation

    def resolve(
        self,
        new_blocks: List[Block],
        unspent_coins: Dict[str, Coin]
    ) -> Tuple[bool, Optional[int]]:
        """resolve the this blockchain with new blocks

        Args
        ----
        new_block: List[Blocks]
            list of new blocks for resolve and add to this blockchain
        unspent_coins: Dict[str, Coin]
            a data from unspent coin for update after resolve

        Return
        ------
        Tuple[bool, Optional[int]]:
            return a tuple which the first is to determine does resolving could do or not 
            and the second one is the index of block in new_blocks that has a problem, if
            it resolves with no problem, the second one is None
        """
        copy_unspent_coins = copy(unspent_coins)
        result = BlockChain.check_blockchain(new_blocks, copy_unspent_coins)
        if not result[0]:
            return result
        self_blockchain_index, new_blockchain_index = self.find_different(new_blocks)
        for i in range(self_blockchain_index):
            self.blocks[-i].revert_outputs(copy_unspent_coins)
            self.blocks.pop()
        # TODO: update outputs coins
        for trx_hash in copy_unspent_coins:
            unspent_coins[trx_hash] = copy_unspent_coins[trx_hash]
        for i in range(new_blockchain_index, 0, -1):
            new_blocks[len(new_blocks) - i].update_outputs(unspent_coins)
            self.blocks.append(new_blocks[len(new_blocks) - i])
        while (not self.is_full_node) and (self.__sizeof__() >= self.cache):
            self.blocks.pop(0)
        return (True, None)

    def find_different(self, new_blocks: List[Block]) -> Tuple[int, int]:
        """find how different two blockchain
        
        Args
        ----
        blocks: List[Block]
            list of other blocks for find different with self blocks

        Returns
        -------
        Tuple[int, int]
            first int is first index self blocks from last that begin different
            
            second int is first index new blocks from last that begin different
        """
        # TODO: work with block height
        for index1, block in enumerate(reversed(self.blocks)):
            for index2, new_block in enumerate(reversed(new_blocks)):
                if block.__hash__ == new_block.__hash__:
                    return index1, index2
        return len(self.blocks), len(new_blocks)

    def get_last_blocks(self, number=1) -> Optional[List[Block]]:
        """get last n blocks"""
        # TODO: get from full node if not exist
        if number > len(self.blocks):
            return None  # bad request
        return self.blocks[-number:]

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
    def check_blockchain(
        blocks: List[Block],
        unspent_coins: Dict[str, Coin]
    ) -> Tuple[bool, Optional[int]]:
        for index, block in enumerate(blocks):
            pre_hash = ""
            if index != 0:
                pre_hash = blocks[index - 1].__hash__
            validation = block.is_valid_block(unspent_coins, pre_hash=pre_hash)
            if validation != BlockValidationLevel.ALL():
                return False, index
        return True, None

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
    def last_block_hash(self) -> str:
        pre_hash = ""
        if self.last_block is not None:
            pre_hash = self.last_block.__hash__
        return pre_hash

    @property
    def height(self) -> int:
        last = self.last_block
        if last is None:
            return 0
        return last.block_height

    def __sizeof__(self) -> int:
        size = 0
        for block in self.blocks:
            size += getsizeof(block)
        return size
