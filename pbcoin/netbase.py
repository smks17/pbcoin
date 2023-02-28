from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum, auto
from sys import getsizeof
from typing import (
    Any,
    Dict,
    List,
    NewType,
    Optional,
    Union
)

import pbcoin.config as conf
from pbcoin.constants import NETWORK_DATA_SIZE, TIMEOUT
from pbcoin.logger import getLogger

logging = getLogger(__name__)

AsyncWriter = NewType("AsyncWriter", asyncio.StreamWriter)
AsyncReader = NewType("AsyncReader", asyncio.StreamReader)


class ConnectionCode(IntEnum):
    NEW_NEIGHBOR = auto()  # send information node as a new neighbors
    NEW_NEIGHBORS_REQUEST = auto()  # request some new nodes for neighbors
    NEW_NEIGHBORS_FIND = auto()  # declare find new neighbors ()
    NOT_NEIGHBOR = auto()  # not be neighbors anymore!
    MINED_BLOCK = auto()  # declare other nodes find a new block
    RESOLVE_BLOCKCHAIN = auto()  # for resolving blockchain of 2 nodes
    GET_BLOCKS = auto()  # request for get some blocks
    SEND_BLOCKS = auto()  # responds to GET_BLOCKS
    ADD_TRX = auto()  # new trx for add to mempool
    PING = auto()  # For pinging other nodes and check connection

class Errno(IntEnum):
    BAD_MESSAGE = auto()  # message could not be parsed or isn't standard
    BAD_TYPE_MESSAGE = auto()  # message type is not from ConnectionCode
    BAD_BLOCK_VALIDATION = auto()  # the block(s) that were sended has problem
    # TODO: Not implemented
    NOT_FOUND_IP_AS_NEIGHBORS = auto()  # sender is not my neighbors (for some messages)
    # TODO: Not implemented
    BAD_TRANSACTION = auto()  # the transaction(s) that were received has problem 


@dataclass
class Addr:
    ip: str
    port: int
    pub_key: Optional[str] = None

    @staticmethod
    def from_hostname(hostname: str, pub_key=None):
        ip, port = hostname.split(":")
        return Addr(ip=ip, port=int(port), pub_key=pub_key)
    
    @property
    def hostname(self): return f"{self.ip}:{self.port}"

    @staticmethod
    def convert_to_addr_list(l: List[str]):
        return list(map(Addr.from_hostname, l))
    
    def __str__(self) -> str:
        if self.pub_key is None:
            return self.hostname
        return self.hostname + ":" + self.pub_key
    
    def __hash__(self) -> int:
        return hash(self.__str__())


class Connection:
    def __init__(self, addr: Addr, timeout: Optional[float] = None):
        self.addr = addr
        if not self.addr:
            self.addr = Addr(ip=conf.settings.network.ip, port=conf.settings.network.port, pub_key=None)
        self.timeout = timeout
    
    async def connect_to(self, src_addr: Addr) -> Peer:
        """make a connection to destination addr and return stream reader and writer"""
        try:
            fut = asyncio.open_connection(src_addr.ip, src_addr.port)
            logging.debug(f"from {self.addr.hostname} Connect to {src_addr.hostname}")
            reader, writer = await asyncio.wait_for(fut, timeout=self.timeout)
            peer = Peer(addr=src_addr,
                                    writer=writer,
                                    reader=reader,
                                    is_connected=True)
        except asyncio.TimeoutError:
            logging.debug(f"Timeout Error connect to {src_addr}")
            return None
        except ConnectionError as e:
            logging.error(f"Connection Error to {src_addr}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"Error", exc_info=True)
            return None
        return peer

    async def connect_and_send(self,
                               src_addr: Addr,
                               data: str,
                               wait_for_receive=True
    ) -> Optional[bytes]:
        """make a connection to destination addr and send data then if wait_for_receive
        is True wait to recieve data from destination and return data"""
        rec_data = b''
        # try to connect
        peer = await self.connect_to(src_addr)
        if peer is None:
            return None
        # write the data
        err = await self.write(peer.writer, data, peer.addr)
        if err is not None:
            return None
        # get the message
        if wait_for_receive:
            rec_data = await self.read(peer.reader, peer.addr)
            if rec_data is None:
                return None
            logging.debug(
                f'receive data from {src_addr.hostname} {rec_data.decode()}')
            # await self.disconnected_from(f"{src_addr.hostname}")
        return rec_data

    async def disconnected_from(self, addr: Addr, wait_to_close=True):
        # TODO: I think this method is not unnecessary
        peer = self.connected.pop(addr.hostname)
        peer.disconnect(wait_to_close)

    async def write(self,
                    writer: AsyncWriter,
                    data: Union[str, bytes],
                    addr: Optional[Addr] = None,
                    flush: bool = True
    ) -> Optional[Exception]:
        """write data from writer to destination and if successfully return true
        otherwise return False
        """
        if writer is None : return Exception("Pass a non writable handler")
        sizeof = lambda input_data : '{:>08d}'.format(getsizeof(input_data)).encode()
               
        if isinstance(data, str):
            data = data.encode()
        try:
            writer.write(sizeof(data))
            writer.write(data)
            if flush:
                await writer.drain()
        except Exception as e:
            if addr is None:
                logging.error(f"Could not write message to {addr}", exc_info=True)
            else:
                logging.error(f"Could not write message", exc_info=True)
            return e
        return None

    async def read(self, reader: AsyncReader, addr: Optional[Addr] = None) -> Optional[bytes]:
        """read data from reader if successfully return the data in bytes type
        otherwise return empty bytes
        """
        if reader is None : return None
        data = b''
        try:
            size_data = await reader.read(NETWORK_DATA_SIZE)
            size_data = int(size_data)
            data = await reader.read(size_data)
        except Exception as e:
            if addr is not None:
                logging.error(f"Could not read message from {addr}", exc_info=True)
            else:
                logging.error(f"Could not read message", exc_info=True)
            return data
        return data

    # TODO: implement reset and close without waiting
    async def reset(self, close=True):
        """delete its neighbors and close the listening too"""
        self.neighbors = dict()
        if close:
            self.close()
        for task in self.tasks:
            await task.close()
        self.tasks = []


@dataclass
class Peer:
    addr: Addr
    writer: Optional[AsyncWriter]
    reader: Optional[AsyncReader]
    last_error: Optional[Errno]
    is_connected: bool

    def __init__(self,
                 addr: Optional[Addr] = None,
                 writer: Optional[AsyncWriter] = None,
                 reader: Optional[AsyncReader] = None,
                 last_error: Optional[Errno] = None,
                 is_connected: bool = True
    ):
        self.addr = addr
        self.writer = writer
        self.reader = reader
        self.last_error = last_error
        self.is_connected = is_connected

    async def disconnect(self, wait_to_close: bool):
        if self.writer is not None and not self.writer.is_closing():
            self.writer.close()
            if wait_to_close:
                await self.writer.wait_closed()
            self.is_connected = True


class Message:
    status: bool
    type_: Union[ConnectionCode, Errno]
    addr: Addr
    data: Dict[str, Any]

    def __init__(self,
                 status: bool,
                 type_: Union[ConnectionCode, Errno],
                 addr: Addr,
                 data: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.type_ = type_
        self.addr = addr
        self.data = data

    def create_message(self, my_addr: Addr):
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
        try:
            copy_data = deepcopy(data)
            src_addr = Addr.from_hostname(copy_data["src_addr"])
            src_addr.pub_key = copy_data["pub_key"]
            new_message = Message(copy_data["status"],
                                  copy_data["type"],
                                  src_addr)
            extra_data = copy_data.get("data", None)
            if extra_data is None:
                return new_message
            return new_message.create_data(**extra_data)
        except KeyError as e:
            logging.debug("Bad key for parsing data message", exec_info = True)
            raise e

    @staticmethod
    def from_str(data: str) -> Message:
        try:
            return Message.from_dict(json.loads(data))
        except KeyError as e:
            logging.debug("Bad key for parsing data message", exec_info = True)
            raise e
            
    def create_data(self, **kwargs):
        try:
            if self.type_ == ConnectionCode.NEW_NEIGHBOR:
                self.data = {
                    "new_node": kwargs["new_node"],
                    "new_pub_key": kwargs["new_pub_key"]
                }
            elif self.type_ == ConnectionCode.NEW_NEIGHBORS_REQUEST:
                self.data = {
                    "n_connections": kwargs["n_connections"],  # how many neighbors you want
                    "p2p_nodes": kwargs["p2p_nodes"],  # nodes that are util found
                    "passed_nodes": kwargs["passed_nodes"] # this request passes from what nodes for searching
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
            elif self.type_ == ConnectionCode.PING:
                self.data = None
        except KeyError as e:
            logging.error("Bad kwargs for creating message data", exec_info = True)
        return self

    def copy(self) -> Message:
        return deepcopy(self)

