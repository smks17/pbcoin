from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

from ellipticcurve.ecdsa import Ecdsa
from ellipticcurve.publicKey import PublicKey
from ellipticcurve.signature import Signature

from .block import Block
from .trx import Coin, Trx

class Mempool:
    """ A mempool class to save and handle new transaction for adding to mempool

    Attributes
    ----------
        transactions: Dict[str, Trx]
            all transaction that should be mined
        in_mining_block: List[str]
            those transaction that in priority for put in mining block
        max_limit_trx: int
            the capacity of in_mining_block
    """
    def __init__(self, max_limit_trx: Optional[int] = None):
        if max_limit_trx is None:
            self.max_limit_trx = 10 #TODO
        else:
            self.max_limit_trx = max_limit_trx
        # all transactions that is exist in mempool (even in block that is mining)
        self.transactions: Dict[str, Trx] = dict()
        self.in_mining_block: List[str] = []

    def add_in_mining(self):
        """add the new transactions to transaction should put in mining blocks"""
        if len(self.in_mining_block) >= self.max_limit_trx:
            return
        # TODO: add prior for transactions for add to queue
        for trx in self.transactions:
            if trx not in self.in_mining_block:
                self.in_mining_block.append(trx)

    def add_new_transaction(self, trx: Trx, sig: Signature, last_block: Block,
                            pub_key: PublicKey, unspent_coins: Dict[str, Coin]) -> bool:
        """add a new transaction to the all mempool transaction and the queue for mining block
        
        Args
        ----
        trx: Trx
            the transaction that you want add to the mempool
        sig: Signature
            signature of the transaction that sender sign
        last_block: Block
            the last block of blockchain
        pub_key: PublicKey
            sender public key
        unspent_coins: Dict[str, Coin]
            list of unspent coins until here
        """
        # TODO: return why result is False
        # checking it is not repetitious transaction
        if trx.__hash__ in self.transactions:
            return False
        # checking its sign to be verified
        if not Ecdsa.verify(trx.__hash__, sig, pub_key):
            return False
        # check double spent and other things
        if not last_block.check_trx(unspent_coins):
            return False
        self.transactions[trx.__hash__] = deepcopy(trx)
        self.add_in_mining()
        return True

    def remove_transaction(self, trx_hash: str) -> bool:
        res = self.transactions.get(trx_hash)
        if res is None:
            return False
        else:
            self.transactions.pop(trx_hash)
            self.in_mining_block.remove(trx_hash)
            return True

    def remove_transactions(self) -> bool:
        for trx_hash in self.in_mining_block:
            self.remove_transaction(trx_hash)

    def is_exist(self, trx_hash):
        return trx_hash in self.transactions

    def get_mine_transactions(self, n_trx: Optional[int] = None) -> List[Trx]:
        """get n transaction for put in miner block"""
        if n_trx is None:
            n_trx = self.max_limit_trx
        self.in_mining_block = self.in_mining_block[:n_trx]

    def reset(self):
        self.get_mine_transactions()

    def __len__(self) -> int:
        """the number of all transactions in mempool"""
        return len(self.transactions)

    def __getattr__(self, item: str):
        assert isinstance(item, str)
        return deepcopy(self.transactions[item])
    
    def __iter__(self):
        for trx in self.in_mining_block:
            yield self.transactions[trx]

    def __contain__(self, key):
        assert isinstance(key, str, Trx)
        if type(key) == str:
            return key in self.in_mining_block
        else:
            return key.__hash__ in self.in_mining_block

    def __repr__(self) -> str:
        return self.transactions.values().__repr__()