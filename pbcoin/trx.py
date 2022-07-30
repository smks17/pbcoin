from datetime import datetime
from hashlib import sha512
import json

from ellipticcurve.ecdsa import Ecdsa

import pbcoin

DEFAULT_SUBSIDY = 50

class Coin:
    nCoins = 0
    def __init__(self, _owner, index: int, _trxHash: str = "", _value = DEFAULT_SUBSIDY):
        self.owner = _owner
        self.value = _value
        self.trxHash = _trxHash
        self.index = index

    def addOutput(self, recipient_key: str, value: float) -> tuple[bool, int]:
        """
            add a transaction

            args
            ----
            recipient_key: str
                address key of recipient
            value: float
                amount which transfer to recipient wallet

            return
            ------
            list[Coin]:
                return the outputs coin
        """
        outputs = []
        remain = self.value - value
        if remain > 0:
            outputs.append(Coin(self.owner, len(outputs), _value=remain))
            outputs.append(Coin(recipient_key, len(outputs) ,_value=value))
        else:
            outputs.append(Coin(recipient_key, len(outputs) ,_value=value))

        return outputs, remain

    def getData(self):
        return {
            "value": self.value,
            "owner": self.owner,
            "trx_hash": self.trxHash,
            "index": self.index
        }

    def __repr__(self):
        return f"{self.owner} {self.value}"

    def __eq__(self, __o: object) -> bool:
        return (self.trxHash == __o.trxHash and self.index == __o.index)

    def checkInputCoin(self):
        trxHash = self.trxHash
        unspent = pbcoin.ALL_OUTPUTS.get(trxHash, None)
        if unspent:
            owner_coin = unspent[self.index]
            if owner_coin.owner == self.owner:
                return True
            else:
                return False

class Trx:
    inputs: list[Coin]
    outputs: list[Coin]
    time: float
    hashTrx: str
    is_generic: bool
    include_block: int
    def __init__(self, include_block: int, _inputs: list[Coin] = None, _outputs: list[Coin] = None, time = None):
        if _inputs == None and _outputs == None:
            self.time = datetime.utcnow().timestamp() if not time else time
            self.senders = []
            self.recipients = [pbcoin.wallet.walletKey.publicKey().toString()]
            self.value = DEFAULT_SUBSIDY
            self.hashTrx = self.calculateHash()
            self.outputs = [Coin(pbcoin.wallet.walletKey.publicKey().toString(), 0, self.hashTrx, self.value)]
            self.inputs = []
            self.is_generic = True
        else:
            self.time = datetime.utcnow().timestamp() if not time else time
            self.senders = [in_coin.owner for in_coin in _inputs]
            self.recipients = [out_coin.owner for out_coin in _outputs]
            self.value = sum(coin.value for coin in _outputs)
            self.hashTrx = self.calculateHash()
            self.inputs = _inputs # TODO: check input not to be empty
            self.outputs = _outputs
            self.is_generic = False
        self.include_block = include_block

    @staticmethod
    def makeTrx(owner_coins: list[Coin], sender_key: str, recipient_key: str, value: float):
        # create non generic trx
        remain = value
        outputs = []
        inputs = []
        for coin in owner_coins:
            if coin.owner == sender_key:
                inputs.append(coin)
                coin_output, remain_coin = coin.addOutput(recipient_key, remain)
                if remain_coin <= 0:
                    remain -= coin.value
                else:
                    remain -= value
                outputs += coin_output
                if remain == 0:
                    break
        
        if remain != 0:
            return None
        trx = Trx(0, inputs, outputs)
        trx.setHashCoins()
        return trx

    def setHashCoins(self):
        for out_coin in self.outputs:
            out_coin.trxHash = self.hashTrx

    def calculateHash(self):
        calHash = sha512((f"{self.senders}{self.recipients}{self.value}{self.time}").encode()).hexdigest()
        self.blockHash = calHash
        return calHash

    def getData(self, with_hash = False, is_POSIX_timestamp = True):
        data = {
            'inputs': [in_coin.getData() for in_coin in self.inputs] if not self.is_generic else [],
            'outputs': [out_coin.getData() for out_coin in self.outputs],
            'value': self.value,
            'time': self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time),
            'include_block': self.include_block
        }
        if with_hash:
            data['hash'] = self.__hash__
        return data



    @property
    def __hash__(self) -> str:
        return self.calculateHash() if not self.hashTrx else self.hashTrx

    def __str__(self) -> str:
        return f'{str(self.inputs)}{str(self.outputs)}{self.time}'
    
    def __repr__(self) -> str:
        return json.dumps(self.getData(with_hash=True, is_POSIX_timestamp=True))

    def sign(self):
        data = self.__hash__
        sig = Ecdsa.sign(data, pbcoin.wallet.walletKey) # TODO: sign sender
        return sig.toBase64()
