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


class Wallet:
    n_amount: float
    _address: Address
    out_coins: Dict[str, List[Coin]]

    def __init__(self,
                 path_secret_key: str = r"./.key",  # TODO: use global variable
                 wallet_name: Optional[str] = None,
                 generate = True,):
        if wallet_name is None:
            wallet_name = f"Wallet-{randint(1, 1000)}"
        self.name = wallet_name
        output_path = opt.join(path_secret_key, wallet_name)
        if generate:
            self.gen_key(output_path)
        else:
            self.load_key(output_path)
        self.n_amount = 0
        self.out_coins = dict()

    def gen_key(self, path: str):
        self._address = Address()
        self._address.save(path)

    def load_key(self, path: str):
        self._address = Address.load(path)

    def updateBalance(self, trx_list: List[Trx]) -> None:
        """update balance wallet user from new trx list"""
        for trx in trx_list:
            for in_coin in trx.inputs:
                if in_coin.owner == self.public_key:
                    self.out_coins[in_coin.trx_hash].remove(in_coin)
                    self.n_amount -= in_coin.value  # TODO: check nAmount

            for out_coin in trx.outputs:
                if out_coin.owner == self.public_key:
                    trx = self.out_coins.get(out_coin.trx_hash, None)
                    if trx:
                        self.out_coins[out_coin.trx_hash].append(out_coin)
                    else:
                        self.out_coins[out_coin.trx_hash] = [out_coin]
                    self.n_amount += out_coin.value

    async def send_coin(self,
                        recipient: str,
                        value: float,
                        mempool: Optional[Mempool] = None,  # just uses for unittest
                        blockchain: Optional[BlockChain] = None,  # just uses for unittest
                        node: Optional[Node] = None,  # just uses for unittest
                        unspent_coins: Optional[Dict[str, Coin]] = None) -> bool:
        """make a transaction to send coins and publish trx to the network"""
        if mempool is None:
            mempool = core.MEMPOOL
        if blockchain is None:
            blockchain = core.BLOCK_CHAIN
        if node is None:
            node = core.NETWORK
        if unspent_coins is None:
            unspent_coins = core.ALL_OUTPUTS
        # if user have amount for sending
        if value <= self.n_amount:
            made_trx = Trx.make_trx(sum(list(self.out_coins.values()), []),
                                    self.public_key, recipient, value)
            # add to own mempool
            if not mempool.add_new_transaction(made_trx,
                                               self.sign(made_trx),
                                               self.walletKey.public_key,
                                               unspent_coins):
                return False
            # send to nodes and add to network mempool
            if conf.settings.glob.network:
                await node.send_new_trx(made_trx, self)
            return True
        else:
            return False

    def sign(self, trx: Trx) -> Tuple[int, int]:
        """sign the transaction for add to mempool or send other nodes"""
        return self._address.sign(trx.__hash__)

    def base64Sign(self, trx_) -> bytes:
        """sign data and return base 64 signature"""
        return tuple_to_string(self.sign(trx_),
                               max_val=self._address.SECP256K1.N,
                               to_b64=True).decode()

    @property
    def public_key(self) -> str:
        """base64 of public key"""
        return base64.b64encode(self._address.public_key.encode()).decode()
