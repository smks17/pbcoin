from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from functools import reduce
from enum import Flag, auto
from operator import or_ as _or_
from hashlib import sha256
from sys import getsizeof
from typing import Any, Dict, Optional

import pbcoin.config as conf
from pbcoin.merkle_tree import MerkleTreeNode
from pbcoin.trx import Coin, Trx


class BlockValidationLevel(Flag):
    Bad = 0
    DIFFICULTY = auto()
    TRX = auto()
    PREVIOUS_HASH = auto()

    @classmethod
    def ALL(cls, except_validations: Optional[BlockValidationLevel] = None):
        """get variable with all flag for checking validation
        also remove except_validations from all

        except_validations: Optional[BlockValidationLevel] = None
            this is validation levels that you want ignore
        """
        if except_validations is None:
            except_validations = cls.Bad
        cls_name = cls.__name__
        if not len(cls):
            raise AttributeError(
                f'empty {cls_name} does not have an ALL value')
        values = filter(lambda x: (x & except_validations) == cls.Bad, cls)
        value = cls(reduce(_or_, values))
        cls._member_map_['ALL'] = value
        return value


class Block:
    """
    The block contains transactions to find a nonce which the block hash should be less
    than difficulty to solve proof-of-work.

    Attributes
    ----------
        - Block Header

        previous_hash: str
            Hash of previous block in blockchain.
        nonce: int
            The number that is added to block hash to be less than difficulty.
        block_hash: str
            Hash string of this block (in hex).
        time: float
            Time that this block mined in POSIX timestamp format.
        is_mined: bool = False
            If it is True, it means block is mined.
        block_height: int
            Determines this block is the nth block that has been mined.
        trx_hashes: list[str]
            List of all trx hash
        merkle_tree: MerkleTree = None
            A object of MerkleTree class of root from list of trx hashes.

        - Addition in Full Block

        trx_list: list[Trx]
            List of all trx in the block.
    """

    def __init__(self, previous_hash: str, block_height: int, subsidy: Optional[Trx] = None):
        """initialize previous_hash, block_height and subsidy(optional)"""
        self.previous_hash = previous_hash
        self.block_height = block_height
        self.nonce = 0
        self.time = datetime.utcnow().timestamp()  # TODO: get from args
        # make subsidy trx (a trx that give itself reward for mine block)
        if subsidy is not None:
            self.transactions = [subsidy]
            self.merkle_tree = self.build_merkle_tree()
            self.has_subsidy = True
        else:
            self.transactions = []
            self.merkle_tree = None
            self.has_subsidy = False

    def add_trx(self, trx: Trx) -> None:
        """Adds new trx without checking it. Also sets the trx hashes coin object."""
        self.transactions.append(trx)
        # TODO: implement add function in merkle tree
        # recalculate merkle tree root hash and trx hash
        self.build_merkle_tree()
        self.calculate_hash()
        # Sets input to spent coin
        for i, coin in enumerate(trx.inputs):
            coin.spend(trx.__hash__, i)
        # Set created_trx_hash of output coins.
        for i, coin in enumerate(trx.outputs):
            coin.created_trx_hash = trx.__hash__
            coin.out_index = i

    def get_list_hashes_trx(self) -> list[str]:
        """Gets the list of all transactions hash"""
        return [trx.__hash__ for trx in self.transactions]

    def build_merkle_tree(self) -> None:
        """Sets and builds merkle tree from list of block trx"""
        self.merkle_tree = MerkleTreeNode.build_merkle_tree(
            self.get_list_hashes_trx())

    def set_mined(self) -> None:
        """Sets this block has been mined and sets block time now"""
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def check_trx(self, unspent_coins: dict[str, Coin]) -> bool:
        """Checks the all block transactions. 
        
        See Also
        -------
        `trx.check()`
        """
        # TODO: return validation
        for trx in self.transactions:
            if not trx.check(unspent_coins):
                return False
        return True

    def update_outputs(self, unspent_coins: dict[str, Coin]) -> None:
        """update "database"(TODO) of output coins that are unspent"""
        for trx in self.transactions:
            in_coins = trx.inputs
            out_coins = trx.outputs
            for coin in in_coins:
                # check input coin and if is valid, delete from unspent coins
                if coin.check_input_coin(unspent_coins):
                    my_unspent = unspent_coins[coin.created_trx_hash]
                    my_unspent[coin.out_index] = None
                    if not any(my_unspent):
                        # delete input coin from unspent_coins coins
                        unspent_coins.pop(coin.created_trx_hash)
                else:
                    pass  # TODO

            # add output coins to unspent coins
            for coin in out_coins:
                trx_hash = coin.created_trx_hash
                unspent_coins[trx_hash] = deepcopy(out_coins)

    def revert_outputs(self, unspent_coins: dict[str, Coin]):
        """Gets the unspent coins and reverse it inplace by this block transaction"""
        # TODO: Relocated this method. here is a bad place for it.
        for trx in self.transactions:
            in_coins = trx.inputs
            out_coins = trx.outputs
            # add input coins to unspent coins
            for coin in out_coins:
                trx_hash = coin.created_trx_hash
                unspent_coins[trx_hash] = deepcopy(out_coins)

            for coin in in_coins:
                my_unspent = unspent_coins[coin.created_trx_hash]
                my_unspent[coin.out_index] = None
                if not any(my_unspent):
                    # delete output coin from unspent_coins coins
                    unspent_coins.pop(coin.created_trx_hash)

    def set_nonce(self, nonce: int):
        self.nonce = nonce

    def calculate_hash(self) -> str:
        if self.merkle_tree is None:
            self.build_merkle_tree()
        data = self.merkle_tree.hash + str(self.nonce) + self.previous_hash + str(self.time)
        calculated_hash = sha256((data).encode()).hexdigest()
        self.block_hash = calculated_hash
        return calculated_hash

    def is_valid_block(
        self,
        unspent_coins: Dict[str, Coin] = None,
        pre_hash: str = "",
        difficulty: Optional[int] = None  # almost for unittest
    ) -> BlockValidationLevel:
        """Checks validation and return validation level

        Parameters
        ---------
        unspent_coins: Optional[Dict[str, Coin]] = None
            The coins that have not been spent yet. It's used to check the validation
            block (transactions).
        pre_hash: str = ""
            The  hash of previous block that is before this block in blockchain.
        difficulty: Optional[int] = None
            The block difficulty that should be.
            If it's passed None, it gets that from configs.

        Return
        ------
        BlockValidationLevel
            Determine that block passed which fields.
        """
        if difficulty is None:
            difficulty = conf.settings.glob.difficulty
        valid = BlockValidationLevel.Bad
        # difficulty level
        if int(self.__hash__, 16) <= difficulty:
            valid = valid | BlockValidationLevel.DIFFICULTY
        # check all trx
        if self.check_trx(unspent_coins):
            valid = valid | BlockValidationLevel.TRX
        # check previous hash
        if self.previous_hash == pre_hash:
            valid = valid | BlockValidationLevel.PREVIOUS_HASH
        return valid

    def search(self, key_hash) -> Optional[int]:
        """Searches from last block to first for finding the block which
        its hash is key_hash
        """
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def get_data(self, is_full_block=True, is_POSIX_timestamp=True) -> dict[str, Any]:
        """gets data of this block that has:

            header:
            - hash: str
            - height: int
            - nonce: int
            - number_trx: int
            - merkle_root: str
            - trx_hashes: List[str]
            - previous_hash: str
            - time: int | str

            other:
            - trx: List[Dict[str, any]]
            - size: int

            Parameters
            ----------
            is_full_block: bool = True
                If it is False, then return just the header block data.
            is_POSIX_timestamp: bool = True:
                If it is False, then return data with humanely readable time represent.

            Return
            ------
                dict[str, any]
                    return the block data
        """
        block_header = {
            "hash": self.__hash__,
            "height": self.block_height,
            "nonce": self.nonce,
            "number_trx": len(self.transactions),
            "merkle_root": self.merkle_tree.hash,
            "trx_hashes": self.get_list_hashes_trx(),
            "previous_hash": self.previous_hash,
            "time": self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time).__str__()
        }
        data = block_header
        if is_full_block:
            trx_list = []
            for i in range(len(self.transactions)):
                trx = self.transactions[i].get_data()
                trx['index'] = i
                trx_list.append(trx)
            data = {
                "size": 0,  # set after init
                "trx": trx_list,
                "header": block_header
            }
            data['size'] = getsizeof(data)
        return data

    @staticmethod
    def from_json_data_header(data: dict[str, Any], is_POSIX_timestamp=True) -> Block:
        """gets a block data header like `get_block` function and then
        make a Block object from that.

        See Also
        --------
        `Block.get_date()`: The function create data like inputs.
        """
        new_block = Block(data['previous_hash'], data['height'])
        new_block.block_hash = data['hash']
        new_block.nonce = data['nonce']
        new_block.trx_hashes = data['trx_hashes']
        new_block.merkle_tree = MerkleTreeNode(data['merkle_root'])
        if is_POSIX_timestamp:
            new_block.time = data['time']
        else:
            datetime.fromisoformat(data['time'])
        return new_block

    @staticmethod
    def from_json_data_full(data: dict['str', any], is_POSIX_timestamp=True) -> Block:
        """gets a block full data like `get_block` function and then
        make a Block object from that.

        See Also
        --------
        `Block.get_date()`: The function create data like inputs.
        """
        new_block = Block.from_json_data_header(data['header'], is_POSIX_timestamp)
        trx = data['trx']
        trxList_ = []
        for each_trx in trx:
            inputs = []
            for coin_idx, in_coin in enumerate(each_trx['inputs']):
                # TODO: It should be in Coin class
                inputs.append(
                    Coin(in_coin['owner'],
                         in_coin['in_index'],
                         in_coin['created_trx_hash'],
                         in_coin['value'],
                         in_coin['trx_hash'],
                         in_coin['out_index']))
            outputs = []
            for coin_idx, out_coin in enumerate(each_trx['outputs']):
                outputs.append(
                    Coin(out_coin['owner'],
                         coin_idx,
                         out_coin['created_trx_hash'],
                         out_coin['value']))
            trxList_.append(Trx(new_block.block_height, "", inputs, outputs, each_trx['time']))
        new_block.transactions = trxList_
        return new_block

    @property
    def hash_list_trx(self):
        return [trx.__hash__ for trx in self.transactions]

    @property
    def __hash__(self):
        if (hasattr(self, 'block_hash') and self.block_hash is not None):
            return self.block_hash
        else:
            return self.calculate_hash()

    def __eq__(self, __o: object) -> bool:
        return __o.__hash__ == self.__hash__

    def __str__(self) -> str:
        return self.transactions.__str__() + str(self.proof) + self.previous_hash

    def __repr__(self) -> str:
        return self.block_hash[-8:]
