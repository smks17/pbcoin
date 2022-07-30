import logging
from datetime import datetime
from hashlib import sha512
from sys import getsizeof

import pbcoin
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

    def addTrx(self, _trx):
        self.trxList.append(_trx)
        self.setRootHashMerkleTree()

    def getListHashesTrx(self):
        return [trx.hashTrx for trx in self.trxList]

    def setRootHashMerkleTree(self):
        # TODO: implement add function in merkle tree
        self.rootHashMerkleTree = MerkleTree.buildMerkleTree(self.getListHashesTrx())

    def setMined(self):
        self.time = datetime.utcnow().timestamp()
        self.is_mined = True

    def checkTrx(self):
        # TODO: return validation
        for index, trx in enumerate(self.trxList):
            in_coins = trx.inputs
            out_coins = trx.outputs
            for coin in in_coins:
                if not coin.checkInputCoin():
                    return False
            if index != 0:
                output_value = sum(out_coin.value for out_coin in out_coins)
                input_value = sum(in_coin.value for in_coin in in_coins)
                if output_value != input_value:
                    return False
            if trx.time <= datetime(2022, 1, 1).timestamp():
                return False
            if not all([out_coin.trxHash == trx.hashTrx for out_coin in out_coins]):
                return False
        return True

    @staticmethod
    def updateOutputs(block):
        for trx in block.trxList:
            in_coins = trx.inputs
            out_coins = trx.outputs
            for coin in in_coins:
                if coin.checkInputCoin():
                    unspent = pbcoin.ALL_OUTPUTS[trxHash]
                    unspent[coin.index] = None
                    if not any(unspent):
                        pbcoin.ALL_OUTPUTS.pop(trxHash)
                else:
                    pass # TODO
            
            for coin in out_coins:
                trxHash = coin.trxHash
                pbcoin.ALL_OUTPUTS[trxHash] = out_coins

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
        for trx_idx, eachTrx in enumerate(trx):
            inputs = []
            for coin_idx, in_coin in enumerate(eachTrx['inputs']):
                inputs.append(Coin(in_coin['owner'], coin_idx, in_coin['trx_hash'], in_coin['value']))
            outputs = []
            for coin_idx, out_coin in enumerate(eachTrx['outputs']):
                outputs.append(Coin(out_coin['owner'], coin_idx, out_coin['trx_hash'], out_coin['value']))
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
