"""The net base module to use for network in pbcoin"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from sys import getsizeof
from typing import (
    List,
    NewType,
    Optional,
    Union
)

import pbcoin.config as conf
from pbcoin.constants import NETWORK_DATA_SIZE
from pbcoin.logger import getLogger


logging = getLogger(__name__)

AsyncWriter = NewType("AsyncWriter", asyncio.StreamWriter)
AsyncReader = NewType("AsyncReader", asyncio.StreamReader)


@dataclass
class Addr:
    """Basic structure network address

    Attributes
    ----------
    ip: str
        A ip version 4
    port: int

    pub_key: Optional[str]
        Its address key
    """
    ip: str
    port: int
    pub_key: Optional[str] = None

    @staticmethod
    def from_hostname(hostname: str, pub_key=None):
        """Creates Addr object from a hostname str. (eg "127.0.0.1:8989")"""
        ip, port = hostname.split(":")
        return Addr(ip=ip, port=int(port), pub_key=pub_key)

    @property
    def hostname(self) -> str:
        """A string hostname of ip and port in shape "<ip>:<port>".
        (eg "127.0.0.1:8989")
        """
        return f"{self.ip}:{self.port}"

    @staticmethod
    def convert_to_addr_list(addr_list: List[str]):
        """A helper function to convert a list of hostname to list of Addr object"""
        return list(map(Addr.from_hostname, addr_list))

    def __str__(self) -> str:
        if self.pub_key is None:
            return self.hostname
        return self.hostname + ":" + self.pub_key

    def __hash__(self) -> int:
        return hash(self.__str__())

    def __eq__(self, __o: "Addr") -> bool:
        return (self.ip == __o.ip and self.port == __o.port and self.pub_key == __o.pub_key)


class Connection:
    """The base network class that is used for connecting other peer or nodes.

    Attributes
    ----------
    addr: Addr
        The itself network address for connection and listening.
    """
    def __init__(self, addr: Addr, timeout: Optional[float] = None):
        self.addr = addr
        if not self.addr:
            self.addr = Addr(ip=conf.settings.network.ip,
                             port=conf.settings.network.port,
                             pub_key=None)
        self.timeout = timeout

    async def connect_to(self, dst_addr: Addr) -> Optional[Peer]:
        """(async) Makes a connection to destination address.

        Parameters
        ----------
        dst_addr: Addr
            The destination address that wants to be connected to.
        Return
        ------
        Optional[Peer]
            A Peer object with connection. If making connection is not successfully
            returns None.
        """
        try:
            # TODO: add timeout
            reader, writer = await asyncio.open_connection(dst_addr.ip, dst_addr.port)
            logging.debug(f"from {self.addr.hostname} Connect to {dst_addr.hostname}")
            peer = Peer(addr=dst_addr,
                        writer=writer,
                        reader=reader,
                        is_connected=True)
        except asyncio.TimeoutError:
            logging.debug(f"Timeout Error connect to {dst_addr}")
            return None
        except (ConnectionError, OSError):
            logging.error(f"Connection Error to {dst_addr}", exc_info=True)
            return None
        except Exception as e:
            raise e
        return peer

    async def connect_and_send(self,
                               dst_addr: Addr,
                               data: str,
                               wait_for_receive=True) -> Optional[bytes]:
        """(async) Makes a connection to the destination address and sends data. Then if
        it is necessary wait to receive data from that and return the data

        Parameters
        ----------
        dst_addr: Addr
            The destination address that wants to be connected to.
        data: str
            The data that wants to be sended to destination.
        wait_for_receive: bool = True
            Determines wait to receives and reads data from destination or not.

        Returns
        -------
        Optional[bytes]
            If wait_for_receive is True, then return the data received.
            Otherwise return nothing
        """
        rec_data = b''
        # try to connect
        peer = await self.connect_to(dst_addr)
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
                f'receive data from {dst_addr.hostname} {rec_data.decode()}')
        return rec_data

    async def write(self,
                    writer: asyncio.StreamWriter,
                    data: Union[str, bytes],
                    addr: Optional[Addr] = None,
                    flush: bool = True) -> Optional[Exception]:
        """(async) Writes the data from writer stream to the destination.

        Parameters
        ----------
        writer: asyncio.StreamWriter
            A stream writer for writing in it and sending data to the destination.
        data: Union[str, bytes]
            The data that wants to be sent to the destination.
        addr: Optional[Addr] = None
            The destination address to which the data wants to be sent.
        flush: bool = True
            Determines to wait to flush the write buffer stream.

        Returns
        -------
        Optional[Exception]
            If it will be successful then return None, otherwise return Error.

        TODO:: returns Exception(Error) is a bad idea. should be replaced ASA.
        """
        if writer is None:
            return Exception("Pass a non writable handler")

        def sizeof(input_data):
            return '{:>08d}'.format(getsizeof(input_data)).encode()

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
                logging.error("Could not write message", exc_info=True)
            return e
        return None

    async def read(self, reader: asyncio.StreamReader, addr: Optional[Addr] = None) -> Optional[bytes]:
        """(async) Writes the data from writer stream from the destination.

        Parameters
        ----------
        reader: asyncio.StreamReader
            A stream reader for reading from it and receiving data from the destination.
        addr: Optional[Addr] = None
            The destination address from which the data wants to be received.

        Returns
        -------
        Optional[bytes]
            If it will be successful then return the received data in bytes type,
            otherwise return empty bytes.
        """
        if reader is None:
            return None
        data = b''
        try:
            size_data = await reader.read(NETWORK_DATA_SIZE)
            size_data = int(size_data)
            data = await reader.read(size_data)
        except Exception:
            if addr is not None:
                logging.error(f"Could not read message from {addr}", exc_info=True)
            else:
                logging.error("Could not read message", exc_info=True)
            return data
        return data


@dataclass
class Peer:
    """To keep information connected peer"""
    addr: Addr
    writer: asyncio.StreamWriter
    reader: asyncio.StreamReader
    is_connected: bool

    def __init__(self,
                 addr: Addr,
                 writer: asyncio.StreamWriter,
                 reader: asyncio.StreamReader,
                 is_connected: bool = True):
        self.addr = addr
        self.writer = writer
        self.reader = reader
        self.is_connected = is_connected

    async def disconnect(self, wait_to_close: bool):
        if self.writer is not None and not self.writer.is_closing():
            self.writer.close()
            if wait_to_close:
                await self.writer.wait_closed()
            self.is_connected = True
