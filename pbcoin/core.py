from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .blockchain import BlockChain
    from .mempool import Mempool
    from .mine import Mine
    from .net import Node
    from .wallet import Wallet

BLOCK_CHAIN: Optional[BlockChain] = None
MINER: Optional[Mine] = None
WALLET: Wallet = None
ALL_OUTPUTS = dict() # TODO: move to database
NETWORK: Optional[Node] = None
MEMPOOL: Optional[Mempool] = None