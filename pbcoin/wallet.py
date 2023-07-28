from __future__ import annotations

import os.path as opt
from random import randint
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import base64

import pbcoin.config as conf
from pbcoin.utils.address import Address
from pbcoin.utils.tuple_util import tuple_to_string
if TYPE_CHECKING:
    from pbcoin.blockchain import BlockChain
    from pbcoin.mempool import Mempool
    from pbcoin.network import Node

from pbcoin.trx import Trx, Coin
import pbcoin.core as core

#TODO: separate wallet from node
#TODO: Write testcase for Wallet


class Wallet:
    """The Wallet class for tracing your balance in the blockchain and sending coins to
    other address key.

    Attributes
    ----------
    _address: Address
        A Address object that is SECP256K1 address generator.
    """
    _address: Address

    def __init__(self,
                 path_secret_key: str = r"./.key",  # TODO: use global variable
                 wallet_name: Optional[str] = None,
                 generate = True,
                 unspent_coins: Optional[Dict[str, Coin]] = None):
        """
        Parameters
        ----------
        path_secret_key: str = "./.key"
            The path where the key is generated or will be saved there.
        wallet_name: Optional[str] = None
            A name for this wallet object. If it's passed None, it generates a random
            name for this wallet.
        generate = True
            Determines generates and saves key or uses an available key (if there exists)
        unspent_coins: Optional[Dict[str, Coin]] = None
            The coins that have not been spent yet. It should be a global variable that
            will be updated. It's used to trace balance and own coins and update that.
            If it's passed None, it gets that from `core.py` file.

        See Also
        --------
        `class Address` in `address.py`
        """
        if wallet_name is None:
            wallet_name = f"Wallet-{randint(1, 1000)}"
        self.name = wallet_name
        output_path = opt.join(path_secret_key, wallet_name)
        if generate:
            self.gen_key(output_path)
        else:
            self.load_key(output_path)
        if unspent_coins is None:
            unspent_coins = core.ALL_OUTPUTS
        self.unspent_coins = unspent_coins

    def gen_key(self, path: str) -> None:
        """Generates a pair keys (secret & public) and save them in path."""
        self._address = Address()
        self._address.save(path)

    def load_key(self, path: str):
        """Loads a pair keys (secret & public) from path."""
        self._address = Address.load(path)

    async def send_coin(self,
                        recipient: str,
                        value: float,
                        mempool: Optional[Mempool] = None,  # just uses for unittest
                        node: Optional[Node] = None,  # just uses for unittest
    ) -> bool:
        """(async) Makes/Creates a transaction and be sent it to other nodes.
        
        Parameters
        ----------
        recipient: str
            The recipient's public address to which wants to be sent.
        value: float
            The amount of coins that want to be sent to the recipient.
        mempool: Optional[Mempool] = None
            A Mempool object to which the new transaction will be added. If it's passed
            None, it gets that from `core.py` file.
        node: Optional[Node] = None,
            The Node object that uses to send the new transaction to other nodes. If it's
            passed None, it gets that from `core.py` file.
        
        Returns
        -------
        bool
            returns True if all things are going well and that wallet has the amount of
            transaction to send.
        """
        if mempool is None:
            mempool = core.MEMPOOL
        if node is None:
            node = core.NETWORK
        # if user have amount for sending
        if value <= self.balance:
            made_trx = Trx.make_trx(sum(list(self.out_coins.values()), []),
                                    self.public_key, recipient, value)
            # add to own mempool
            if not mempool.add_new_transaction(made_trx,
                                               self.sign(made_trx),
                                               self.public_key,
                                               self.unspent_coins):
                return False
            # send to nodes and add to network mempool
            if conf.settings.glob.network:
                await node.send_new_trx(made_trx, self)
            return True
        else:
            return False

    def sign(self, trx: Trx) -> Tuple[int, int]:
        """Signs the transaction for add to mempool or send other nodes.
        It returns r and s of sign parameters.

        See Also
        --------
        `Address.sign()`
        """
        return self._address.sign(trx.__hash__)

    def base64Sign(self, trx) -> bytes:
        """Signs data and return base 64 signature
        
        See Also
        --------
        `Address.sign()`
        """
        return tuple_to_string(self.sign(trx),
                               max_val=self._address.SECP256K1.N,
                               to_b64=True).decode()

    @property
    def public_key(self) -> str:
        """Base64 of public key"""
        return base64.b64encode(self._address.public_key.encode()).decode()

    @property
    def balance(self) -> int:
        """The summation of unspent output coins values that makes my balance"""
        amount = 0
        for created_trx_hash in self.unspent_coins:
            coins = self.unspent_coins[created_trx_hash]
            for coin in coins:
                if coin.owner == self.public_key:
                    amount += coin.value
        return amount

    @property
    def out_coins(self) -> Dict[str, Coin]:
        """My unspent output coins that be available to spent"""
        my_coins = dict()
        for created_trx_hash in self.unspent_coins:
            coins = self.unspent_coins[created_trx_hash]
            for coin in coins:
                if coin.owner == self.public_key:
                    trx_coins = my_coins.get(coin.created_trx_hash, None)
                    if trx_coins is None:
                        my_coins[coin.created_trx_hash] = [coin]
                    else:
                        trx_coins.append(coin)
        return my_coins