from __future__ import annotations

from enum import IntEnum, IntFlag, auto

class CliErrorCode(IntFlag):
    """Flags for using in the cli api"""
    NOTHING = 0  # no err
    BAD_USAGE = auto()  # bad usage of cli
    NOT_FOUND = auto()  # not found your request query
    TRX_PROBLEM = auto()  # problem in making or sending transactions
    MINING_ON = auto()  # mining is already working
    MINING_OFF = auto()  # mining has already been stoped

    def message(self):
        """get the message for this code"""
        assert len(CliErrorCode) == 6, "Not Implemented a or more code yet"
        if self & CliErrorCode.BAD_USAGE:
            return "ERROR: Bad usage for command"
        elif self & CliErrorCode.NOT_FOUND:
            return "ERROR: Not found your request"
        elif self & CliErrorCode.TRX_PROBLEM:
            return "ERROR: Problem in build and send transaction"
        elif self & CliErrorCode.MINING_ON:
            return "ERROR: Mining was already working"
        elif self & CliErrorCode.MINING_OFF:
            return "ERROR: Mining has already been stoped"
        else:
            return f"ERROR: {self}"

# TODO: better command and subcommand
class CliCommandCode(IntEnum):
    """All command in cli for cli api"""
    NONE = 0  # bad
    GEN_KEY = auto()  # TODO: generate a pair key
    TRX = auto()  # build a transaction
    BALANCE = auto()  # get the balance wallet
    BLOCK = auto()  # query block
    MEMPOOL = auto()  # query mempool
    NEIGHBORS = auto()  # query neighbors in the network
    MINING = auto()  # stop/start mining ang get state

    @staticmethod
    def getCode(value: str) -> CliCommandCode:
        value = value.strip().lower()
        assert len(CliCommandCode) == 9, "Not Implemented one or more command yet"
        if value == 'gen-key':
            return CliCommandCode.GEN_KEY
        elif value == 'trx':
            return CliCommandCode.TRX
        elif value == 'node':
            return CliCommandCode.NODE
        elif value == 'balance':
            return CliCommandCode.BALANCE
        elif value == 'block':
            return CliCommandCode.BLOCK
        elif value == 'mempool':
            return CliCommandCode.MEMPOOL
        elif value == 'neighbors':
            return CliCommandCode.NEIGHBORS
        elif value == 'mining':
            return CliCommandCode.MINING
        else:
            return CliCommandCode.NONE
