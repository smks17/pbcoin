from hashlib import sha512

from pbcoin.trx import Trx

class Block:
    trxList : list[Trx]
    previousHash : str
    proof : int
    blockHash: str
    
    def __init__(self, preHash):
        self.previousHash = preHash
        # subsidy
        self.trxList.append(Trx())
        self.proof = 0

    def setProof(self, _proof: int): self.proof = _proof
    
    def calculateHash(self):
        calHash = sha512(self.__str__()).hexdigest()
        self.blockHash = calHash
        return calHash

    @property
    def hash(self):
        return self.calculateHash() if self.blockHash == None else self.blockHash

    def __str__(self) -> str:
        return self.trxList.__str__() + str(self.proof) + self.previousHash