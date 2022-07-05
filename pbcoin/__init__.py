from pbcoin.blockchain import BlockChain
from pbcoin.key import Key
from pbcoin.net import Node

DIFFICULTY = (2 ** 512 - 1) >> (4*4) # difficulty level
BLOCK_CHAIN : BlockChain = BlockChain()
addrKey: Key = None
NETWORK: Node = None