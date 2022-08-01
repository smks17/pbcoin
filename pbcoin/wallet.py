import logging
import os
from random import random

from ellipticcurve.privateKey import PrivateKey
from ellipticcurve.ecdsa import Ecdsa

import pbcoin
import pbcoin.trx as trx

class Wallet:
    nAmount: float
    walletKey: PrivateKey
    out_coins: dict[str,list[trx.Coin]]
    name = f"Wallet-{int(random()*1000)}"

    def __init__(self, key = None):
        if key != None:
            # TODO: check keys
            # TODO: trace for find amount of wallet
            pass
        else:
            self.genKey()
            self.nAmount = 0
            self.out_coins = dict()

    def genKey(self):
        self.walletKey = PrivateKey()
        os.makedirs("./.key", exist_ok=True)
        with open("./.key/key.pub", "w") as file:
            file.write(self.walletKey.publicKey().toString())
        with open("./.key/key.sk", "w") as file:
            file.write(str(self.walletKey.secret))

    def updateBalance(self, trxList: list[trx.Trx]):
        for trx in trxList:
            for in_coin in trx.inputs:
                if in_coin.owner == self.walletKey.publicKey().toString():
                    self.out_coins[in_coin.trxHash].remove(in_coin)
                    self.nAmount -= out_coin.value # TODO: check nAmount

            for out_coin in trx.outputs:
                if out_coin.owner == self.walletKey.publicKey().toString():
                    res_trx = self.out_coins.get(out_coin.trxHash, None)
                    if res_trx:
                        self.out_coins[out_coin.trxHash].append(out_coin)
                    else:
                        self.out_coins[out_coin.trxHash] = [out_coin]
                    self.nAmount += out_coin.value

    async def sendCoin(self, recipient: str, value: float):
        if value <= self.nAmount:
            made_trx = trx.Trx.makeTrx(sum(list(self.out_coins.values()), []),
                            self.walletKey.publicKey().toString(), recipient, value)
            if not pbcoin.MINER.addTrxToMempool(made_trx, self.sign(made_trx), self.walletKey.publicKey()):
                return False
            await pbcoin.NETWORK.sendNewTrx(made_trx)
            return True
        else:
            return False

    def sign(self, _trx):
        return Ecdsa.sign(_trx.__hash__, pbcoin.wallet.walletKey)

    def base64Sign(self, _trx):
        return self.sign(_trx).toBase64()