from __future__ import annotations

import json
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple
)
from datetime import datetime
from hashlib import sha512

from .constants import SUBSIDY


class Coin:
    def __init__(self, owner_: str, index_: int, trx_hash_: str = "", value_=SUBSIDY):
        self.owner = owner_
        self.value = value_
        self.trx_hash = trx_hash_
        self.index = index_

    def make_output(self, recipient_key: str, amount: float) -> Tuple[bool, int]:
        """
            makes from this coin an unspent coin for use. in fact,
            converts coin into one or two coins that are one of them
            is used for recipient and the other one is remain for
            the owner it if recipient coin is less than all the first coin

            args
            ----
            recipient_key: str
                address key of recipient
            amount: float
                amount which transfer to recipient wallet

            return
            ------
            Tuple[Coin]:
                return the outputs coin
        """
        outputs = []
        remain = self.value - amount
        if remain > 0:
            outputs.append(Coin(self.owner, len(outputs), value_=remain))
            outputs.append(Coin(recipient_key, len(outputs), value_=amount))
        else:
            outputs.append(Coin(recipient_key, len(outputs), value_=amount))

        return outputs, remain

    def get_data(self) -> Dict[str, Any]:
        """
        return a dictionary that contains:
        - value: the amount of this coin
        - owner: who is (or was) this coin for
        - trx_hash: exists in which transaction
        - index: index of transaction in the block that contains this transaction
        """
        return {
            "value": self.value,
            "owner": self.owner,
            "trx_hash": self.trx_hash,
            "index": self.index
        }

    def __eq__(self, __o: object) -> bool:
        return (self.trx_hash == __o.trx_hash
            and self.index == __o.index
            and self.owner == __o.owner
            and self.value == __o.value)

    def __repr__(self) -> str:
        return f"{self.value} from {self.owner[:8]} in transaction {self.trx_hash[:8]} with index {self.index}"

    def check_input_coin(self, unspent_coins: dict[str, Coin]) -> bool:
        trx_hash_ = self.trx_hash
        my_unspent = unspent_coins.get(trx_hash_, None)
        if my_unspent is not None:
            owner_coin = my_unspent[self.index]
            if owner_coin.owner == self.owner:
                return True
            else:
                return False
        else:
            return False

class Trx:
    """Transaction class

        Attribute
        ---------
            inputs: List[Coin]
                list of coins to send to recipients. there are another unspent
                coin (output coin) in a before trx
            outputs: List[Coin]:
                The coins which their owner could use for sending to others
                (if are mined)
            time: float
                time that is make trx
            hash_trx: str
                trx hash for put it in block
            is_generic: bool
                is it a base coin or not? the base coin is the first coin
                is made by miners for its mining reward
            include_block: str
                in which block is this trx was mined? it is a hex hash of a block
                in blockchain which was mined transaction in
            sender_key: str
                Public key who make this transaction
    """

    def __init__(
        self,
        include_block_: int,
        sender_key: str,
        inputs_: Optional[List[Coin]] = None,
        outputs_: Optional[List[Coin]] = None,
        time_: Optional[float] = None, 
    ) -> None:
        self.time = datetime.utcnow().timestamp() if not time_ else time_
        if inputs_ == None and outputs_ == None:
            self.senders = []
            self.recipients = [sender_key]
            self.value = SUBSIDY
            self.hash_trx = self.calculate_hash()
            self.outputs = [Coin(sender_key, 0, self.hash_trx, self.value)]
            self.inputs = []
            self.is_generic = True
        else:
            self.senders = [in_coin.owner for in_coin in inputs_]
            self.recipients = [out_coin.owner for out_coin in outputs_]
            self.value = sum(coin.value for coin in outputs_)
            self.hash_trx = self.calculate_hash()
            self.inputs = inputs_  # TODO: check input not to be empty
            for out_coin in outputs_:
                out_coin.trx_hash = self.hash_trx
            self.outputs = outputs_
            self.is_generic = False
        self.public_key = sender_key # TODO: should be lists
        self.include_block = include_block_

    @staticmethod
    def make_trx(
        owner_coins: List[Coin],
        sender_key: str,
        recipient_key: str,
        value: float
    ) -> Trx:
        """
        create a transaction from sender coins

        Args
        ----
        owner_coins: List[Coin]
            a List of sender's coin
        sender_key: str
            public key of sender
        recipient_key: str
            the public key of who want sends to
        value:
            amount of send

        Returns
        -------
            return a object of Trx class
        """
        # TODO: change sender key to List of sender key
        remain = value
        outputs = []
        inputs = []
        for coin in owner_coins:
            if coin.owner == sender_key:
                inputs.append(coin)
                coin_output, remain_coin = coin.make_output(
                    recipient_key, remain)
                if remain_coin <= 0:
                    remain -= coin.value
                else:
                    remain -= value
                outputs += coin_output
                if remain == 0:
                    break

        if remain != 0:
            return None
        trx = Trx(0, sender_key, inputs, outputs)
        trx.set_hash_coins()
        return trx

    def set_hash_coins(self):
        """set the output coins of trx to hash of this trx"""
        for out_coin in self.outputs:
            out_coin.trx_hash = self.hash_trx

    def calculate_hash(self) -> str:
        """calculate this trx hash and return hex hash"""
        cal_hash = sha512(
            (f"{self.senders}{self.recipients}{self.value}{self.time}").encode()
        ).hexdigest()
        self.block_hash = cal_hash
        return cal_hash

    def get_data(self, with_hash=False, is_POSIX_timestamp=True) -> Dict[str, Any]:
        """
        get transaction data that has:
            - inputs: the input coins
            - output: the output coins
            - value: amount of coins are sended
            - time: the time is create this trx
            - include_block: this trx is in which block in blockchain
            - hash: if with_hash is True, then put trx hash too

        Args
        ----
            with_hash: bool = False
                if True put trx hash too
            is_POSIX_timestamp: bool = True
                if not True then put hummable time

        Returns
        -------
            return a dict[str, Any] contains trx data
        """
        data = {
            'inputs': [in_coin.get_data() for in_coin in self.inputs] if not self.is_generic else [],
            'outputs': [out_coin.get_data() for out_coin in self.outputs],
            'value': self.value,
            'time': self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time),
            'include_block': self.include_block,
        }
        if with_hash:
            data['hash'] = self.__hash__
        return data

    @property
    def __hash__(self) -> str:
        return self.calculate_hash() if not self.hash_trx else self.hash_trx

    def __str__(self) -> str:
        return f'{str(self.inputs)}{str(self.outputs)}{self.time}'

    def __repr__(self) -> str:
        return f'({str(self.inputs)}->{str(self.outputs)} on {datetime.fromtimestamp(self.time)})'
