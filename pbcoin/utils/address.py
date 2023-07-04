"""A simple address generation (SECP256K1)"""
from __future__ import annotations

import os.path as opt
from os import mkdir

import base64
from dataclasses import dataclass
from hashlib import sha256
from random import randint
from typing import Optional, Tuple

from pbcoin.utils.tuple_util import tuple_from_string, tuple_to_string

@dataclass
class Curve:
    """elliptic curve"""
    a: int
    b: int
    P: int
    N: int


class Point:
    """This class is simple represent of a point in elliptic curve"""
    def __init__(self, x, y, curve: Curve):
        self._x = x
        self._y = y
        self._curve = curve

    def __add__(self, __o):
        assert __o._curve == self._curve
        if self.is_identity():
            return Point(__o._x, __o._y, __o._p, __o._a)
        elif __o.is_identity():
            return Point(self._x, self._y, self._curve)
        if self == __o:
            return self._double()
        if self._x == __o._x:
            return Point(None, None, self._curve)
        s = ((__o._y - self._y)
             * pow((__o._x - self._x), -1, self._curve.P))
        x3 = ((s * s) - self._x - __o._x) % self._curve.P
        y3 = (s * (self._x - x3) - self._y) % self._curve.P
        return Point(x3, y3, self._curve)

    def _double(self):
        s = ((3 * (self._x * self._x) + self._curve.a)
             * pow((2 * self._y), -1, self._curve.P))
        x3 = ((s * s) - (2 * self._x)) % self._curve.P
        y3 = (s * (self._x - x3) - self._y) % self._curve.P
        return Point(x3, y3, self._curve)

    def __rmul__(self, n):
        if n == 0:
            return Point(None, None, None, None)
        elif n == 1:
            return Point(self._x, self._y, self._curve)
        if n % 2 == 0:
            return (self + ((n-1) * self))
        else:
            return (self + ((n//2) * (self + self)))

    def is_identity(self):
        return self._x is None

    def __eq__(self, __o):
        return (self._x == __o._x and
                self._y == __o._y)

    def __str__(self) -> str:
        return f"({self._x}, {self._y})"

    def __getitem__(self, i):
        if isinstance(i, int):
            if i == 0:
                return self._x
            elif i == 1:
                return self._y
        elif isinstance(i, str):
            if i.lower() == "x":
                return self._x
            elif i.lower() == "x":
                return self._y
        raise ValueError()

    @staticmethod
    def from_str(string: str, curve: Optional[Curve] = None, from_b64=False):
        if from_b64:
            string = base64.b64decode(string).decode()
        if string.startswith("0x"):
            string = string[2:]
        length = len(string) // 2
        x = int(string[:length], 16)
        y = int(string[length:], 16)
        return Point(x, y, curve)

    @property
    def tuple(self):
        return (self._x, self._y)


class Address:
    """Generator address of wallet in SECP256K1 curve"""
    _MAX_SECRET_VALUE = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140
    SECP256K1 = Curve(a=0, b=7,
                      P=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F,
                      N=0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141)
    G = Point(0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798,
              0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8,
              SECP256K1)

    def __init__(self,
                 secret: Optional[int] = None,
                 public: Optional[Point] = None) -> None:
        self._secret = secret
        self.public = public

    def gen_public(self):
        if self._secret is None:
            raise ValueError("_secret is None")
        self.public = self._secret * self.G

    def gen_secret(self):
        self._secret = randint(1, self._MAX_SECRET_VALUE)

    @property
    def private(self):
        return self._secret

    def save(self, base_path):
        """save keys in base64 in base_path with file names:

        public -> key.pub

        private -> sec.pub

        If secret or public haven't generated, it would generate
        """
        if self._secret is None:
            self.gen_secret()
        if self.public is None:
            self.gen_public()
        if not opt.exists(base_path):
            mkdir(base_path)
        public_key_path = opt.join(base_path, "key.pub")
        # write in files
        with open(public_key_path, "w") as f:
            f.write(tuple_to_string(self.public.tuple, self.SECP256K1.N).decode())
        # TODO: write as PEM format
        private_key_path = opt.join(base_path, "key.sk")
        with open(private_key_path, "w") as f:
            f.write(base64.b64encode(hex(self._secret).encode()).decode())

    @property
    def public_key(self) -> str:
        """in hex"""
        return tuple_to_string(self.public.tuple,
                               max_val=self.SECP256K1.N,
                               to_b64=False)

    @staticmethod
    def load(base_path):
        """load secret from base_path. there must be a key.sk file name
        that contains secret key"""
        private_key_path = opt.join(base_path, "key.sk")
        with open(private_key_path, "r") as f:
            encoded_secret = f.read()
        secret = int((base64.b64decode(encoded_secret)).decode(), 16)
        address = Address(secret=secret)
        address.gen_public()
        return address

    def sign(self, message: str, message_is_hash=True) -> Tuple[int, int]:
        """sign message by its keys and return a tuple r and s"""
        def hash(integer):
            return int(sha256(integer.encode("utf-8")).hexdigest(), 16)

        def calculate_r_s(k, msg):
            N = self.SECP256K1.N
            R = k * self.G
            r = R[0] % N
            s = ((msg + r * self.private) * pow(k, -1, N)) % N
            return r, s
        if message_is_hash:
            i_message = int(message, 16)
        else:
            message = hash(message)
            i_message = int(message, 16)
        k = hash(str(i_message) + message) % (self.SECP256K1.N - 1)
        r, s = calculate_r_s(k, i_message)
        while r == 0 or s == 0:
            k = randint(1, self.SECP256K1.N - 1)
            r, s = calculate_r_s(k, i_message)
        return r, s

    @classmethod
    def verify(cls, message: str, sig: Tuple[int, int], public_key: str, from_b64=True) -> bool:
        """verify a message by r and s in sig parameter by its key"""
        r, s = sig
        message = int(message, 16)
        N = cls.SECP256K1.N
        if 1 > r and r >= N:
            raise ValueError("r is not in range (1, N-1)")
        if 1 > s and s >= N:
            raise ValueError("s is not in range (1, N-1)")
        inv = pow(s, -1, N)
        u1 = ((message * inv) % N) * cls.G
        u2 = ((r * inv) % N) * Point.from_str(public_key,
                                              curve=cls.SECP256K1,
                                              from_b64=from_b64)
        v = u1 + u2
        return (v[0] % N == r)
