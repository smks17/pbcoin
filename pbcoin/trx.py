from datetime import datetime
from hashlib import sha512
import json

import pbcoin

DEFAULT_SUBSIDY = 50

class Trx:
    sender: str
    recipient: str
    amount: float
    time: float
    hashTrx: str
    def __init__(self, **kwargs):
        if len(kwargs) == 0:
            # this is subsidy trx
            self.sender = ""
            self.recipient = pbcoin.addrKey.compressedPublic # TODO: get address key
            self.amount = DEFAULT_SUBSIDY
            self.time = datetime.utcnow().timestamp()
        elif len(kwargs) >= 3:
            self.sender = kwargs['sender']
            self.recipient = kwargs['recipient']
            self.amount = kwargs['amount']
            if not kwargs.get('time'):
                self.time = kwargs['time']
            else:
                self.time = datetime.utcnow().timestamp()
        else:
            assert (False, "Bad usage")

        self.hashTrx = self.__hash__
    
    def calculateHash(self):
        calHash = sha512(self.__str__()).hexdigest()
        self.blockHash = calHash
        return calHash

    def getData(self, with_hash = False, is_POSIX_timestamp = True):
        data = {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'time': self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time)
        }
        if with_hash:
            data['hash'] = self.hashTrx
        return data

    @property
    def __hash__(self) -> str:
        return sha512(self.__str__().encode()).hexdigest()

    def __str__(self) -> str:
        return f'{self.sender}{self.recipient}{self.amount}{self.time}'
    
    def __repr__(self) -> str:
        return self.getData(with_hash=True, is_POSIX_timestamp=False)