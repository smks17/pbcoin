import logging
from datetime import datetime
from hashlib import sha512
from sys import getsizeof

import pbcoin
from pbcoin import trx
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
        self.blocHeight = blockHeight
        subsidy = Trx(self.blocHeight)
        self.trxList = [subsidy]
        self.nonce = 0

    def addTrx(self, inputs, outputs, time):
        # TODO: check validity
        self.trxList.append(trx.Trx(self.blocHeight, inputs, outputs, time))

    def getListHashesTrx(self):
        return [trx.hashTrx for trx in self.trxList]

    def setRootHashMerkleTree(self):
        self.rootHashMerkleTree = MerkleTree.buildMerkleTree(self.getListHashesTrx())

    def setMined(self):
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def updateOutputs(self):
        for trx in self.trxList:
            for i, out_coin in enumerate(trx.outputs):
                addr_coins = pbcoin.ALL_OUTPUTS.get(out_coin.owner)
                if addr_coins:
                    addr_coins.add((out_coin,i))
                else:
                    pbcoin.ALL_OUTPUTS[out_coin.owner] = {(out_coin, i)}
            for in_coin in trx.inputs:
                addr_coins = pbcoin.ALL_OUTPUTS.get(in_coin.owner)
                if addr_coins:
                    addr_coins.remove(in_coin.owner)
                else:
                    # TODO: bad trx
                    pass

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
            trxList = []
            for i in range(len(self.trxList)):
                trx = self.trxList[i].getData()
                trx['index'] = i
                trxList.append(trx)
            data = {
                "size": 0,  # set after init
                "trx": trxList,
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
            inputs = [Coin(in_coin['owner'], in_coin['value']) for in_coin in eachTrx['inputs']]
            outputs = [Coin(out_coin['owner'], out_coin['value']) for out_coin in eachTrx['outputs']]
            _trxList.append(
                Trx(new_block.blocHeight, inputs, outputs, eachTrx['time'])
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
