import json
from datetime import datetime
from hashlib import sha512
from sys import getsizeof

from pbcoin.trx import Coin, Trx
from pbcoin.merkleTree import MerkleTree

class Block:
    trxList: list[Trx]
    previousHash: str
    nonce: int
    blockHash: str
    time: float  # time that this block mined in POSIX timestamp format
    is_mined = False
    blocHeight: int
    trxHashes: list[str]  # using for header block
    rootHashMerkleTree: MerkleTree = None

    def __init__(self, preHash: str, blockHeight: int):
        self.previousHash = preHash
        subsidy = Trx()
        self.trxList = [subsidy]
        self.nonce = 0
        self.blocHeight = blockHeight

    def addTrx(self, _trx):
        # TODO: check validity
        self.trxList.append(_trx)

    def getListHashesTrx(self):
        return [trx.hashTrx for trx in self.trxList]

    def setRootHashMerkleTree(self):
        self.rootHashMerkleTree = MerkleTree.buildMerkleTree(self.getListHashesTrx())

    def setMined(self):
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def setNonce(self, _nonce: int): self.nonce = _nonce

    def calculateHash(self):
        if not self.rootHashMerkleTree:
            self.setRootHashMerkleTree()
        nonceHash = sha512(str(self.nonce).encode()).hexdigest()
        calculatedHash = sha512(
            (self.rootHashMerkleTree.hash + nonceHash + self.previousHash).encode()).hexdigest()
        self.blockHash = calculatedHash
        return calculatedHash

    def getData(self, fullBlock = True, is_POSIX_timestamp = True):
        blockHeader = {
            "hash": self.__hash__,
            "height": self.blocHeight,
            "nonce": self.nonce,
            "number_trx": len(self.trxList),
            "merkle_root": self.rootHashMerkleTree.hash,
            "trx_hashes": self.getListHashesTrx(),
            "previous_hash": self.previousHash,
            "time": self.time if is_POSIX_timestamp else datetime.fromtimestamp(self.time)
        }
        data = blockHeader
        if fullBlock:
            data = {
                "size": 0,  # set after init
                "trx": [trx.getData() for trx in self.trxList],
                "header": blockHeader
            }
            data['size'] = getsizeof(data)
        return data

    @staticmethod
    def fromJsonDataHeader(_data: dict['str', any], is_POSIX_timestamp = True):
        new_block = Block(_data['previous_hash'], _data['height'])
        new_block.blockHash = _data['hash']
        new_block.nonce = _data['nonce']
        new_block.trxHashes = _data['trx_hashes']
        new_block.rootHashMerkleTree = MerkleTree(_data['merkle_root'])
        if is_POSIX_timestamp:
            new_block.time = _data['time']
        else:
            datetime.fromisoformat(_data['time'])
        return new_block

    @staticmethod
    def fromJsonDataFull(_data: dict['str', any], is_POSIX_timestamp = True):
        new_block = Block.fromJsonDataHeader(_data['header'], is_POSIX_timestamp)
        trx = _data['trx']
        _trxList = [] 
        for eachTrx in trx:
            inputs = [Coin(in_coin['owner'], Coin['value']) for in_coin in eachTrx['inputs']]
            outputs = [Coin(out_coin['owner'], Coin['value']) for out_coin in eachTrx['inputs']]
            _trxList.append(
                Trx(inputs, outputs, eachTrx['time'])
            )
        new_block.trxList = _trxList
        return new_block


    @property
    def __hash__(self):
        return self.calculateHash() if self.blockHash == None else self.blockHash

    def __str__(self) -> str:
        return self.trxList.__str__() + str(self.proof) + self.previousHash

    def __repr__(self) -> str:
        return self.getData()
