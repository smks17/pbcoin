from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from enum import IntEnum, auto
from sys import getsizeof
from typing import (
    Any,
    Dict,
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

    def __str__(self) -> str:
        if self.pub_key is None:
            return self.hostname
        return self.hostname + ":" + self.pub_key
    
    def __hash__(self) -> int:
        return hash(self.__str__())


class Connection:
    def __init__(self, addr: Addr, timeout: Optional[float] = TIMEOUT):
        self.addr = addr
        if not self.addr:
            self.addr = Addr(ip=conf.settings.network.ip, port=conf.settings.network.port, pub_key=None)
        self.timeout = timeout
    
    async def connect_to(self, dst_addr: Addr) -> PeerHandler:
        """make a connection to destination addr and return stream reader and writer"""
        try:
            fut = asyncio.open_connection(dst_addr.ip, str(dst_addr.port))
            logging.debug(f"from {self.addr.hostname} Connect to {dst_addr.hostname}")
            reader, writer = await asyncio.wait_for(fut, timeout=self.timeout)
            peer_handler = PeerHandler(addr=dst_addr,
                                    writer=writer,
                                    reader=reader,
                                    is_connected=True)
        except asyncio.TimeoutError:
            logging.debug(f"Timeout Error connect to {dst_addr}")
            return None
        except ConnectionError:
            logging.error(f"Connection Error to {dst_addr}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"Error", exc_info=True)
            return None
        return peer_handler

    async def connect_and_send(self,
                               dst_addr: Addr,
                               data: str,
                               wait_for_receive=True
    ) -> Optional[bytes]:
        """make a connection to destination addr and send data then if wait_for_receive
        is True wait to recieve data from destination and return data"""
        rec_data = b''
        # try to connect
        peer_handler = await self.connect_to(dst_addr)
        if peer_handler is None:
            return None
        # write the data
        err = await self.write(peer_handler.writer, data, peer_handler.addr)
        if err is not None:
            return None
        # get the message
        if wait_for_receive:
            rec_data = await self.read(peer_handler.reader, peer_handler.addr)
            if rec_data is None:
                return None
            logging.debug(
                f'receive data from {dst_addr.hostname} {rec_data.decode()}')
            await self.disconnected_from(f"{dst_addr.hostname}")
        return rec_data

    async def disconnected_from(self, addr: Addr, wait_to_close=True):
        # TODO: I think this method is not unnecessary
        peer_handler = self.connected.pop(addr.hostname)
        peer_handler.disconnect(wait_to_close)

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

    def close(self):
        """close listening and close all handler tasks"""
        if self.is_listening:
            self.server.close()
            self.is_listening = False


@dataclass
class PeerHandler:
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
        if self.addr is None and self.writer is not None:
            ip, port = writer.get_extra_info('peername')
            self.addr = Addr(ip=ip, port=port)
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
    dst_addr: Addr
    data: Dict[str, Any]

    def __init__(self,
                 status: bool,
                 type_: Union[ConnectionCode, Errno],
                 dst_addr: Addr,
                 data: Dict[str, Any]
    ):
        self.status = status
        self.type_ = type_
        self.dst_addr = dst_addr
        self.data = data

    def create_message(self, pub_key: str):
        base_data = {
            "status": self.status,
            "type": self.type_,
            "dst_addr": self.dst_addr.hostname,
            "pub_key": pub_key
        }
        return json.dumps(base_data | self.data)
