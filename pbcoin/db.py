from __future__ import annotations
from copy import deepcopy

from typing import Any, Dict, Optional

import pbcoin.config as conf
from pbcoin.block import Block
from pbcoin.trx import Trx, Coin
from pbcoin.utils.sqlite import Sqlite


class DB:
    """The database class
    
    It uses to insert and query objects like ```Block```, ```Trx``` and ```Coin```.
    """
    def __init__(self,
                 db_path: Optional[str] = None,
                 blocks_table_name: Optional[str] = None,
                 trx_table_name: Optional[str] = None,
                 coins_table_name: Optional[str] = None):
        if db_path is None:
            db_path = conf.settings.database.path
        self.db = Sqlite(db_path, check_same_thread=False)
        if blocks_table_name is None:
            blocks_table_name = conf.settings.database.blocks_table
        self.blocks_table_name = blocks_table_name
        if trx_table_name is None:
            trx_table_name = conf.settings.database.trx_table
        self.trx_table_name = trx_table_name
        if coins_table_name is None:
            coins_table_name = conf.settings.database.coins_table
        self.coins_table_name = coins_table_name

    def init(self, init_filename: Optional[str] = None):
        if init_filename is None:
            init_filename = conf.settings.database.init_filename
        self.db.run_sql_file(init_filename)

    def insert_block(self, block: Block | Dict[str, Any]):
        if isinstance(block, Block):
            data = block.get_data(is_full_block=True, is_POSIX_timestamp=True)
        else:
            assert block.get("header") is not None
            data = deepcopy(block)
        header_block = data["header"]
        trx_hashes = header_block.pop("trx_hashes")
        size = data.pop("size")
        for trx_data in data["trx"]:
            trx_data["hash"] = trx_hashes[trx_data["index"]]
            self.insert_trx(trx_data)
        self.db.insert(header_block, self.blocks_table_name)

    def insert_trx(self, trx: Trx | Dict[str, Any]):
        if isinstance(trx, Trx):
            trx_data = trx.get_data(with_hash=True)
        else:
            trx_data = deepcopy(trx)
        inputs = trx_data.pop("inputs")
        outputs = trx_data.pop("outputs")
        trx_data["t_index"] = trx_data.pop("index")
        for coin_data in inputs + outputs:
            self.insert_coin(coin_data)
        self.db.insert(trx_data, self.trx_table_name)

    def insert_coin(self, coin: Coin | Dict[str, Any]):
        if isinstance(coin, Coin):
            coin_data = coin.get_data()
        else:
            coin_data = deepcopy(coin)
        q = self.get_coin(coin_hash=coin_data["hash"])
        if not q:
            self.db.insert(coin_data, self.coins_table_name)
        else:
            self.db.update([("hash", coin_data["hash"])],
                           coin_data.items(),
                           self.coins_table_name)

    def get_block(self, hash_str: Optional[str] = None, index: Optional[int] = None) -> Block:
        assert ((hash_str is not None) ^ (index is not None)),  \
            "Should been passed just (at least) hash_str or index to query"
        if hash_str is not None:
            q = self.db.query("*", self.blocks_table_name, [("hash", hash_str)])[0]
        elif index is not None:
            q = self.db.query("*", self.blocks_table_name, [("index", index)])[0]
        block_header = {
            "hash": q[0],
            "height": int(q[1]),
            "nonce": int(q[2]),
            "number_trx": int(q[3]),
            "merkle_root": q[4],
            "previous_hash": q[5],
            "time": q[6]
        }
        # TODO: get by order index
        list_trx, hash_list_trx = self.get_trx(block_hash = hash_str)
        block_header["trx_hashes"] = hash_list_trx
        block_data = {
            "header": block_header,
            "trx": list_trx,
            "size": None
        }
        return block_data

    def get_last_block(self):
        q = self.db.query("*, MAX(height) AS height", self.blocks_table_name)
        if not q:
            return None
        q = q[0]
        block_header = {
            "hash": q[0],
            "height": int(q[1]),
            "nonce": int(q[2]),
            "number_trx": int(q[3]),
            "merkle_root": q[4],
            "previous_hash": q[5],
            "time": q[6]
        }
        return block_header

    def get_trx(self, trx_hash: Optional[str] = None, block_hash: Optional[str] = None):
        assert ((trx_hash is not None) ^ (block_hash is not None)),  \
            "Should been passed just (at least) trx_hash or block_hash to query"
        if trx_hash is not None:
            q_trx = self.db.query("*", self.trx_table_name, [("hash", trx_hash)])
        if block_hash is not None:
            q_trx = self.db.query("*", self.trx_table_name, [("include_block", block_hash)])
        list_trx = []
        hash_list_trx = []
        for q in q_trx:
            index = int(q[3])
            hash_list_trx.insert(index, q[0])
            trx_data = {
                "hash": q[0],
                "include_block": q[1],
                "value": int(q[2]),
                "index": int(q[3]),
                "time": int(q[4])
            }
            inputs = self.get_coin(created_trx_hash=q[0])
            trx_data["inputs"] = inputs
            outputs = self.get_coin(trx_hash=q[0])
            trx_data["outputs"] = outputs
            list_trx.insert(index, trx_data)
            return list_trx, hash_list_trx

    def get_coin(self,
                 coin_hash: Optional[str] = None,
                 created_trx_hash: Optional[str] = None,
                 trx_hash: Optional[str] = None):
        assert ((coin_hash is not None) ^ (created_trx_hash is not None) ^ (trx_hash is not None)),  \
            "Should been passed just (at least) coin_hash or trx_hash to query"
        if coin_hash is not None:
            q_coins = self.db.query("*", self.coins_table_name, [("hash", coin_hash)])
        elif created_trx_hash is not None:
            q_coins = self.db.query("*", self.coins_table_name, [("created_trx_hash", created_trx_hash)])
        elif trx_hash is not None:
            q_coins = self.db.query("*", self.coins_table_name, [("trx_hash", trx_hash)])
        coins = []
        for q in q_coins:
            coin = {
                "hash": q[0],
                "created_trx_hash": q[1],
                "in_index": int(q[2]),
                "value": int(q[3]),
                "owner": q[4],
            }
            # if coin was spent
            if q[5]:
                coin.update({"trx_hash": q[5], "out_index": int(q[6])})
                coins.insert(coin["out_index"], coin)
            else:
                coins.insert(coin["in_index"], coin)
        return coins


# TODO: write unittest for db
