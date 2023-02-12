# TODO: net.py will be replaced by this module

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import random
from sys import argv
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Tuple
)

import pbcoin.config as conf
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
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
        self.messages_history: Dict[str, Any] = dict()  # TODO: use kinda combination of OrderedSet & Queue
        
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
            peer_handler.addr = Addr.from_hostname(data["src_addr"])
            type_ = data['type']
            pub_key = data["pub_key"]
            actual_data = data["data"]
        except:
            status = False
            type_ = Errno.BAD_MESSAGE
            logging.debug(f"Bad message from {peer_handler.addr}")
        peer_handler.addr.pub_key = pub_key  # TODO: maybe it's better right check for pub_key 
        message = Message(status=status,
                          type_=type_,
                          addr=peer_handler.addr,
                          data=actual_data)
        proc_handler = ProcessingHandler(message=message,
                                         node=self,
                                         peer_handler=peer_handler)
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

    def add_neighbor(self, new_addr: Addr):
        if not self.is_my_neighbor(new_addr):
            self.neighbors[new_addr.pub_key] = new_addr
        else:
            pass  # TODO: handle error

    def delete_neighbor(self, addr: Addr):
        if self.is_my_neighbor(addr):
            self.neighbors.pop(addr.pub_key)
        else:
            pass  # TODO: handle error
        
        
    def is_my_neighbor(self, addr: Addr) -> bool:
        return self.neighbors.get(addr.pub_key, None) is not None
            
    def add_message_history(self, message: Message):
        self.messages_history[message.addr.pub_key] = message

    def allow_new_neighbor(self):
        return len(self.neighbors) < TOTAL_NUMBER_CONNECTIONS

    def has_capacity_neighbors(self):
        return len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS
    
    def iter_neighbors(self, forbidden: Iterable[str] = [], shuffle = True) -> Generator:
        copy_neighbors = deepcopy(self.neighbors)
        if shuffle:
            random.shuffle(copy_neighbors)
        for pub_key in copy_neighbors:
            addr = self.neighbors.get(pub_key)
            if addr == None:
                continue  #! It's kinda non reachable at all
            # doesn't send data to the repetitious/forbidden nodes
            # maybe later stuck in a loop
            if addr.hostname not in forbidden:
                yield addr

    def close(self):
        """close listening and close all handler tasks"""
        if self.is_listening:
            self.server.close()
            self.is_listening = False
  
    @property
    def hostname(self) -> str: return self.conn.addr.hostname
