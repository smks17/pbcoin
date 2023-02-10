# TODO: net.py will be replaced by this module

from __future__ import annotations

import asyncio
import json
from typing import Dict, Tuple

import pbcoin.config as conf
from pbcoin.logger import getLogger
from pbcoin.netbase import (
    Addr,
    AsyncReader,
    AsyncWriter,
    Connection,
    Errno,
    Message,
    PeerHandler
)
from pbcoin.process_handler import ProcessingHandler


logging = getLogger(__name__)


class Node:
    def __init__(self, conn: Connection):
        self.conn = conn
        self.is_listening = False
        self.neighbors: Dict[str, Tuple[str, int]] = dict()
        self.connected: Dict[str, str] = dict()
        self.tasks = []  # save all tasks that process message
        
    async def handle_peer(self, reader: AsyncReader, writer: AsyncWriter):
        """ this is a callback method that
        handles requests data that receive from other nodes"""
        peer_handler = PeerHandler(writer=writer, reader=reader)
        data = await self.conn.read(peer_handler.reader, peer_handler.addr)
        if data is None:
            raise Exception("Something wrong with read method and returns None")
        data = data.decode()
        if data == "":
            logging.warning(f"Get a empty data from {peer_handler.addr}")
            return
        logging.debug('receive data: ' + data)
        status = True
        pub_key = None
        actual_data = None
        try:
            data = json.loads(data)
            #TODO: check that request is from neighbors or not
            type_ = data['type']
            pub_key = data["pub_key"]
            actual_data = data["data"]
        except:
            status = False
            type_ = Errno.BAD_MESSAGE
            logging.debug(f"Bad message from {peer_handler.addr}")
        peer_handler.addr.pub_key = pub_key  # TODO: maybe it's better right check for pub_key 
        message = Message(status=status, type_=type_, dst_addr=peer_handler.addr, data=actual_data)
        proc_handler = ProcessingHandler(message=message, node=self)
        if not conf.settings.glob.debug:
            self.tasks.append(asyncio.create_task(proc_handler.handle()))
        else:
            #! TODO: just uses for debug and should be deleted after implementing handler
            task = asyncio.create_task(proc_handler.handle())
            await task

    async def listen(self):
        """start listening requests from other nodes and callback self.handle_peer"""
        try:
            ip_host = self.conn.addr.ip
            port_host = self.conn.addr.port
            self.server = await asyncio.start_server(
                self.handle_peer, host=ip_host, port=port_host)
        except Exception as e:
            logging.fatal("Could not start up server connection", exc_info=True)
            raise e
        logging.info(
            f"node connection is serve on {self.server.sockets[0].getsockname()}")
        async with self.server:
            try:
                self.is_listening = True
                await self.server.serve_forever()
            except Exception:
                logging.fatal("Serving is broken", exc_info=True)
            finally:
                self.is_listening = False

    async def write(self,
                    peer_handler: PeerHandler,
                    data: Union[str, bytes],
                    flush=True
    ) -> Optional[Exception]:
        """write data from writer to destination and if successfully return true
        otherwise return False
        """
        if peer_handler.writer is None : return Exception("Pass a non writable handler")
        sizeof = lambda input_data : '{:>08d}'.format(getsizeof(input_data)).encode()
        writer = peer_handler.writer
               
        if isinstance(data, str):
            data = data.encode()
        try:
            writer.write(sizeof(data))
            writer.write(data)
            if flush:
                await writer.drain()
        except Exception as e:
            logging.error(f"Could not write message to {peer_handler.addr}")
            return e
        return None

    async def read(self, peer_handler: PeerHandler) -> Optional[bytes]:
        """read data from reader if successfully return the data in bytes type
        otherwise return empty bytes
        """
        if peer_handler.reader is None : return None
        reader = peer_handler.reader
        data = b''
        try:
            size_data = await reader.read(NETWORK_DATA_SIZE)
            size_data = int(size_data)
            data = await reader.read(size_data)
        except Exception as e:
            logging.error(f"Could not read message from {peer_handler.addr}")
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
        for task in self.tasks:
            await task.close()

