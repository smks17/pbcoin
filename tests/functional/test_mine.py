import os
import pytest

import pbcoin.config as conf
from pbcoin.block import Block, BlockValidationLevel
from pbcoin.blockchain import BlockChain
from pbcoin.mempool import Mempool
from pbcoin.mine import Mine
from pbcoin.trx import Coin, Trx
from pbcoin.wallet import Wallet


class TestTrx:
    @pytest.fixture
    async def mine_some_blocks(self, request):
        n = request.param
        blockchain = []
        self.unspent_coins = {}
        miner = Mine(blockchain, None, Mempool(), None)
        for i in range(n):
            pre_hash = ""
            if len(blockchain) > 0:
                pre_hash = blockchain[-1].__hash__
            new_block = Block(pre_hash, i+1, Trx(1, "miner"))
            await miner.mine(new_block, difficulty=conf.settings.glob.difficulty)
        self.__class__.blockchain = BlockChain(blockchain)
        last_block = self.__class__.blockchain.last_block
        assert self.__class__.blockchain.height > 0, "Didn't mine anything"
        assert self.__class__.blockchain.last_block is not None, \
               "Didn't save the mined block"
        assert last_block.block_height == n

    @pytest.mark.parametrize("mine_some_blocks", [1, 2], indirect=True)
    async def test_mine_some_block(self, mine_some_blocks):
        """just test mine a valid block or not (with no extra transactions)"""
        result = BlockChain.check_blockchain(self.blockchain.blocks, {}, conf.settings.glob.difficulty)
        assert result == (True, None, BlockValidationLevel.ALL())

    async def test_mine_with_transaction(self):
        """this function mine 3 blocks and check all possible of transactions getting
        from mempool
        """
        # init objects
        blockchain = BlockChain()
        wallet = Wallet(path_secret_key=os.environ["KEY_PATH"])
        mempool = Mempool()
        miner = Mine(blockchain, None, mempool, None)
        unspent_coins = dict()

        # mine one block with no transaction
        new_block = blockchain.setup_new_block(Trx(1, wallet.public_key), mempool)
        await miner.mine(new_block, add_block=False, difficulty=conf.settings.glob.difficulty)
        blockchain.add_new_block(new_block,
                                 unspent_coins=unspent_coins,
                                 difficulty=conf.settings.glob.difficulty)
        # make a new transaction for testing mining one block
        new_trx = Trx(
            2,
            wallet.public_key,
            blockchain.last_block.transactions[-1].outputs,
            [Coin(wallet.public_key, 0, value_=30),
             Coin("fake1", 1, value_=20)]
        )
        # add new transaction to mempool and check it
        assert mempool.add_new_transaction(new_trx,
                                           wallet.sign(new_trx),
                                           wallet.public_key,
                                           unspent_coins), \
            "Could not add transaction to mempool because has bad validation"
        assert len(mempool.transactions) == 1, "Transaction didn't add to mempool"
        # update unspent coins for next block
        new_block.update_outputs(unspent_coins)

        # mine second block with new transaction and check it
        new_block = blockchain.setup_new_block(Trx(2, wallet.public_key), miner.mempool)
        await miner.mine(new_block, add_block=False, difficulty=conf.settings.glob.difficulty)
        blockchain.add_new_block(new_block,
                                 ignore_validation=True,
                                 unspent_coins=unspent_coins,
                                 difficulty=conf.settings.glob.difficulty)
        assert len(blockchain.blocks) == 2, "Could not Mine new block"
        last_block = blockchain.last_block
        assert len(last_block.transactions) == 2, "Transactions didn't add to mined block"
        # check transaction in mined block is same or not
        actual_outputs = [
            Coin(wallet.public_key, 0, last_block.get_list_hashes_trx()[1], 30),
            Coin('fake1', 1, last_block.get_list_hashes_trx()[1], 20),
        ]
        assert last_block.transactions[1].outputs == actual_outputs, "Bad output transaction"
        actual_inputs = [
            Coin(wallet.public_key, 0, blockchain.blocks[0].transactions[0].hash_trx, 50)
        ]
        assert last_block.transactions[1].inputs == actual_inputs, "Bad input transaction"
        assert len(miner.mempool) == 0, "Didn't delete mempool transaction that was mined"

        new_trx = [
            Trx(3,
                wallet.public_key,
                [blockchain.last_block.transactions[-1].outputs[0]],
                [Coin("fake2", 1, value_=30)]),
            Trx(3,
                wallet.public_key,
                [blockchain.last_block.transactions[-1].outputs[1]],
                [Coin("fake1", 1, value_=20)])
        ]
        mempool.max_limit_trx = 1
        # add new transaction to mempool and check it
        for trx in new_trx:
            assert mempool.add_new_transaction(trx,
                                               wallet.sign(trx),
                                               wallet.public_key,
                                               unspent_coins), \
                "Could not add transaction to mempool because has bad validation"
        assert len(mempool.transactions) == 2, "Transaction didn't add to mempool"

        # mine third block with new transaction and check it
        new_block = blockchain.setup_new_block(Trx(3, wallet.public_key), miner.mempool)
        await miner.mine(new_block, add_block=False, difficulty=conf.settings.glob.difficulty)
        blockchain.add_new_block(new_block, ignore_validation=True, difficulty=conf.settings.glob.difficulty)
        assert len(blockchain.blocks) == 3, "Could not Mine new block"
        last_block = blockchain.last_block
        assert len(last_block.transactions) == 2, "Transactions didn't add to mined block"
        # check transaction in third mined block is same or not
        actual_outputs = [
            Coin('fake2', 1, last_block.get_list_hashes_trx()[1], 30),
        ]
        assert last_block.transactions[1].outputs == actual_outputs, "Bad output transaction"
        actual_inputs = [
            Coin(wallet.public_key, 0, blockchain.blocks[1].transactions[1].hash_trx, 30)
        ]
        assert last_block.transactions[1].inputs == actual_inputs, "Bad input transaction"
        assert len(miner.mempool) == 1, \
            "Didn't delete mempool transaction that was mined or add all trx"
