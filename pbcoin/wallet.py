import os

from ellipticcurve.privateKey import PrivateKey

from random import random
import pbcoin.trx as trx

class Wallet:
    nAmount: int
    walletKey: PrivateKey
    out_coins: list[trx.Coin]
    name = f"Wallet-{int(random()*1000)}"

    def __init__(self, key = None):
        if key != None:
            # TODO: check keys
            # TODO: trace for find amount of wallet
            pass
        else:
            self.genKey()

    def genKey(self):
        self.walletKey = PrivateKey()
        os.makedirs("./.key", exist_ok=True)
        with open("./.key/key.pub", "w") as file:
            file.write(self.walletKey.publicKey().toString())
        with open("./.key/key.sk", "w") as file:
            file.write(str(self.walletKey.secret))
