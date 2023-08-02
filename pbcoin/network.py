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
from pbcoin.block import Block, BlockValidationLevel
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
    """The Node class for interaction with other nodes. This class inherits from
    the `Connection` class.
    
    See Also
    --------
    `class Connection` docs in `netbase.py`.
    """
    def __init__(self,
                 addr: Addr,
                 proc_handler: ProcessingHandler,
                 timeout: Optional[float] = None):
        super().__init__(addr, timeout)
        self.neighbors: Dict[str, Tuple[str, int]] = dict()
        self.tasks = []  # save all tasks that process message
        # TODO: use kinda combination of OrderedSet & Queue to store last message and
        #       in process_handler doesn't use direct write or read
        self.proc_handler = proc_handler

    async def handle_peer(self, reader: AsyncReader, writer: AsyncWriter):
        """(async) This is a callback method that handles requests for data received
        from other nodes.
        """
        # get its ip port from meta data
        ip, port = writer.get_extra_info('peername')
        # create a peer object to handle better
        peer = Peer(addr=Addr(ip, port), writer=writer, reader=reader)
        # read data
        data = await self.read(peer.reader, peer.addr)
        if data is None:
            raise Exception("Something wrong with read method and returns None")
        try:
            # create message
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
        # set peer addr from that in message say
        peer.addr = message.addr  # TODO: maybe it's better right check for pub_key
        # run handler in a async task
        if not conf.settings.glob.debug:
            self.tasks.append(
                asyncio.create_task(self.proc_handler.handle(message, peer, self))
            )
        else:
            #! TODO: just uses for debug and should be deleted after implementing handler
            task = asyncio.create_task(self.proc_handler.handle(message, peer, self))
            await task

    async def create_a_server(self, loop: Optional[asyncio.AbstractEventLoop]=None):
        """(async) It just creates a server with callback `self.handle_peer`. It gets the
        IP and Port of the server from `self.addr` and it will be run in a specific loop
        if it's passed. If the process is going on not successfully, it will be raised.
        """
        try:
            ip_host = self.addr.ip
            port_host = self.addr.port
            self.server = await asyncio.start_server(self.handle_peer,
                                                     host=ip_host,
                                                     port=port_host,
                                                     loop=loop)
        except Exception as e:
            logging.fatal("Could not start up server connection", exc_info=True)
            raise e
        else:
            logging.debug(
                f"Node server is created on {self.server.sockets[0].getsockname()}")

    async def listen(self):
        """(async) Start listening requests from other nodes and callback
        `self.handle_peer`. If the process is going on not successfully, it will be raised.
        """
        if not hasattr(self, "server") or self.server is None:
            await self.create_a_server()
        async with self.server:
            try:
                logging.info(f"Node server is listening to requests!")
                await self.server.serve_forever()
            except Exception:
                logging.fatal("Serving is broken", exc_info=True)
                raise

    def add_neighbor(self, new_addr: Addr):
        """Just adds new_addr to its neighbors if possible"""
        if not self.is_my_neighbor(new_addr):
            self.neighbors[new_addr.pub_key] = new_addr
        else:
            pass  # TODO: handle error

    def delete_neighbor(self, addr: Addr) -> bool:
        """Just deletes addr from its neighbors list if exists"""
        if self.is_my_neighbor(addr):
            self.neighbors.pop(addr.pub_key)
            return True
        else:
            return False

    def is_my_neighbor(self, addr: Addr) -> bool:
        """Check this addr is in its neighbors lists or not"""
        return self.neighbors.get(addr.pub_key, None) is not None

    def allow_new_neighbor(self) -> bool:
        """Checks have any place for new neighbors in which
            were not reached TOTAL_NUMBER_CONNECTIONS or not
        """
        return len(self.neighbors) < TOTAL_NUMBER_CONNECTIONS

    def has_capacity_neighbors(self) -> bool:
        """Check the number of neighbors were reached TOTAL_NUMBER_CONNECTIONS or not"""
        return len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS

    def iter_neighbors(self, forbidden: Iterable[str] = [], shuffle = True) -> Generator:
        """Iteration to its neighbors except they are not on the forbidden list"""
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
        try:
            self.server.close()
        except asyncio.CancelledError:
            pass

    async def start_up(self, seeds: List[str], get_blockchain = True) -> None:
        """(async) Begins to find new neighbors and connect to the blockchain network.

        Starts from some nodes and requests them to find some new neighbors nodes. After
        receiving results, tries to connect and be  neighbors with found nodes in the
        result. In the end, try to get blockchain from self neighbors.

        Parameters
        ---------
        seeds: List[str]
            A list of hostname to connect them for start point.
        get_blockchain: bool = True
            Determines get blockchain from other nodes or not.

        Return
        ------
        Nothing
        """
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
        """Declares other neighbor nodes that have found a newly mined block.

        Creates a message containing the new block data. Then sends and waits to get a
        response from the node to determine if there are any errors or not.

        If the response says BAD_BLOCK_VALIDATION, it will be checked block and if the
        node has said correct, it stops sending to others. otherwise, ignore that
        response.

        Else if the response says OBSOLETE_BLOCK, it will try to get new blocks from
        other nodes.

        On the other side, nodes also do the same.

        Parameters
        ----------
        block: Block
            The transactions that want to be declared others.

        Return
        ------
        List[Tuple[Addr, Errno, Dict[str, Any]]]
            Returns a list of errors the data contains: the address of which error
            response, the type's error, and the message data that will be needed.
        
        See Also
        --------
        `ProcessHandler.handle_new_block()`
        """
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
                    pre_hash = self.proc_handler.blockchain[block.block_height - 1].__hash__
                    validation = block.is_valid_block(self.proc_handler.unspent_coins,
                                                      pre_hash=pre_hash)
                    if validation != BlockValidationLevel.ALL():
                        logging.error("Bad block is mined")
                        errors.append((response.addr, response.type_, response.data))
                        # TODO: Remove that from blockchain
                        break
                elif response.type_ == Errno.OBSOLETE_BLOCK:
                    request = Message(status = True,
                                      type_ = ConnectionCode.GET_BLOCKS,
                                      addr = dst_addr,
                                      ).create_data(first_index = self.proc_handler.blockchain.height - 1)
                    res = await self.connect_and_send(message.addr, request.create_message(self.addr))
                    res = Message.from_str(res.decode())
                    if res.status:
                        blocks = res.data['blocks']
                        blocks = [Block.from_json_data_full(block) for block in blocks]
                        result, block_index, validation = self.proc_handler.blockchain.resolve(blocks, self.proc_handler.unspent_coins)
                        if result:
                            logging.debug(f"new block chian: {self.proc_handler.blockchain.get_hashes()}")
                            break
                        # TODO: Add penalty for node that badly response and tell it
                        else:
                            logging.debug("Bad validation blocks that it sent for get blocks")
                    else:
                        logging.error("Bad request send for get blocks")
                        errors.append((response.addr, response.type_, response.data))
                        log_error_message(logging,
                                          dst_addr.hostname,
                                          message.type_.name,
                                          res.type_.name)
        return errors

    async def send_new_trx(self, trx: Trx, wallet: Wallet) -> List[Tuple]:
        """Declares other neighbors nodes to add to their mempool the new transaction
        which just has been created.

        Creates a message containing transaction data and the signature and self public
        key address. Then sends that and waits to get a response from the node to
        determine if there is any errors or not.

        On the other side, nodes also do the same.

        Parameters
        ----------
        trx: Trx
            The transactions that want to be declared others.
        wallet: Wallet
            The wallet object for signing and get the public key address.

        Return
        ------
        List[Tuple[Addr, Errno, Dict[str, Any]]]
            Returns a list of errors the data contains: the address of which error
            response, the type's error, and the message data that will be needed.
        
        See Also
        --------
        `ProcessHandler.handle_new_trx()`
        """
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

    async def send_ping_to(self, dst_addr: Addr) -> bool:
        """Sends a Ping message to dst_addr and returns True if the response is OK,
        otherwise False if the connection failed for some reason.

        See Also
        --------
        `ProcessHandler.handle_ping()
        """
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

    @property
    def is_listening(self) -> bool:
        if hasattr(self, "server") or self.server is not None:
            return self.server.is_serving
        return False