from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Optional

import pbcoin
from pbcoin.block import Block, BlockValidationLevel
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.mine import Mine
from pbcoin.utils.netbase import Addr, Peer
from pbcoin.netmessage import ConnectionCode, Errno, Message
from pbcoin.utils.tuple_util import tuple_from_string
from pbcoin.logger import getLogger
from pbcoin.trx import Coin, Trx
if TYPE_CHECKING:
    from pbcoin.core import Pbcoin
    from pbcoin.network import Node

logging = getLogger(__name__)


class ProcessingHandler:
    """This class is for handling request of other peers

    Attributes
    ----------
    blockchain: Blockchain
        A Blockchain object
    unspent_coins: Dict[str, Coin]
        List of unspent coins
    wallet: Wallet
        A Wallet object
    mempool: Mempool
        A Mempool object to add transactions
    """
    def __init__(self, pbcoin: Pbcoin):
        self.pbcoin = pbcoin

    async def handle(self, message: Message,  *args) -> None:
        """(async) Handles the request that a node was sended.

        Parameters
        ----------
        message: Message
            A Message object that contains received data.
        peer: Peer
            A Peer object that contains information about the sender.
        node: Node
            A node object that will be used for interacting other nodes.

        Return
        ------
        Nothing

        NOTE:: All other methods of this class have the same parameters and return item.
        And also they are async function too.
        """
        # TODO: Check the structure of message data is correct or not
        try:
            if not message.status:
                self.handle_error(message, *args)
            if message.type_ == ConnectionCode.NEW_NEIGHBOR:
                await self.handle_new_neighbor(message, *args)
            elif message.type_ == ConnectionCode.NEW_NEIGHBORS_REQUEST:
                await self.handle_request_new_node(message, *args)
            elif message.type_ == ConnectionCode.NOT_NEIGHBOR:
                await self.handle_delete_neighbor(message, *args)
            elif message.type_ == ConnectionCode.MINED_BLOCK:
                await self.handle_mined_block(message, *args)
            elif message.type_ == ConnectionCode.RESOLVE_BLOCKCHAIN:
                await self.handle_resolve_blockchain(message, *args)
            elif message.type_ == ConnectionCode.GET_BLOCKS:
                await self.handle_get_blocks(message, *args)
            elif message.type_ == ConnectionCode.ADD_TRX:
                await self.handle_new_trx(message, *args)
            elif message.type_ == ConnectionCode.PING_PONG:
                await self.handle_ping(message, *args)
        except Exception as e:
            logging.critical("Error in processing handler", exc_info=e)


    def handle_error(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not implemented yet!")

    async def handle_new_neighbor(self, message: Message, peer: Peer, node: Node):
        new_node_addr = Addr.from_hostname(message.data["new_node"])  # maybe it's better check with itself
        new_node_addr.pub_key = message.data["new_pub_key"]
        node.add_neighbor(new_node_addr)
        logging.info(f"New neighbor for {node.addr.hostname} : {new_node_addr.hostname}")
        response = Message(True,
                           ConnectionCode.NEW_NEIGHBOR,
                           message.addr
                           ).create_data(
                               new_node=node.addr.hostname,
                               new_pub_key=node.addr.pub_key)
        await node.write(peer.writer, response.create_message(node.addr), message.addr)

    async def handle_request_new_node(self, message: Message, peer: Peer, node: Node):
        """(async) Handles a new node just upped for addition to the network to try
        finding new neighbors for it.

        - It first checks itself to have a place to adds itself neighbors. If it is then,
        add itself to `to_request_other` list that contains nodes which the new node will
        request for adding to its neighbors list.

        - Next, if the new node still has a place for a neighbor, it will send a request to
        its neighbors for finding recursively new nodes to do the same.

        - If still didn't find any neighbors for it, it will delete a node from its
        neighbors and now there will be 2 new places (nodes) to be a new neighbors.

        - At the end, sends the result.
        """
        n_connections = int(message.data["n_connections"])
        message.data["passed_nodes"].append(node.addr.hostname)
        to_request_other = Message(
            status = True,
            type_ = ConnectionCode.NEW_NEIGHBORS_REQUEST,
            addr = message.addr
        ).create_data(
            n_connections = n_connections,
            p2p_nodes = message.data["p2p_nodes"],
            passed_nodes = message.data["passed_nodes"]
        )
        # add the new neighbor to itself if its capacity neighbors are not filled yet
        if node.allow_new_neighbor():
            n_connections -= 1
            to_request_other.data["p2p_nodes"].append(f"{node.addr.hostname}")
        # if still need new neighbors
        new_nodes = set()
        if n_connections != 0:
            # prepare message to send other nodes for search
            new_request = to_request_other.copy()
            # TODO: here it is awaiting for each request and ech node play a gather neighbors
            # TODO: it's better we could implement someway that could be connect
            #       directly and delete the middle nodes
            for addr in node.iter_neighbors(new_request.data["passed_nodes"]):
                new_request.addr = addr
                try:
                    response = await node.connect_and_send(
                        addr,
                        new_request.create_message(node.addr),
                        wait_for_receive=True)
                    if response is None:
                        continue
                    response = Message.from_str(response.decode())
                    if response.status is False:
                        continue
                    n_connections = response.data["n_connections"]
                    new_nodes |= set(response.data["p2p_nodes"])
                    to_request_other.data["p2p_nodes"] = list(new_nodes)
                    to_request_other.data["n_connections"] = n_connections
                except ConnectionError:
                    # TODO: checking for connection that neighbor is online yet?
                    logging.error(f"Could not connect and send data to {addr}", exc_info=True)
                except KeyError:
                    pass  # TODO
                # We find all its neighbors
                if n_connections == 0:
                    break
        # resolve connections if can not find Any neighbors for it
        # delete own neighbor then we have 2 free connections for neighbors
        if n_connections == TOTAL_NUMBER_CONNECTIONS and node.has_capacity_neighbors():
            for addr in node.iter_neighbors(forbidden = []):
                request = Message(status=True,
                                  type_=ConnectionCode.NOT_NEIGHBOR,
                                  addr=addr).create_data(node_hostname=node.addr.hostname,
                                                         pub_key=node.addr.pub_key)
                response = await node.connect_and_send(addr, request.create_message(node.addr))
                response = Message.from_str(response.decode())
                if response.status is True:
                    node.delete_neighbor(addr)
                    logging.info(f"delete neighbor for {node.addr.hostname} : {addr}")
                    new_nodes = [f"{node.addr.hostname}", f"{addr.hostname}"]
                    to_request_other.data["p2p_nodes"] += new_nodes
                    to_request_other.data['n_connections'] -= 2
                    break
        # send the result
        final_request = Message(status=True,
                                type_=ConnectionCode.NEW_NEIGHBORS_FIND,
                                addr=message.addr).create_data(
                                    p2p_nodes = to_request_other.data["p2p_nodes"],
                                    n_connections = to_request_other.data["n_connections"],
                                    passed_nodes = to_request_other.data["passed_nodes"],
                                    for_node = message.addr.hostname
                                )
        await node.write(peer.writer,
                         final_request.create_message(node.addr),
                         message.addr)

    async def handle_delete_neighbor(self, message: Message, peer: Peer, node: Node):
        """(async) Handles requests to end with being themself neighbors.

        See Also
        --------
        `handle_request_new_node()`
        """
        # TODO: send the result with nonblock
        response = Message(status=True,
                           type_=ConnectionCode.NOT_NEIGHBOR,
                           addr=message.addr).create_data(
                               node_hostname = node.addr.hostname,
                               pub_key = node.addr.pub_key
                           )
        addr = Addr.from_hostname(message.data["node_hostname"])
        addr.pub_key = message.data["pub_key"]
        if node.delete_neighbor(addr):
            logging.info(f"delete neighbor for {node.addr.hostname}: {message.addr.hostname}")
            response = Message(True, ConnectionCode.OK_MESSAGE, addr)
        else:
            response = Message(False, 0, addr)
        await node.write(peer.writer, response.create_message(node.addr), message.addr)

    @Mine.interrupt_mining()
    async def handle_mined_block(self, message: Message, peer: Peer, node: Node):
        """(async) Handles to request finder a new block.

        First the block will been checked:
        - If the new block is just the next of the last block of the self blockchain and
        it is valid, then it will be added to the self blockchain.

        - Else if the new block is just the next of the last block of self blockchain but
        it is not valid, it will send an error to the sender and not add to self
        blockchain.

        - If the new block is too further from the last block of the self blockchain and
        there is a gap between the new block and the self last block, it will get the gap
        blocks and resolve it with the self-blockchain. If there is any problem in the
        sent blocks, it will send an error to the sender and not add to the self
        blockchain.

        - Otherwise, if self blockchain is further than the new block, then it will tell
        the sender to get the new blocks and resolve its blockchain.
        """
        block_data = message.data
        logging.debug(f"Mine block from {message.addr.hostname}: {block_data} to check")
        block = Block.from_json_data_full(block_data['block'])
        # checking which blockchain is longer, mine or him?
        if block.block_height > self.pbcoin.blockchain.height:
            number_new_blocks = block.block_height - self.pbcoin.blockchain.height
            if number_new_blocks == 1:
                # just this block is new
                done = self.pbcoin.blockchain.add_new_block(block, self.pbcoin.all_outputs, db=self.pbcoin.database)
                if done != BlockValidationLevel.ALL():
                    error = Message(False, Errno.BAD_BLOCK_VALIDATION, peer.addr)
                    error = error.create_data(block_hash=block.__hash__,
                                              block_height=block.block_height,
                                              validation=done)
                    await node.write(peer.writer, error.create_message(node.addr))
                    logging.debug(f"Bad request mined block from {message.addr.hostname} validation: {done}")
                else:
                    last = self.pbcoin.blockchain.last_block
                    last.update_outputs(self.pbcoin.all_outputs)
                    logging.info(f"New mined block from {message.addr.hostname}")
                    logging.debug(f"info mined block from {message.addr.hostname}: {block.get_data()}")
                    ok_msg = Message(True, ConnectionCode.OK_MESSAGE, message.addr)
                    logging.debug(f"new block chian: {self.pbcoin.blockchain.get_hashes()}")
                    await node.write(peer.writer, ok_msg.create_message(node.addr))
            else:
                # request for get n block before this block for add to its blockchain and resolve
                request = Message(status = True,
                                  type_ = ConnectionCode.GET_BLOCKS,
                                  addr = message.addr,
                                  ).create_data(first_index = self.pbcoin.blockchain.height)
                res = await node.connect_and_send(message.addr, request.create_message(node.addr))
                res = Message.from_str(res.decode())
                if res.status:
                    blocks = res.data['blocks']
                    blocks = [Block.from_json_data_full(block) for block in blocks]
                    result, block_index, validation = self.pbcoin.blockchain.resolve(blocks, self.pbcoin.all_outputs)
                    if result:
                        logging.debug(f"new block chian: {self.pbcoin.blockchain.get_hashes()}")
                        ok_msg = Message(True, ConnectionCode.OK_MESSAGE, res.addr)
                        await node.write(peer.writer, ok_msg.create_message(node.addr))
                    else:
                        logging.debug("Bad validation blocks that it sent for get blocks")
                        fail_msg = Message(False, Errno.BAD_BLOCK_VALIDATION, peer.addr)
                        block = blocks[block_index]
                        fail_msg = fail_msg.create_data(block_hash = block.__hash__,
                                                        block_index = block_index,
                                                        validation = validation)
                        await node.write(peer.writer, fail_msg.create_message(node.addr))
                else:
                    # TODO
                    logging.error(f"Bad request was sended for get blocks from {peer.addr.hostname}")
        else:
            # TODO: current blockchain is longer so declare other for resolve that
            request = Message(False,
                              Errno.OBSOLETE_BLOCK,
                              peer.addr)
            await node.write(peer.writer, request.create_message(node.addr))

    @Mine.interrupt_mining()
    async def handle_resolve_blockchain(self, message: Message, peer: Peer, node: Node):
        """(async) Handles request to resolve self blockchain with new blocks."""
        blocks = message.data['blocks']
        blocks = [Block.from_json_data_full(block) for block in blocks]
        result, index_block, validation = self.pbcoin.blockchain.resolve(blocks, self.pbcoin.all_outputs)
        if not result:
            pass  # TODO: should tell other nodes that blocks have problem
        else:
            ok_msg = Message(True, ConnectionCode.OK_MESSAGE, message.addr)
            await node.write(peer.writer, ok_msg.create_message(node.addr))

    async def handle_get_blocks(self, message: Message, peer: Peer, node: Node):
        """(async) Handles for requesting another node for getting blocks from the first
        index or first block hash until the last block.
        """
        copy_blockchain = copy(self.pbcoin.blockchain)
        first_index: Optional[int] = None
        hash_block = message.data.get('hash_block', None)
        if hash_block:
            first_index = copy_blockchain.search(hash_block)
        else:
            first_index = message.data.pop('first_index', None)
        request = None
        if first_index is None or first_index > self.pbcoin.blockchain.height:
            # doesn't have this specific chain or block(s)
            # TODO: maybe it's good to get from a full node
            logging.debug("doesn't have self chain!")
            # TODO: report with error code
            request = Message(False,
                              Errno.BAD_BLOCK_VALIDATION,
                              message.addr)
        else:
            blocks = copy_blockchain.get_data(first_index)
            request = Message(True,
                              ConnectionCode.SEND_BLOCKS,  # TODO: Delete SEND_BLOCKS code
                              message.addr).create_data(blocks=blocks)
        await node.write(peer.writer, request.create_message(node.addr), False)

    async def handle_new_trx(self, message: Message, peer: Peer, node: Node):
        """(async) Handles to request maker a new transaction.

        Gets the data from the message and builds Trx object from it. After that check
        the validation of the transaction. If the transaction is valid, it will be added
        to the mempool to mine. Otherwise, will be sent an error message to the sender.
        """
        message.data['passed_nodes'].append(node.addr.hostname)
        public_key = message.data['public_key']
        sig = tuple_from_string(message.data['signature'], from_b64=True)
        trx_data = message.data['trx']
        trx_inputs = trx_data['inputs']
        trx_outputs = trx_data['outputs']
        inputs = []
        outputs = []
        # make trx from receive data
        for in_coin in trx_inputs:
            inputs.append(Coin(in_coin["owner"],
                               in_coin["out_index"],
                               in_coin["created_trx_hash"],
                               in_coin["value"],
                               in_coin["trx_hash"],
                               in_coin["in_index"]))
        for out_coin in trx_outputs:
            outputs.append(Coin(out_coin["owner"],
                                out_coin["out_index"],
                                out_coin["created_trx_hash"],
                                out_coin["value"]))
        time = trx_data['time']
        new_trx = Trx(self.pbcoin.blockchain.height,
                      self.pbcoin.wallet.public_key,
                      inputs, outputs, time)
        # add to mempool and send other nodes
        result = self.pbcoin.mempool.add_new_transaction(new_trx,
                                                  sig,
                                                  public_key,
                                                  self.pbcoin.all_outputs)
        if result:
            for pub_key in node.neighbors:
                dst_addr = node.neighbors[pub_key]
                if dst_addr.hostname not in message.data['passed_nodes']:
                    copy_msg = message.copy
                    copy_msg.src_addr = self.pbcoin.network.addr
                    copy_msg.dst_addr = dst_addr
                    await self.connect_and_send(dst_addr, copy_msg.create_message(self.pbcoin.network.addr), False)
            ok_message = Message(True, ConnectionCode.OK_MESSAGE, message.addr)
            await node.write(peer.writer, ok_message.create_message(node.addr), True)
        else:
            error = Message(False, Errno.BAD_TRANSACTION, message.addr)
            await node.write(peer.writer, error.create_message(node.addr), True)

    async def handle_ping(self, message: Message, peer: Peer, node: Node):
        """(async) Handles a ping message to check the connection. Just Pong it!"""
        response = message.copy()
        try:
            await node.write(peer.writer, response.create_message(node.addr), message.addr)
        except ConnectionError:
            pass  # TODO
