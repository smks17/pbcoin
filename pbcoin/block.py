from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from functools import reduce
from enum import Flag, auto
from operator import or_ as _or_
from hashlib import sha512
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
    Block contains transactions and nodes find a hash of them
    that is less than difficulty

    Attributes
    ----------
        trx_list: list[Trx]
            list of all trx in block
        previous_hash: str
            hash of previous block in blockchain
        nonce: int

        block_hash: str
            hash string this block (in hex)
        time: float
            time that this block mined in POSIX timestamp format
        is_mined: bool = False
            if it is True, it means block is mined
        block_height: int
            how many block is before that block in blockchain
        trx_hashes: list[str]
            list of all trx hash (using for header block)
        merkle_tree: MerkleTree = None
            a object of MerkleTree class of root
    """

    def __init__(self, preHash: str, block_height: int, subsidy: Optional[Trx] = None):
        self.previous_hash = preHash
        self.block_height = block_height
        self.nonce = 0
        self.time = datetime.utcnow().timestamp()
        # make subsidy trx (a trx that give itself reward for mine block)
        if subsidy is not None:
            self.transactions = [subsidy]
            self.merkle_tree = self.build_merkle_tree()
            self.has_subsidy = True
        else:
            self.transactions = []
            self.merkle_tree = None
            self.has_subsidy = False

    def add_trx(self, trx_: Trx) -> None:
        """ add new trx without checking to block """
        self.transactions.append(trx_)
        # TODO: implement add function in merkle tree
        self.build_merkle_tree()
        self.calculate_hash()
        for coin in trx_.outputs:
            coin.trx_hash = trx_.__hash__

    def get_list_hashes_trx(self) -> list[str]:
        return [trx.__hash__ for trx in self.transactions]

    def build_merkle_tree(self) -> None:
        """ set and build merkle tree from trxs of block"""
        self.merkle_tree = MerkleTreeNode.build_merkle_tree(
            self.get_list_hashes_trx())

    def set_mined(self) -> None:
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def check_trx(self, unspent_coins: dict[str, Coin]) -> bool:
        """checking the all block trx"""
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
                    my_unspent = unspent_coins[coin.trx_hash]
                    my_unspent[coin.index] = None
                    if not any(my_unspent):
                        # delete input coin from unspent_coins coins
                        unspent_coins.pop(coin.trx_hash)
                else:
                    pass  # TODO

            # add output coins to unspent coins
            for coin in out_coins:
                trx_hash = coin.trx_hash
                unspent_coins[trx_hash] = deepcopy(out_coins)

    def revert_outputs(self, unspent_coins: dict[str, Coin]):
        for trx in self.transactions:
            in_coins = trx.inputs
            out_coins = trx.outputs
            # add input coins to unspent coins
            for coin in in_coins:
                trx_hash = coin.trx_hash
                unspent_coins[trx_hash] = deepcopy(out_coins)

            for coin in out_coins:
                my_unspent = unspent_coins[coin.trx_hash]
                my_unspent[coin.index] = None
                if not any(my_unspent):
                    # delete output coin from unspent_coins coins
                    unspent_coins.pop(coin.trx_hash)

    def set_nonce(self, nonce_: int): self.nonce = nonce_

    def calculate_hash(self) -> str:
        if self.merkle_tree is None:
            self.build_merkle_tree()
        data = self.merkle_tree.hash + str(self.nonce) + self.previous_hash + str(self.time)
        calculated_hash = sha512((data).encode()).hexdigest()
        self.block_hash = calculated_hash
        return calculated_hash

    def is_valid_block(
        self,
        unspent_coins: Dict[str, Coin],
        pre_hash = "",
        difficulty = None  # almost for unittest
    ) -> BlockValidationLevel:
        """checking validation and return validation level"""
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
        """search from last block to first for find block with key_hash"""
        for i in range(len(self.blocks)-1, -1, -1):
            if self.blocks[i].__hash__ == key_hash:
                return i
        return None

    def get_data(self, is_full_block=True, is_POSIX_timestamp=True) -> dict[str, Any]:
        """
            get data of block that has:
                header:
                - hash: block hash
                - height: block height (number of blocks before this block)
                - nonce:
                - number trx: number of transactions in this block
                - merkle_root: merkle tree root hash of transactions
                - trx_hashes: list of transactions hash
                - previous_hash
                - time: the time is mined

                other:
                - trx: list of all block transactions
                - size: size of data (block)
            
            argument
            --------
                - fis_ull_block: bool = True
                    if it is False, return just header block data
                - is_POSIX_timestamp: bool = True:
                    if it is False, return data with humanely time represent
            return
            ------
                dict[str, any]
                    return block data
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
    def from_json_data_header(data: dict['str', any], is_POSIX_timestamp=True) -> Block:
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
        new_block = Block.from_json_data_header(data['header'], is_POSIX_timestamp)
        trx = data['trx']
        trxList_ = []
        for each_trx in trx:
            inputs = []
            for coin_idx, in_coin in enumerate(each_trx['inputs']):
                inputs.append(
                    Coin(in_coin['owner'],
                         coin_idx,
                         in_coin['trx_hash'],
                         in_coin['value']))
            outputs = []
            for coin_idx, out_coin in enumerate(each_trx['outputs']):
                outputs.append(
                    Coin(out_coin['owner'],
                         coin_idx,
                         out_coin['trx_hash'],
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
