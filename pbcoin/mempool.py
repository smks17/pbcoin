from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from pbcoin.utils.address import Address
from pbcoin.trx import Coin, Trx


class Mempool:
    """ A mempool class to save and handle new transactions for mining in blocks.

    Attributes
    ----------
    transactions: Dict[str, Trx]
        All transactions should be mined. The dict key is the transaction hash and the
        value is the transaction.
    in_mining_transactions: List[str]
        Those priority transactions that for putting in a mining block.
    max_limit_trx: int
        The capacity of in_mining_transactions. The number of transactions will be able to be
        provided and mined in a new block.
    """
    def __init__(self, max_limit_trx: Optional[int] = None):
        if max_limit_trx is None:
            self.max_limit_trx = 10  #TODO
        else:
            self.max_limit_trx = max_limit_trx
        # all transactions that is exist in mempool (even in block that is mining)
        self.transactions: Dict[str, Trx] = dict()
        self.in_mining_transactions: List[str] = []

    def add_in_mining(self):
        """Pics some transactions up to max_limit_trx as priority transactions to be mined"""
        if len(self.in_mining_transactions) >= self.max_limit_trx:
            return
        # TODO: add prior for transactions for add to queue
        for trx in self.transactions:
            if trx not in self.in_mining_transactions:
                self.in_mining_transactions.append(trx)

    def add_new_transaction(self, trx: Trx,
                            sig: Tuple[int, int],
                            public_key: str,
                            unspent_coins: Dict[str, Coin]) -> bool:
        """Adds a new transaction to the transaction queue to will be mined later in a
        block. First, it checks the transaction and signature then adds the transaction
        to mempool and then will update in_mining_transactions if it's necessary.

        Args
        ----
        trx: Trx
            The transaction that you want to be added to the mempool.
        sig: Tuple[int, int]
            Parameters of signature (r, s) from the transaction.
        pub_key: str
            Sender public key address in hex.
        unspent_coins: Dict[str, Coin]
            The coins that have not been spent yet. It's used to check the validation
            transaction.

        Return
        ------
        bool
            Returns True if the transaction is valid.
        """
        # TODO: return why result is False
        # checking it is not repetitious transaction
        if trx.__hash__ in self.transactions:
            return False
        # checking its sign to be verified
        if not Address.verify(trx.__hash__, sig, public_key, from_b64=True):
            return False
        # check double spent and other things
        if not trx.check(unspent_coins):
            return False
        self.transactions[trx.__hash__] = deepcopy(trx)
        self.add_in_mining()
        return True

    def remove_transaction(self, trx_hash: str) -> bool:
        """Remove a transaction from mempool and return True if exists, otherwise return
        False
        """
        res = self.transactions.get(trx_hash)
        if res is None:
            return False
        else:
            self.transactions.pop(trx_hash)
            self.in_mining_transactions.remove(trx_hash)
            return True

    def remove_transactions(self, list_trx: List[str]):
        """Removes a list of transaction from mempool and return True if they exist,
        otherwise return False
        """
        for trx_hash in self.in_mining_transactions:
            if trx_hash in list_trx:
                self.remove_transaction(trx_hash)

    def is_exist(self, trx_hash: str):
        """Checks a transaction is in mempool or not"""
        return trx_hash in self.transactions

    def get_mine_transactions(self, n_trx: Optional[int] = None) -> List[Trx]:
        """Pics just n transaction from in_mining_transactions and put it again in
        in_mining_transactions (inplace). n_trx is should be less than max_limit_trx
        """
        # TODO: check n_trx is less than max_limit_trx
        if n_trx is None:
            n_trx = self.max_limit_trx
        self.in_mining_transactions = self.in_mining_transactions[:n_trx]

    def reset(self):
        """Updates new in_mining_transactions"""
        self.get_mine_transactions()

    def __len__(self) -> int:
        """the number of all transactions in mempool"""
        return len(self.transactions)

    def __getattr__(self, item: str):
        assert isinstance(item, str)
        return deepcopy(self.transactions[item])

    def __iter__(self):
        for trx in self.in_mining_transactions:
            yield self.transactions[trx]

    def __contain__(self, key: str | Trx):
        if isinstance(key, str):
            return key in self.in_mining_transactions
        elif isinstance(key, Trx):
            return key.__hash__ in self.in_mining_transactions
        else:
            ValueError(f"Not supported {type(key)}")

    def __repr__(self) -> str:
        return self.transactions.values().__repr__()
