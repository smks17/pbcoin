from datetime import datetime
from hashlib import sha512

import pbcoin

DEFAULT_SUBSIDY = 50

class Coin:
    nCoins = 0
    def __init__(self, _owner: str, _value = DEFAULT_SUBSIDY):
        self.owner = _owner
        self.value = _value

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
            outputs.append(Coin(self.owner, remain))
            outputs.append(Coin(recipient_key, value))
        else:
            outputs.append(Coin(recipient_key, self.value))

        return outputs, remain

    def getData(self):
        return {
            "value": self.value,
            "owner": self.owner
        }

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
            self.outputs = [Coin(pbcoin.wallet.walletKey.compressedPublic)]
            self.value = DEFAULT_SUBSIDY
            self.is_generic = True
            self.inputs = []
            self.hashTrx = self.calculateHash()
        else:
            self.time = datetime.utcnow().timestamp()
            self.inputs = _inputs
            self.outputs = _outputs
            self.value = sum(coin.value for coin in self.outputs)
            self.is_generic = False
            self.hashTrx = self.calculateHash()
        self.include_block = include_block

    @staticmethod
    def makeTrx(self,owner_coins: list[Coin], sender_key: str, recipient_key: str, value: float):
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
        return Trx(outputs, inputs)

    def calculateHash(self):
        calHash = sha512(self.__str__().encode()).hexdigest()
        self.blockHash = calHash
        return calHash

    def getData(self, with_hash = False, is_POSIX_timestamp = True):
        data = {
            'inputs': [in_coin.getData() for in_coin in self.inputs] if self.is_generic else [],
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
        return f'{self.inputs}{self.outputs}{self.value}{self.time}'
    
    def __repr__(self) -> str:
        return self.getData(with_hash=True, is_POSIX_timestamp=False)
