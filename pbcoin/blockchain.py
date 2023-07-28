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

import pbcoin.config as conf
import pbcoin.core as core
from pbcoin.block import Block, BlockValidationLevel
from pbcoin.db import DB
from pbcoin.mempool import Mempool
from pbcoin.trx import Coin, Trx


class BlockChain:
    """An in-memory blocks data"""
    def __init__(self, blocks = [], full_node = True):
        """
        Parameters
        ----------
        blocks: List[Block] = []
            The list of block if exist
        full_node: bool = True
            If this is True keep all the blocks in memory or database.
            Otherwise delete further blocks.
        """
        self.blocks = blocks
        self.is_full_node = full_node
        if not self.is_full_node:
            # how much keep blocks data in memory for non full nodes. its value is in kb.
            self.cache = conf.settings.glob.cache

    def setup_new_block(self, subsidy: Trx, mempool: Mempool):
        """Setup a new block in chain for mine.
        Adds subsidy and transactions from mempool to the block.
        """
        # TODO: checking from other nodes if this node is not a full node
        previous_hash = self.last_block_hash
        height = self.height + 1
        block = Block(previous_hash, height, subsidy=subsidy)
        # add remain transactions in mempool to next block
        for trx in mempool:
            block.add_trx(trx)
        return block

    def add_new_block(
        self,
        block: Block,
        unspent_coins: Optional[Dict[str, Coin]]=None,
        ignore_validation=False,
        fetch_db: Optional[bool] = None,
        difficulty: Optional[int] = None,  # almost just for unittest
        db: Optional[DB] = None
    ) -> BlockValidationLevel:
        """ Add a block to the blockchain.

        Parameters
        ----------
        block: Block
            The block that you want to be added.
        unspent_coins: Optional[Dict[str, Coin]] = None
            The coins that have not been spent yet. It's used to check the validation
            block (transactions) and update that. If it's passed None, it gets that from
            `core.py` file.
        ignore_validation: bool = False
            If True then will not check the validation of the block.
            Even though, the validation block is bad.
        fetch_db: Optional[bool] = None
            If True, then the database will be updated.
        difficulty: Optional[int] = None
            The block difficulty that should be.
            If it's passed None, it gets that from configs.
        db: Optional[DB] = None
            The database object is to update that and add the new block into it.
            If it's passed None, it gets that from `core.py` file.
            And if fetch_db is passed False, it would not matters db.

        Return
        ------
        BlockValidationLevel
            It returns the validation which blocks the pass. If it equals
            the all block validation, it means the block successfully has been added.
            Otherwise, it has not been added
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        if fetch_db is None:
            fetch_db = conf.settings.database.fetch
        if not ignore_validation:
            validation = block.is_valid_block(
                unspent_coins, pre_hash=self.last_block_hash, difficulty=difficulty)
        else:
            validation = BlockValidationLevel.ALL()
        if validation == BlockValidationLevel.ALL():
            self.blocks.append(deepcopy(block))
            if unspent_coins is not None:
                self.last_block.update_outputs(unspent_coins)
            if fetch_db:
                self.fetch_db(db)
        # check that blockchain in memory is less than cache size
        if (not self.is_full_node) and (self.__sizeof__() >= self.cache):
            self.blocks.pop(0)
        return validation

    def resolve(
        self,
        new_blocks: List[Block],
        unspent_coins: Dict[str, Coin],
        difficulty: Optional[int] = None  # almost for unittest
    ) -> Tuple[bool, Optional[int], BlockValidationLevel]:
        """Resolves this blockchain with the new blocks.

        Parameters
        ----------
        new_blocks: List[Blocks]
            List of the new blocks to resolve and for adding to this blockchain
        unspent_coins: Dict[str, Coin]
            The coins that have not been spent yet for update after resolve.
        difficulty: Optional[int] = None
            The block difficulty that should be for checking block validation.
            If it's passed None, it gets that from configs.

        Returns
        -------
        Tuple[bool, Optional[int], BlockValidationlevel]:
            it Returns a tuple which determines resolving is successfully or not.
            Looking to docs of method ```Blockchain.check_blockchain``` for return items.
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        copy_unspent_coins = copy(unspent_coins)
        result = BlockChain.check_blockchain(
            new_blocks, copy_unspent_coins, difficulty)
        # if there is no bad  block validation
        if not result[0]:
            return result
        self_blockchain_index, new_blockchain_index = self.find_different(new_blocks)
        for i in range(self_blockchain_index):
            self.blocks[-i].revert_outputs(copy_unspent_coins)
            self.blocks.pop()
        for trx_hash in copy_unspent_coins:
            unspent_coins[trx_hash] = copy_unspent_coins[trx_hash]
        for i in range(new_blockchain_index, 0, -1):
            new_blocks[len(new_blocks) - i].update_outputs(unspent_coins)
            self.blocks.append(new_blocks[len(new_blocks) - i])
        # TODO: add fetch db here too
        # check that blockchain in memory is less than cache size
        while (not self.is_full_node) and (self.__sizeof__() >= self.cache):
            self.blocks.pop(0)
        return (True, None, BlockValidationLevel.ALL())

    def find_different(self, new_blocks: List[Block]) -> Tuple[int, int]:
        """Find where is the difference placed between two blockchains.

        Parameters
        ----------
        blocks: List[Block]
            List of blocks that has the difference with self blocks.

        Returns
        -------
        Tuple[int, int]
            first int is the first index of self blocks from the last its block where
            begins difference. And second int is the first index of the new blocks from
            the last its blocks where begins difference.
        """
        # TODO: work with block height
        for index1, block in enumerate(reversed(self.blocks)):
            for index2, new_block in enumerate(reversed(new_blocks)):
                if block.__hash__ == new_block.__hash__:
                    return index1, index2
        return len(self.blocks), len(new_blocks)

    def get_last_blocks(self, number=1) -> Optional[List[Block]]:
        """get last n blocks. from -number to last one."""
        # TODO: get from full node if not exist
        if number > len(self.blocks):
            return None  # bad request
        return self.blocks[-number:]

    def search(self, key_hash: str) -> Optional[int]:
        """search from last block to first to find block with this key_hash
        and return its index (height)
        """
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def get_data(self, first_index=0, last_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """get block data from first_index to last_index.
        (last_index = None means to end of blockchain)"""
        # TODO: if not exist get from full node
        if last_index is None:
            last_index = len(self.blocks)
        return [block.get_data() for block in self.blocks[first_index: last_index]]

    def get_hashes(self, first_index=0, last_index: Optional[int] = None) -> List[str]:
        """ get list of blocks hash in blockchain """
        # TODO: if not exist get from full node
        if last_index is None:
            last_index = len(self.blocks)
        if len(self.blocks) == 0:
            return []
        return [block.__hash__ for block in self.blocks[first_index: last_index]]

    def fetch_db(self, db: Optional[DB] = None):
        """Fetching memory data with database

        This method checks just the height of the last block in memory and database and
        compares then the blocks add to/get from the database.
        
        Parameters
        ----------
        db: Optional[DB] = None
            A connected object of `DB` class.
            If it's passed None, it gets that from `core.py`.

        Return
        ------
        Nothing
        """
        if db is None:
            db = core.DATABASE
        block_header = db.get_last_block()
        db_height = 0
        if block_header is not None:
            db_height = block_header["height"]
        distance = self.height - db_height
        if distance > 0:
            # Should insert to db
            for i in range(db_height, self.height):
                # TODO: catch sql error inside db
                db.insert_block(self.blocks[i])
        elif distance < 0:
            # Should query from db
            for i in range(db_height - distance):
                block_data = db.get_block(index=i)
                block = Block.from_json_data_full(block_data)
                self.add_new_block(block, fetch_db=False)

    @staticmethod
    def check_blockchain(
        blocks: List[Block],
        unspent_coins: Dict[str, Coin],
        difficulty: Optional[int] = None  # almost just for unittest
    ) -> Tuple[bool, Optional[int], BlockValidationLevel]:
        """Check the validation of blocks.

        Parameters
        ----------
        blocks: List[Blocks]
            List of the blocks want to be checked.
        unspent_coins: Dict[str, Coin]
            The coins that have not been spent yet for checking blocks transactions.
        difficulty: Optional[int] = None
            The block difficulty that should be for checking block validation.
            If it's passed None, it gets that from configs.

        Returns
        -------
        Tuple[bool, Optional[int], BlockValidationlevel]:
            it Returns a tuple which the first one is to determine blocks are valid or not
            and the second one is the index of block in new_blocks that has a problem, if
            it has been resolved with no problem, the second one is None. And that last
            one for validation level for non valid block it it exists.
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        for index, block in enumerate(blocks):
            pre_hash = ""
            if index != 0:
                pre_hash = blocks[index - 1].__hash__
            validation = block.is_valid_block(unspent_coins,
                                              pre_hash=pre_hash,
                                              difficulty=difficulty)
            if validation != BlockValidationLevel.ALL():
                return False, index, validation
        return True, None, BlockValidationLevel.ALL()

    @staticmethod
    def json_to_blockchain(blockchain_data: List[Dict[str, Any]]) -> BlockChain:
        """Gets a dictionary(json) of list of block data and return a Blockchain object"""
        blockchain = [Block.from_json_data_full(block) for block in blockchain_data]
        return BlockChain(blockchain)

    @property
    def last_block(self) -> Optional[Block]:
        """last block that exists in memory"""
        # TODO: get from db if necessary
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
        """height of last block that exists in memory"""
        last = self.last_block
        if last is None:
            return 0
        return last.block_height

    def __sizeof__(self) -> int:
        size = 0
        for block in self.blocks:
            size += getsizeof(block)
        return size

    def __getitem__(self, index):
        return self.blocks[index]
