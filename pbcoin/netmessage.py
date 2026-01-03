from __future__ import annotations
from copy import deepcopy

from enum import IntEnum, auto
import json
from typing import Any, Dict, Optional, Union

from pbcoin.logger import getLogger
from pbcoin.utils.netbase import Addr

logging = getLogger(__name__)


class ConnectionCode(IntEnum):
    OK_MESSAGE = auto()  # for ok reply to request
    NEW_NEIGHBOR = auto()  # send information node as a new neighbors
    NEW_NEIGHBORS_REQUEST = auto()  # request some new nodes for neighbors
    NEW_NEIGHBORS_FIND = auto()  # declare find new neighbors ()
    NOT_NEIGHBOR = auto()  # not be neighbors anymore!
    MINED_BLOCK = auto()  # declare other nodes find a new block
    RESOLVE_BLOCKCHAIN = auto()  # for resolving blockchain of 2 nodes
    GET_BLOCKS = auto()  # request for getting some blocks
    # TODO: remove SEND_BLOCKS
    SEND_BLOCKS = auto()  # responds to GET_BLOCKS
    ADD_TRX = auto()  # new trx for add to mempool
    PING_PONG = auto()  # For pinging other nodes and check connection


class Errno(IntEnum):
    BAD_MESSAGE = auto()  # message could not be parsed or isn't standard
    BAD_TYPE_MESSAGE = auto()  # message type is not from ConnectionCode
    BAD_BLOCK_VALIDATION = auto()  # the block(s) that were sended has problem
    BAD_TRANSACTION = auto()  # the transaction(s) that were received has problem
    OBSOLETE_BLOCK = auto()  # A block in a blockchain that is behind other node blockchain


class Message:
    """A Message class that contains network message data and information

    Attributes
    ----------
    status: bool
        Determines this message is an OK message or a fail message.
    type_: Union[ConnectionCode, Errno]
        This message sends for what things.
    addr: Addr
        The sender's ip and port
    data: Dict[str, Any]
        The extra(actual) data that this type_ of message needs
    """
    status: bool
    type_: Union[ConnectionCode, Errno]
    addr: Addr
    data: Optional[Dict[str, Any]]

    def __init__(self,
                 status: bool,
                 type_: Union[ConnectionCode, Errno],
                 addr: Addr,
                 data: Optional[Dict[str, Any]] = None):
        """Initialize object attribute

        See Also
        --------
        `Message` docs
        """
        self.status = status
        self.type_ = type_
        self.addr = addr
        self.data = data

    def create_message(self, my_addr: Addr) -> str:
        """Gathers info and makes a JSON object and converts it to a bytes array"""
        base_data = {
            "status": self.status,
            "type": self.type_,
            "dst_addr": self.addr.hostname,
            "src_addr": my_addr.hostname,
            "pub_key": my_addr.pub_key,
            "data": self.data
        }
        return json.dumps(base_data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Message:
        """Parse the message from a dict/JSON message"""
        copy_data = deepcopy(data)
        src_addr = Addr.from_hostname(copy_data["src_addr"])
        src_addr.pub_key = copy_data["pub_key"]
        status = copy_data["status"]
        if status is True:
            type = ConnectionCode(copy_data["type"])
        else:
            type = Errno(copy_data["type"])
        new_message = Message(status, type, src_addr)
        extra_data = copy_data.get("data", None)
        if extra_data is None:
            return new_message
        return new_message.create_data(**extra_data)

    @staticmethod
    def from_str(data: str) -> Message:
        return Message.from_dict(json.loads(data))

    def create_data(self, **kwargs):
        """Sets and checks extra data that is different for every code message"""
        try:
            if not self.status:
                if self.type_ == Errno.BAD_MESSAGE:
                    self.data = None
                    pass
                elif self.type_ == Errno.BAD_BLOCK_VALIDATION:
                    self.data = {
                        "block_hash": kwargs["block_hash"],
                        "block_index": kwargs["block_index"],
                        "validation": kwargs["validation"]
                    }
            elif self.type_ == ConnectionCode.NEW_NEIGHBOR:
                self.data = {
                    "new_node": kwargs["new_node"],
                    "new_pub_key": kwargs["new_pub_key"]
                }
            elif self.type_ == ConnectionCode.NEW_NEIGHBORS_REQUEST:
                self.data = {
                    # how many neighbors you want
                    "n_connections": kwargs["n_connections"],
                    # nodes that are util found
                    "p2p_nodes": kwargs["p2p_nodes"],
                    # this request passes from what nodes for searching
                    "passed_nodes": kwargs["passed_nodes"]
                }
            elif self.type_ == ConnectionCode.NEW_NEIGHBORS_FIND:
                self.data = {
                    "n_connections": kwargs["n_connections"],
                    "p2p_nodes": kwargs["p2p_nodes"],
                    "passed_nodes": kwargs["passed_nodes"],
                    "for_node": kwargs["for_node"]

                }
            elif self.type_ == ConnectionCode.NOT_NEIGHBOR:
                self.data = {
                    "node_hostname": kwargs["node_hostname"],
                    "pub_key": kwargs["pub_key"]
                }
            elif self.type_ == ConnectionCode.MINED_BLOCK:
                self.data = {"block": kwargs["block"]}
            elif self.type_ == ConnectionCode.RESOLVE_BLOCKCHAIN:
                self.data = {"blocks": kwargs["blocks"]}
            elif self.type_ == ConnectionCode.GET_BLOCKS:
                hash_block = kwargs.get("hash_block", None)
                if hash_block is not None:
                    self.data = {"hash_block": hash_block}
                else:
                    self.data = {"first_index": kwargs["first_index"]}
            elif self.type_ == ConnectionCode.SEND_BLOCKS:
                self.data = {"blocks": kwargs["blocks"]}
            elif self.type_ == ConnectionCode.ADD_TRX:
                self.data = {"trx": kwargs["trx"],
                             "signature": kwargs["signature"],
                             "public_key": kwargs["public_key"],
                             "passed_nodes": kwargs["passed_nodes"]}
            elif self.type_ == ConnectionCode.PING_PONG:
                self.data = None
        except KeyError:
            logging.error("Bad kwargs for creating message data")
        return self

    def copy(self) -> Message:
        """Copies the message and returns that"""
        return deepcopy(self)
