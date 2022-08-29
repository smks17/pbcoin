from __future__ import annotations

from datetime import datetime
from hashlib import sha512
from sys import getsizeof
from typing import Any

import pbcoin.core as core
from .trx import Coin, Trx
from .merkle_tree import MerkleTreeNode

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

    def __init__(self, preHash: str, block_height: int):
        self.previous_hash = preHash
        self.block_height = block_height
        self.nonce = 0
        # make subsidy trx (a trx that give itself reward for mine block)
        subsidy = Trx(self.block_height)
        self.transactions = [subsidy]
        self.merkle_tree = self.build_merkle_tree()

    def add_trx(self, trx_: Trx) -> None:
        """ add new trx without checking to block """
        self.transactions.append(trx_)
        # TODO: implement add function in merkle tree
        self.build_merkle_tree()

    def get_list_hashes_trx(self) -> list[str]:
        return [trx.hash_trx for trx in self.transactions]

    def build_merkle_tree(self) -> None:
        """ set and build merkle tree from trxs of block"""
        self.merkle_tree = MerkleTreeNode.build_merkle_tree(
            self.get_list_hashes_trx())

    def set_mined(self) -> None:
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def check_trx(self) -> bool:
        """checking the all block trx"""
        # TODO: return validation
        for index, trx in enumerate(self.transactions):
            in_coins = trx.inputs
            out_coins = trx.outputs
            for coin in in_coins:
                # is input coin trx valid
                if not coin.check_input_coin():
                    return False
            if index != 0:
                # check equal input and output value
                output_value = sum(out_coin.value for out_coin in out_coins)
                input_value = sum(in_coin.value for in_coin in in_coins)
                if output_value != input_value:
                    return False
            # check valid time
            if trx.time <= datetime(2022, 1, 1).timestamp():
                return False
            # check trx hash output coin
            if not all([out_coin.trx_hash == trx.hash_trx for out_coin in out_coins]):
                return False
        return True

    def update_outputs(self) -> None:
        """update "database" of output coins that are unspent"""
        for trx in self.transactions:
            in_coins = trx.inputs
            out_coins = trx.outputs
            for coin in in_coins:
                # check input coin and if is valid, delete from unspent coins
                if coin.check_input_coin():
                    unspent = core.ALL_OUTPUTS[trx_hash]
                    unspent[coin.index] = None
                    if not any(unspent):
                        core.ALL_OUTPUTS.pop(trx_hash)
                else:
                    pass  # TODO

            # add output coins to unspent coins
            for coin in out_coins:
                trx_hash = coin.trx_hash
                core.ALL_OUTPUTS[trx_hash] = out_coins

    def set_nonce(self, nonce_: int): self.nonce = nonce_

    def calculate_hash(self) -> str:
        if not self.merkle_tree:
            self.build_merkle_tree()
        nonce_hash = sha512(str(self.nonce).encode()).hexdigest()
        calculated_hash = sha512(
            (self.merkle_tree.hash + nonce_hash + self.previous_hash).encode()
        ).hexdigest()
        self.block_hash = calculated_hash
        return calculated_hash

    def get_data(self, is_full_lock=True, is_POSIX_timestamp=True) -> dict[str, Any]:
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
        if is_full_lock:
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
                        in_coin['value']
                    )
                )
            outputs = []
            for coin_idx, out_coin in enumerate(each_trx['outputs']):
                outputs.append(
                    Coin(out_coin['owner'],
                        coin_idx,
                        out_coin['trx_hash'],
                        out_coin['value']
                    )
                )
            trxList_.append(
                Trx(new_block.block_height, inputs, outputs, each_trx['time'])
            )
        new_block.transactions = trxList_
        return new_block

    @property
    def __hash__(self):
        return self.calculate_hash() if self.block_hash == None else self.block_hash

    def __str__(self) -> str:
        return self.transactions.__str__() + str(self.proof) + self.previous_hash

    def __repr__(self) -> str:
        return self.get_data()
