from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Dict

from pbcoin.block import Block, BlockValidationLevel
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.netbase import Addr, ConnectionCode, Message, Peer
from pbcoin.logger import getLogger
if TYPE_CHECKING:
    from pbcoin.blockchain import BlockChain
    from pbcoin.trx import Coin
    from pbcoin.network import Node
    from pbcoin.wallet import Wallet

logging = getLogger(__name__)


class ProcessingHandler:
    def __init__(self, blockchain: BlockChain, unspent_coins: Dict[str, Coin], wallet: Wallet):
        self.blockchain = blockchain
        self.unspent_coins = unspent_coins
        self.wallet = wallet
        
    async def handle(self, *args) -> bool:
        message = args[0]
        # TODO: Check the structure of message data is correct or not 
        if not message.status:
            self.handle_error()
        assert len(ConnectionCode) == 10, "Some ConnectionCode are not implemented yet!"
        if message.type_ == ConnectionCode.NEW_NEIGHBOR:
            await self.handle_new_neighbor(*args)
        elif message.type_ == ConnectionCode.NEW_NEIGHBORS_REQUEST:
            await self.handle_request_new_node(*args)
        elif message.type_ == ConnectionCode.NEW_NEIGHBORS_FIND:
            await self.handle_found_neighbors(*args)
        elif message.type_ == ConnectionCode.NOT_NEIGHBOR:
            await self.handle_delete_neighbor(*args)
        elif message.type_ == ConnectionCode.MINED_BLOCK:
            await self.handle_mined_block(*args)
        elif message.type_ == ConnectionCode.RESOLVE_BLOCKCHAIN:
            await self.handle_resolve_blockchain(*args)
        elif message.type_ == ConnectionCode.GET_BLOCKS:
            await self.handle_get_blocks(*args)
        elif message.type_ == ConnectionCode.SEND_BLOCKS:
            await self.handle_send_blocks(*args)
        elif message.type_ == ConnectionCode.ADD_TRX:
            await self.handle_new_trx(*args)
        elif message.type_ == ConnectionCode.PING:
            await self.handle_ping(*args)

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
        """handle a new node for add to the network by finding new neighbors for it"""
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
            # TODO: her it is awaiting for each request and ech node play a gather neighbors
            # TODO: it's better we could implement someway that could be connect directly and delete the middlenodes
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
                    if response.status == False:
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
                                  addr=addr
                          ).create_data(node_hostname=node.addr.hostname,
                                        pub_key=node.addr.pub_key)
                response = await node.connect_and_send(addr, request.create_message(node.addr))
                response = Message.from_str(response.decode())
                if response.status == True:
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
    
    async def handle_found_neighbors(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not used!")

    async def handle_delete_neighbor(self, message: Message, peer: Peer, node: Node):
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
        else:
            # TODO: make a error message
            response.status = False
        await node.write(peer.writer, response.create_message(node.addr), message.addr) 
        
    async def handle_mined_block(self, message: Message, peer: Peer, node: Node):
        """handle for request finder new block"""
        block_data = message.data
        logging.debug(f"Mine block from {message.addr.hostname}: {block_data}")
        block = Block.from_json_data_full(block_data['block'])
        # checking which blockchain is longer, own or its?
        if block.block_height > self.blockchain.height:
            number_new_blocks = block.block_height - self.blockchain.height
            if number_new_blocks == 1:
                # just this block is new
                done = self.blockchain.add_new_block(block, self.unspent_coins)
                if done != BlockValidationLevel.ALL():
                    # TODO: send why receive data is a bad request
                    logging.error(f"Bad request mined block from {message.addr.hostname} validation: {done}")
                else:
                    last = self.blockchain.last_block
                    last.update_outputs(self.unspent_coins)
                    self.wallet.updateBalance(deepcopy(last.transactions))
                    logging.info(f"New mined block from {message.addr.hostname}")
                    logging.debug(
                        f"info mined block from {message.addr.hostname}: {block.get_data()}")
            else:
                # TODO: request for get n block before this block for add to its blockchain and resolve
                pass
        else:
            # TODO: current blockchain is longer so declare other for resolve that
            logging.error("Not implemented resolve shorter blockchain")
        logging.debug(f"new block chian: {self.blockchain.get_hashes()}")
        
    def handle_resolve_blockchain(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_get_blocks(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_send_blocks(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_new_trx(self, message: Message, peer: Peer, node: Node):
        raise NotImplementedError("This method is not implemented yet!")

    async def handle_ping(self, message: Message, peer: Peer, node: Node):
        response = message.copy()
        response.addr = node.addr
        try:
            await node.write(peer.writer, response.create_message(node.addr), message.addr)
        except ConnectionError:
            pass  # TODO
