from __future__ import annotations

import asyncio
from copy import deepcopy
from json import JSONDecodeError
import random
from typing import (
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING
)

import pbcoin.config as conf
from pbcoin.blockchain import BlockChain
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.logger import getLogger, log_error_message
from pbcoin.netmessage import ConnectionCode, Errno, Message
from pbcoin.utils.netbase import (
    Addr,
    AsyncReader,
    AsyncWriter,
    Connection,
    Peer
)
if TYPE_CHECKING:
    from pbcoin.block import Block
    from pbcoin.process_handler import ProcessingHandler
    from pbcoin.trx import Trx
    from pbcoin.wallet import Wallet

logging = getLogger(__name__)


class Node(Connection):
    def __init__(self,
                 addr: Addr,
                 proc_handler: ProcessingHandler,
                 timeout: Optional[float] = None):
        super().__init__(addr, timeout)
        self.is_listening = False
        self.neighbors: Dict[str, Tuple[str, int]] = dict()
        self.tasks = []  # save all tasks that process message
        # TODO: use kinda combination of OrderedSet & Queue to store last message and
        #       in process_handler doesn't use direct write or read
        self.proc_handler = proc_handler

    async def handle_peer(self, reader: AsyncReader, writer: AsyncWriter):
        """ this is a callback method that
        handles requests data that receive from other nodes"""
        ip, port = writer.get_extra_info('peername')
        peer = Peer(addr=Addr(ip, port), writer=writer, reader=reader)
        data = await self.read(peer.reader, peer.addr)
        if data is None:
            raise Exception("Something wrong with read method and returns None")
        try:
            data = data.decode()
            message = None
            #TODO: check that request is from neighbors or not
            message = Message.from_str(data)
        except (JSONDecodeError, KeyError):
            logging.debug(f"Get a bad data message from {peer.addr}")
            error = Message(False, Errno.BAD_MESSAGE, peer.addr)
            await self.write(peer.writer, error.create_message(self.addr))
            return
        except Exception:
            logging.error("Something wrong in parsing message", exec_info=True)
            return
        logging.debug('receive data: ' + data)
        peer.addr = message.addr  # TODO: maybe it's better right check for pub_key
        if not conf.settings.glob.debug:
            self.tasks.append(
                asyncio.create_task(self.proc_handler.handle(message, peer, self))
            )
        else:
            #! TODO: just uses for debug and should be deleted after implementing handler
            task = asyncio.create_task(self.proc_handler.handle(message, peer, self))
            await task

    async def listen(self):
        """start listening requests from other nodes and callback self.handle_peer"""
        try:
            ip_host = self.addr.ip
            port_host = self.addr.port
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

    def delete_neighbor(self, addr: Addr) -> bool:
        if self.is_my_neighbor(addr):
            self.neighbors.pop(addr.pub_key)
            return True
        else:
            return False

    def is_my_neighbor(self, addr: Addr) -> bool:
        return self.neighbors.get(addr.pub_key, None) is not None

    def allow_new_neighbor(self):
        return len(self.neighbors) < TOTAL_NUMBER_CONNECTIONS

    def has_capacity_neighbors(self):
        return len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS

    def iter_neighbors(self, forbidden: Iterable[str] = [], shuffle = True) -> Generator:
        copy_neighbors_pub_key = deepcopy(list(self.neighbors.keys()))
        if shuffle:
            random.shuffle(copy_neighbors_pub_key)
        for pub_key in copy_neighbors_pub_key:
            addr = self.neighbors.get(pub_key)
            if addr is None:
                continue  #! It's kinda non reachable at all
            # doesn't send data to the repetitious/forbidden nodes
            # maybe later stuck in a loop
            if addr.hostname not in forbidden:
                yield addr

    def close(self):
        """close listening and close all handler tasks"""
        if self.is_listening:
            try:
                self.server.close()
                self.is_listening = False
            except asyncio.CancelledError:
                pass

    async def start_up(self, seeds: List[str], get_blockchain = True):
        """begin to find new neighbors and connect to the blockchain network"""
        nodes = []
        seeds = Addr.convert_to_addr_list(seeds)
        for seed in seeds:
            request = Message(status=True,
                              type_=ConnectionCode.NEW_NEIGHBORS_REQUEST,
                              addr=seed)
            request = request.create_data(n_connections = TOTAL_NUMBER_CONNECTIONS,
                                          p2p_nodes = [],
                                          passed_nodes = [self.addr.hostname])
            response = await self.connect_and_send(seed,
                                                   request.create_message(self.addr),
                                                   wait_for_receive=True)
            response = Message.from_str(response.decode())
            if not response.status:
                log_error_message(logging,
                                  seed,
                                  request.type_.name,
                                  response.type_.name)
                continue
            nodes += Addr.convert_to_addr_list(response.data['p2p_nodes'])
            # checking find all neighbors
            if (response.status is True
                    and response.type_ == ConnectionCode.NEW_NEIGHBORS_FIND
                    and response.data['n_connections'] == 0):
                break

        # sending found nodes for requesting neighbors
        for node in nodes:
            final_request = Message(True,
                                    ConnectionCode.NEW_NEIGHBOR,
                                    node)
            final_request = final_request.create_data(new_node = self.addr.hostname,
                                                      new_pub_key = self.addr.pub_key)
            response = await self.connect_and_send(node,
                                                   final_request.create_message(self.addr),
                                                   wait_for_receive=True)
            response = Message.from_str(response.decode())
            if response.status:
                self.add_neighbor(response.addr)
                logging.info(f"new neighbors for {self.addr.hostname} : {node.hostname}")
                if get_blockchain:
                    # get block chain from other nodes
                    #TODO: resolve blockchain
                    request_blockchain = Message(True, ConnectionCode.GET_BLOCKS, node)
                    request_blockchain.create_data(first_index=0)
                    rec = await self.connect_and_send(node,
                                                      request_blockchain.create_message(self.addr))
                    rec = Message.from_str(rec.decode())
                    if rec.status:
                        blockchain = BlockChain.json_to_blockchain(rec.data['blocks'])
                        logging.debug(f"Blockchain: {blockchain.blocks}")
                        if self.proc_handler.blockchain.height < blockchain.height:
                            self.proc_handler.blockchain = blockchain
                    else:
                        raise NotImplementedError()
            else:
                log_error_message(logging,
                                  seed,
                                  request.type_.name,
                                  response.type_.name)

    async def send_mined_block(self, block: Block) -> List[Tuple[Addr, Errno, Dict]]:
        """declare other nodes for find new block"""
        message = Message(True,
                          ConnectionCode.MINED_BLOCK,
                          None,
                          {"block": block.get_data()})
        errors = []
        for pub_key in self.neighbors:
            dst_addr = self.neighbors[pub_key]
            message.addr = dst_addr
            response = await self.connect_and_send(dst_addr,
                                                   message.create_message(self.addr),
                                                   True)
            try:
                response = Message.from_str(response.decode())
            except:
                continue  # NOTE: Here is not too much matter
            if not response.status:
                if response.type_ == Errno.BAD_BLOCK_VALIDATION:
                    pass  # TODO: better handle error
                errors.append((response.addr, response.type_, response.data))
                log_error_message(logging,
                                  dst_addr.hostname,
                                  message.type_.name,
                                  response.type_.name)
        return errors

    async def send_new_trx(self, trx: Trx, wallet: Wallet):
        """declare other neighbors new transaction for adding to mempool"""
        message = Message(True, ConnectionCode.ADD_TRX, None)
        message = message.create_data(trx = trx.get_data(with_hash=True),
                                      signature = wallet.base64Sign(trx),
                                      public_key = wallet.public_key,
                                      passed_nodes = [self.addr.hostname])
        errors = []
        for pub_key in self.neighbors:
            dst_addr = self.neighbors[pub_key]
            message.addr = dst_addr
            response = await self.connect_and_send(dst_addr,
                                                   message.create_message(self.addr),
                                                   True)
            if response is None:
                continue
            try:
                response = Message.from_str(response.decode())
            except:
                continue
            if not response.status:
                if response.type_ == Errno.BAD_TRANSACTION:
                    pass  # TODO: better handle error
                errors.append((response.addr, response.type_, response.data))
                log_error_message(logging,
                                  dst_addr.hostname,
                                  message.type_.name,
                                  response.type_.name)
        return errors

    async def send_ping_to(self, dst_addr) -> bool:
        request = Message(True, ConnectionCode.PING_PONG, dst_addr)
        try:
            rec = await self.connect_and_send(dst_addr,
                                              request.create_message(self.addr),
                                              wait_for_receive=True)
            if rec is None:
                return False
            rec = Message.from_str(rec.decode())
            if not rec.status:
                log_error_message(logging,
                                  dst_addr.hostname,
                                  request.type_.name,
                                  rec.type_.name)
                return False
        except Exception:
            return False
        return True
