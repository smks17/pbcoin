from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple
)
from datetime import datetime
from hashlib import sha256

from pbcoin.constants import SUBSIDY


class Coin:
    def __init__(self,
                 owner: str,
                 out_index: int,
                 created_trx_hash: str = "",
                 value=SUBSIDY,
                 trx_hash: Optional[str]=None,
                 in_index: Optional[int]=None):
        self.owner = owner
        self.value = value
        self.created_trx_hash = created_trx_hash
        self.out_index = out_index
        self.trx_hash = trx_hash
        self.in_index = in_index
        self.hash_coin = self.calculate_hash()

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
            outputs.append(Coin(self.owner, len(outputs), value=remain))
            outputs.append(Coin(recipient_key, len(outputs), value=amount))
        else:
            outputs.append(Coin(recipient_key, len(outputs), value=amount))

        return outputs, remain

    def get_data(self) -> Dict[str, Any]:
        """
        return a dictionary that contains:
        - hash: calculated of coin hash
        - value: the amount of this coin
        - owner: who is (or was) this coin for
        - created_trx_hash: was created in which transaction
        - out_index: index of transaction in the block that was created
        and if the coin was spent in addition:
        - trx_hash: the hash of trx which spent in
        - in_index: index of transaction in the block that was spent
        """
        data = {
            "hash": self.__hash__,
            "value": self.value,
            "owner": self.owner,
            "created_trx_hash": self.created_trx_hash,
            "out_index": self.out_index,
        }
        if self.is_spent:
            data.update({"trx_hash": self.trx_hash, "in_index": self.in_index})
        return data

    def __eq__(self, __o: object) -> bool:
        return (self.created_trx_hash == __o.created_trx_hash and
                self.in_index == __o.in_index and
                self.owner == __o.owner and
                self.value == __o.value)

    def __repr__(self) -> str:
        if self.is_spent:
            return f"{self.value} from {self.owner[:8]} "  \
                f"created in transaction {self.created_trx_hash[:8]} with index {self.in_index} "  \
                f"was spent in transaction {self.trx_hash[:8]} with index {self.out_index}"
        return f"{self.value} from {self.owner[:8]} "  \
                f"created in transaction {self.created_trx_hash[:8]} with index {self.in_index} "  \
                f"and be not spent"

    def calculate_hash(self) -> str:
        """calculate this trx hash and return hex hash"""
        cal_hash = sha256(
            (f"{self.value}{self.owner}{self.created_trx_hash}{self.in_index}").encode()
        ).hexdigest()
        self.coin_hash = cal_hash
        return cal_hash

    @property
    def __hash__(self) -> str:
        return self.calculate_hash() if not self.hash_coin else self.hash_coin

    def check_input_coin(self, unspent_coins: dict[str, Coin]) -> bool:
        trx_hash = self.created_trx_hash
        my_unspent = unspent_coins.get(trx_hash, None)
        if my_unspent is not None:
            owner_coin = my_unspent[self.out_index]
            if owner_coin.owner == self.owner:
                return True
            else:
                return False
        else:
            return False

    def spend(self, trx_hash, index):
        self.trx_hash = trx_hash
        self.in_index = index

    @property
    def is_spent(self):
        return self.trx_hash is not None


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
        if inputs_ is None and outputs_ is None:
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
                out_coin.created_trx_hash = self.hash_trx
            self.outputs = outputs_
            self.is_generic = False
        self.public_key = sender_key  # TODO: should be lists
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
                coin_output, remain_coin = coin.make_output(recipient_key, remain)
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
        for i, in_coin in enumerate(self.inputs):
            in_coin.spend(self.hash_trx, i)
        for i, out_coin in enumerate(self.outputs):
            out_coin.created_trx_hash = self.hash_trx
            out_coin.out_index = i

    def calculate_hash(self) -> str:
        """calculate this trx hash and return hex hash"""
        cal_hash = sha256(
            (f"{self.senders}{self.recipients}{self.value}{self.time}").encode()
        ).hexdigest()
        self.hash_trx = cal_hash
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
        inputs = [in_coin.get_data() for in_coin in self.inputs] if not self.is_generic else []
        outputs = [out_coin.get_data() for out_coin in self.outputs]
        data = {
            'inputs': inputs,
            'outputs': outputs,
            'value': self.value,
            'time': self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time),
            'include_block': self.include_block,
        }
        if with_hash:
            data['hash'] = self.__hash__
        return data

    def check(self, unspent_coins) -> bool:
        for index, coin in enumerate(self.inputs):
            # is input coin trx valid
            if coin is not None and not coin.check_input_coin(unspent_coins):
                return False
            # check equal input and output value
            output_value = sum(out_coin.value for out_coin in self.outputs)
            input_value = sum(in_coin.value for in_coin in self.inputs)
            if output_value != input_value:
                return False
            # check valid time
            if self.time <= datetime(2022, 1, 1).timestamp():
                return False
            # check trx hash output coin
            if not all([out_coin.created_trx_hash == self.hash_trx for out_coin in self.outputs]):
                return False
        return True

    @property
    def __hash__(self) -> str:
        return self.calculate_hash() if not self.hash_trx else self.hash_trx

    def __str__(self) -> str:
        return f'{str(self.inputs)}{str(self.outputs)}{self.time}'

    def __repr__(self) -> str:
        return f'({str(self.inputs)}->{str(self.outputs)} on {datetime.fromtimestamp(self.time)})'
