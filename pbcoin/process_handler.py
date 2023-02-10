from __future__ import annotations
from typing import TYPE_CHECKING

from pbcoin.netbase import Addr, ConnectionCode, Message
from pbcoin.logger import getLogger
if TYPE_CHECKING:
    from pbcoin.network import Node


logging = getLogger(__name__)


class ProcessingHandler:
    def __init__(self, message: Message, node: Node):
        self.message = message
        self.node = node

    async def handle(self) -> bool:
        if not self.message.status:
            self.handle_error()
        assert len(ConnectionCode) == 8, "Some ConnectionCode are not implemented yet!"
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

    def handle_new_neighbor(self):
        raise NotImplementedError("This method is not implemented yet!")

    def handle_request_new_node(self):
        raise NotImplementedError("This method is not implemented yet!")
    
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

