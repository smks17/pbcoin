import random
import hashlib

SIZE_KEY = 256

_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

class Point:
    def __init__(self, x, y, p = _P):
        self.__x = x
        self.__y = y
        self.P = p

    def getCoordinate(self):
        return self.__x, self.__y

    def __add__(self,  __o: object) -> object:
        if __o == self:
            sloop =  sloop = 3 * (self.__x ** 2) * pow(2 * self.__y, self.P - 2, self.P)
        else:
            sloop = (__o.__y - self.__y) * pow(__o.__x - self.__x, self.P - 2, self.P)
        x = (sloop ** 2) - self.__x - __o.__x
        y = sloop * (self.__x - x) - self.__y
        return Point(x % self.P, y % self.P)

    def __eq__(self, __o: object) -> bool:
        return __o.__x == self.__x and __o.__y == self.__y

    def __repr__(self) -> str:
        return f'({self.__x}, {self.__y})'

class Key:
    G = Point(0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
              0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

    def __init__(self, sk = None):
        self.__sk = sk
        self.__pk = None

    def genPrivateKey(self, seed: int = 0):
        random.seed(seed)
        key = random.randbytes(int(SIZE_KEY / 8))
        self.__sk = int.from_bytes(key, "little")
        return self.__sk

    def genPublicKey(self):
        # TODO: check if public key was not generated for __sk
        if not self.__sk:
            self.genPrivateKey(123)
        ret = self.G
        G = self.G
        for i in range(1, SIZE_KEY):
            G += G
            if self.__sk & (1 << i):
                ret = ret + G

        x, y = ret.getCoordinate()
        self.__pk = '0x4' + hex(x)[2:] + hex(y)[2:]
        return self.__pk


    @staticmethod
    def isValid(sk, pk):
        # TODO: better validation
        temp = Key(sk)
        temp.genPublicKey()
        return temp.uncompressedPublic == pk

    @property
    def compressedPublic(self):
        x = self.__pk[3:64 + 3]
        y = int(eval('0x' + self._Key__pk[-64:]))
        pre = '0x2' if y % 2 else '0x3'
        return pre + x

    @property
    def uncompressedPublic(self):
        return self.genPublicKey()

    @property
    def secret(self):
        return self.__sk if self.__sk else 0
