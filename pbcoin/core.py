from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pbcoin.blockchain import BlockChain
    from pbcoin.mempool import Mempool
    from pbcoin.mine import Mine
    from pbcoin.network import Node
    from pbcoin.wallet import Wallet

BLOCK_CHAIN: Optional[BlockChain] = None
MINER: Optional[Mine] = None
WALLET: Wallet = None
ALL_OUTPUTS = dict()  # TODO: move to database
NETWORK: Optional[Node] = None
MEMPOOL: Optional[Mempool] = None
