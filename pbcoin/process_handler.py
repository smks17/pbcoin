from __future__ import annotations

from typing import TYPE_CHECKING

from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.netbase import Addr, ConnectionCode, Message, PeerHandler
from pbcoin.logger import getLogger
if TYPE_CHECKING:
    from pbcoin.network import Node


logging = getLogger(__name__)


class ProcessingHandler:
    def __init__(self, message: Message, node: Node, peer_handler: PeerHandler):
        self.message = message
        self.node = node
        self.peer_handler = peer_handler

    async def handle(self) -> bool:
        if not self.message.status:
            self.handle_error()
        assert len(ConnectionCode) == 10, "Some ConnectionCode are not implemented yet!"
        if self.message.type_ == ConnectionCode.NEW_NEIGHBOR:
            await self.handle_new_neighbor()
        elif self.message.type_ == ConnectionCode.NEW_NEIGHBORS_REQUEST:
            await self.handle_request_new_node()
        elif self.message.type_ == ConnectionCode.NEW_NEIGHBORS_FIND:
            await self.handle_found_neighbors()
        elif self.message.type_ == ConnectionCode.NOT_NEIGHBOR:
            await self.handle_delete_neighbor()
        elif self.message.type_ == ConnectionCode.MINED_BLOCK:
            await self.handle_mined_block()
        elif self.message.type_ == ConnectionCode.RESOLVE_BLOCKCHAIN:
            await self.handle_resolve_blockchain()
        elif self.message.type_ == ConnectionCode.GET_BLOCKS:
            await self.handle_get_blocks()
        elif self.message.type_ == ConnectionCode.SEND_BLOCKS:
            await self.handle_send_blocks()
        elif self.message.type_ == ConnectionCode.ADD_TRX:
            await self.handle_new_trx()
        elif self.message.type_ == ConnectionCode.PING:
            await self.handle_ping()

    def handle_error(self):
        raise NotImplementedError("This method is not implemented yet!")

    async def handle_new_neighbor(self):
        new_node_addr = Addr.from_hostname(self.message.data["new_node"])  # maybe it's better check with itself
        new_node_addr.pub_key = self.message.data["new_pub_key"]
        self.node.add_neighbor(new_node_addr)
        logging.info(f"New neighbor for {self.node.hostname} : {new_node_addr.hostname}")
        self.node.add_message_history(self.message)
        print(f"Neighbors: {self.node.neighbors}!")
        
    async def handle_request_new_node(self):
        # TODO: this method maybe has error and should be debuged
        """handle a new node for add to the network by finding new neighbors for it"""
        n_connections = int(self.message.data["number_connections_requests"])
        self.message.data["passed_nodes"].append(self.node.hostname)
        to_request_other = Message(
            status = True,
            type_ = ConnectionCode.NEW_NEIGHBORS_REQUEST,
            addr = self.message.addr
        ).create_data(
            n_connections = n_connections,
            p2p_nodes = self.message.data["p2p_nodes"],
            passed_nodes = self.message.data["passed_nodes"]
        )
        # add the new neighbor to itself if its capacity neighbors are not filled yet
        if self.node.allow_new_neighbor():
            n_connections -= 1
            to_request_other.data["p2p_nodes"].append(f"{self.node.hostname}")
        # if still need new neighbors
        if n_connections != 0:
            # prepare message to send other nodes for search
            new_request = to_request_other.copy()
            for addr in self.node.iter_neighbors(new_request.data["passed_nodes"]):
                new_request.addr = addr
                try:
                    await self.node.conn.connect_and_send(
                        addr,
                        new_request.create_message(self.conn.node.addr),
                        wait_for_receive=False)
                    to_request_other = Message.from_str(response.decode())
                    n_connections = to_request_other['number_connections_requests']
                except ConnectionError:
                    # TODO: checking for connection that neighbor is online yet?
                    logging.error("", exc_info=True)
                except KeyError:
                    pass  # TODO
                # We find all its neighbors
                if n_connections == 0:
                    break

        # resolve connections if can not find Any neighbors for it
        # delete own neighbor then we have 2 free connections for neighbors
        if n_connections == TOTAL_NUMBER_CONNECTIONS and self.node.has_capacity_neighbors():
            for addr in self.node.iter_neighbors(forbidden = []):
                request = Message(status=True,
                                  type_=ConnectionCode.NOT_NEIGHBOR,
                                  addr=addr
                          ).create_data(node_key_pub=self.node.addr.pub_key)
                response = await self.connect_and_send(addr, request.create_message(self.node.addr))
                response = Message.from_str(response.decode())
                if response['status'] == True:
                    self.node.delete_neighbor(addr)
                    logging.info(f"delete neighbor for {self.node.hostname} : {addr}")
                    new_nodes = [f"{self.node.hostname}", f"{addr}"]
                    to_request_other.data["p2p_nodes"] += new_nodes
                    to_request_other.data['number_connections_requests'] -= 2
                    break
        # send the result
        final_request = Message(status=True,
                                type_=ConnectionCode.NEW_NEIGHBORS_FIND,
                                addr=self.message.addr).create_data(
                                    p2p_nodes = to_request_other.data["p2p_nodes"],
                                    n_connections = to_request_other.data["number_connections_requests"],
                                    passed_nodes = to_request_other.data["passed_nodes"],
                                    for_node = self.message.addr.hostname
                                )
        await self.node.conn.connect_and_send(
            self.message.addr,
            final_request.create_message(self.node.conn.addr),
            wait_for_receive=False)
    
    def handle_found_neighbors(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_delete_neighbor(self):
        raise NotImplementedError("This method is not implanted yet!")

    def handle_mined_block(self):
        raise NotImplementedError("This method is not implemented yet!")
        
    def handle_resolve_blockchain(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_get_blocks(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_send_blocks(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_new_trx(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_ping(self):
        raise NotImplementedError("This method is not implemented yet!")

