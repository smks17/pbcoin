from __future__ import annotations

from os import makedirs
from random import random
from typing import Dict, List, Optional, TYPE_CHECKING

from ellipticcurve.privateKey import PrivateKey
from ellipticcurve.signature import Signature
from ellipticcurve.ecdsa import Ecdsa

import pbcoin.config as conf
if TYPE_CHECKING:
    from pbcoin.blockchain import BlockChain
    from pbcoin.mempool import Mempool
    from pbcoin.network import Node

from pbcoin.trx import Trx, Coin
import pbcoin.core as core

#TODO: separate wallet from node


class Wallet:
    n_amount: float
    walletKey: PrivateKey
    out_coins: Dict[str, List[Coin]]
    name = f"Wallet-{int(random()*1000)}"

    def __init__(self, key=None):
        if key is not None:
            # TODO: check keys
            # TODO: trace for find amount of wallet
            pass
        else:
            self.gen_key()
            self.n_amount = 0
            self.out_coins = dict()

    def gen_key(self):
        """generate a pair key and save in memory and file"""
        # TODO: better usage
        self.walletKey = PrivateKey()
        makedirs("./.key", exist_ok=True)
        with open("./.key/key.pub", "w") as file:
            file.write(self.public_key)
        with open("./.key/key.sk", "w") as file:
            file.write(str(self.walletKey.secret))

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
                                               self.walletKey.publicKey(),
                                               unspent_coins):
                return False
            # send to nodes and add to network mempool
            if conf.settings.glob.network:
                await node.send_new_trx(made_trx, self)
            return True
        else:
            return False

    def sign(self, trx: Trx) -> Signature:
        """sign the transaction for add to mempool or send other nodes"""
        return Ecdsa.sign(trx.__hash__, self.walletKey)

    def base64Sign(self, trx_) -> bytes:
        """sign data and return base 64 signature"""
        return self.sign(trx_).toBase64()

    @property
    def public_key(self) -> str:
        return self.walletKey.publicKey().toString()
