from __future__ import annotations

from typing import Any, Dict, List, NewType, Optional, Tuple
from datetime import datetime
from hashlib import sha256

from pbcoin.constants import SUBSIDY


ALL_COINS_TYPE = NewType("ALL_COINS_TYPE", Dict[str, List["Coin"]])


class Coin:
    """
    Attributes
    ----------
    owner: str
        The Address of the coin owner
    out_index: int
        The index in the transaction in which the coin has been created.
    created_trx_hash: str = ""
        The transaction hash that in which has been created.
    value: int = SUBSIDY
        The value of the coin.
    trx_hash: Optional[str] = None
        The hash of trx in which coin has been spent. (If has been spent)
    in_index: Optional[int] = None
        The index in the transaction in which the coin has been spent. (If has been spent)
    hash_coin: str
        Hash string of this coin (in hex).
    """

    def __init__(
        self,
        owner: str,
        out_index: int,
        created_trx_hash: str = "",
        value: int = SUBSIDY,
        trx_hash: Optional[str] = None,
        in_index: Optional[int] = None,
    ):
        """Initializes attributes except hash"""
        self.owner = owner
        self.value = value
        self.created_trx_hash = created_trx_hash
        self.out_index = out_index
        self.trx_hash = trx_hash
        self.in_index = in_index
        self.hash_coin = self.calculate_hash()

    def make_output(self, recipient_key: str, amount: float) -> Tuple[List[Coin], int]:
        """Makes from this coin an unspent coin for use. in fact,
        converts coin into one or two coins that are one of them
        is used for recipient and the other one is remain for
        the owner it if recipient coin is less than all the first coin

        Parameters
        ----------
        recipient_key: str
            Address of recipient
        amount: float
            Amount values which transfer to recipient address

        returns
        -------
        Tuple[List[coin], int]:
            returns the outputs coin and the value which remain.
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
        """Returns a dictionary from coin data.

        See Also
        --------
        `class Coin` docs"""
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
        return (
            self.created_trx_hash == __o.created_trx_hash
            and self.in_index == __o.in_index
            and self.owner == __o.owner
            and self.value == __o.value
        )

    def __repr__(self) -> str:
        if self.is_spent:
            return (
                f"{self.value} from {self.owner[:8]} "
                f"created in transaction {self.created_trx_hash[:8]} with index {self.in_index} "
                f"was spent in transaction {self.trx_hash[:8]} with index {self.out_index}"
            )
        return (
            f"{self.value} from {self.owner[:8]} "
            f"created in transaction {self.created_trx_hash[:8]} with index {self.in_index} "
            f"and be not spent"
        )

    def calculate_hash(self) -> str:
        """calculate this coin hash sha256 and set the `self.coin_hash`
        then return hex of that.
        """
        cal_hash = sha256(
            (f"{self.value}{self.owner}{self.created_trx_hash}{self.in_index}").encode()
        ).hexdigest()
        self.coin_hash = cal_hash
        return cal_hash

    @property
    def __hash__(self) -> str:
        return self.calculate_hash() if not self.hash_coin else self.hash_coin

    def check_input_coin(self, unspent_coins: ALL_COINS_TYPE) -> bool:
        """Check the coin that is able to spent or not.

        Parameters
        ----------
        unspent_coins: Optional[Dict[str, Coin]] = None
            The coins that have not been spent yet. It's used to check
            the this coin is in it or not.

        Return
        ------
        True if coin is able to spent other wise return False
        """
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

    def spend(self, trx_hash: str, in_index: int):
        """sets the coin has been spent"""
        self.trx_hash = trx_hash
        self.in_index = in_index

    @property
    def is_spent(self):
        return self.trx_hash is not None


class Trx:
    """Transaction class

    Attribute
    ---------
        hash_trx: str
            Trx string of this block (in hex).
        is_generic: bool
            Determines it a base trx. The base trx is the first trx is made by miners
            for their mining rewards.
        include_block: str
            In which block has been mined this transaction? It is a hex of block hash in
            the blockchain in which was mined transaction.
        sender_key: str
            Sender addresses who made this transaction.
        inputs: List[Coin]
            List of coins that the sender provides for recipients. They are unspent coins.
            (to have not spent before yet)
        outputs: List[Coin]:
            The list of coins which their owner could use for sending to others.
        values: int
            The amount of coins which have been sent.
        time: float
            Time which trx is made
    """

    def __init__(
        self,
        include_block_: int,
        sender_key: str,
        inputs: Optional[List[Coin]] = None,
        outputs: Optional[List[Coin]] = None,
        time: Optional[float] = None,
    ) -> None:
        """initializes object attribute based on being necessary"""
        self.time = datetime.utcnow().timestamp() if not time else time
        if inputs is None and outputs is None:
            self.senders = []
            self.recipients = [sender_key]
            self.value = SUBSIDY
            self.hash_trx = self.calculate_hash()
            self.outputs = [Coin(sender_key, 0, self.hash_trx, self.value)]
            self.inputs = []
            self.is_generic = True
        else:
            self.senders = [in_coin.owner for in_coin in inputs]
            self.recipients = [out_coin.owner for out_coin in outputs]
            self.value = sum(coin.value for coin in outputs)
            self.hash_trx = self.calculate_hash()
            self.inputs = inputs  # TODO: check input not to be empty
            for out_coin in outputs:
                out_coin.created_trx_hash = self.hash_trx
            self.outputs = outputs
            self.is_generic = False
        self.public_key = sender_key  # TODO: should be lists
        self.include_block = include_block_

    @staticmethod
    def make_trx(
        owner_coins: List[Coin], sender_key: str, recipient_key: str, value: float
    ) -> Trx:
        """
        Just creates a transaction object from owner coins.

        Args
        ----
        owner_coins: List[Coin]
            A List of coins that a person owns he wants to send.
        sender_key: str
            The public key address of owner the coins and the sender.
        recipient_key: str
            The Public key address of who wants to receive the coins.
        value:
            The amount of coins which want to send.

        Returns
        -------
        Trx
            A Trx object that creates from inputs and outputs coins.
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
        """Sets the output coins of trx to hash of this trx"""
        for i, in_coin in enumerate(self.inputs):
            in_coin.spend(self.hash_trx, i)
        for i, out_coin in enumerate(self.outputs):
            out_coin.created_trx_hash = self.hash_trx
            out_coin.out_index = i

    def calculate_hash(self) -> str:
        """calculate this trx hash sha256 and set the `self.hash_trx`
        then return hex of that.
        """
        cal_hash = sha256(
            (f"{self.senders}{self.recipients}{self.value}{self.time}").encode()
        ).hexdigest()
        self.hash_trx = cal_hash
        return cal_hash

    def get_data(self, with_hash=False, is_POSIX_timestamp=True) -> Dict[str, Any]:
        """Returns a dictionary from coin data.

        Parameters
        ----
        with_hash: bool = False
            Determines puts trx hash or not.
        is_POSIX_timestamp: bool = True
            Determines puts hummable time or not.

        Returns
        -------
            return a dict[str, Any] contains trx data

        See Also
        --------
        `class Trx` docs
        """
        inputs = (
            [in_coin.get_data() for in_coin in self.inputs]
            if not self.is_generic
            else []
        )
        outputs = [out_coin.get_data() for out_coin in self.outputs]
        data = {
            "inputs": inputs,
            "outputs": outputs,
            "value": self.value,
            "time": self.time
            if is_POSIX_timestamp
            else datetime.fromtimestamp(self.time),
            "include_block": self.include_block,
            "hash": self.__hash__,
        }
        if with_hash:
            data["hash"] = self.__hash__
        return data

    def check(self, unspent_coins: Dict[str, Any]) -> bool:
        """Checks this transaction is valid or not"""
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
            if not all(
                [
                    out_coin.created_trx_hash == self.hash_trx
                    for out_coin in self.outputs
                ]
            ):
                return False
        return True

    @property
    def __hash__(self) -> str:
        return self.calculate_hash() if not self.hash_trx else self.hash_trx

    def __str__(self) -> str:
        return f"{str(self.inputs)}{str(self.outputs)}{self.time}"

    def __repr__(self) -> str:
        return f"({self.value} coins from {self.senders} to {self.recipients} on {datetime.fromtimestamp(self.time)})"
