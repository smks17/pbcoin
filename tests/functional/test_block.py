from datetime import datetime

import pytest

from pbcoin.block import Block, BlockValidationLevel
import pbcoin.config as conf
from pbcoin.trx import Trx, Coin


class TestBlock:
    @pytest.fixture
    def setUp_chain_trx(self, request):
        """make n blocks with n transactions that from previous transaction's block"""
        self.test_blocks: list[Block] = []
        self.all_trx: list[Trx] = []
        self.unspent_coins: dict[str, Coin] = dict()
        for i in range(request.param):
            if i == 0:
                new_block = Block("", i+1)
            else:
                new_block = Block(self.test_blocks[-1].__hash__, i+1)
            if i == 0:
                new_trx = Trx(1, f"owner{i}", [], [Coin(f"owner{i+1}", 0)])
            else:
                new_trx = Trx(1, f"owner{i}", self.all_trx[-1].outputs, [Coin(f"owner{i+1}", 0)])
            self.all_trx.append(new_trx)
            new_block.add_trx(new_trx)
            self.test_blocks.append(new_block)

    def test_add_transaction(self):
        """test adding a transaction to a block"""
        block = Block("", 1)
        temp_owner_key = "0x222"
        temp_trx = Trx(1, temp_owner_key, [], [Coin(temp_owner_key, 0)])
        block.add_trx(temp_trx)
        assert block.transactions[0].outputs[0].created_trx_hash == temp_trx.__hash__, \
            "Problem in output coin created_trx_hash value"
        assert temp_trx.__hash__ in block.get_list_hashes_trx(), \
            "Problem in no added new transaction to the block or"  \
            "bad block_hash assign for transaction data"

    @pytest.mark.parametrize("setUp_chain_trx", [1, 2, 3], indirect=True)
    def test_update_unspent_coins(self, setUp_chain_trx):
        """test update unspent coins for 1, 2, 3 transactions"""
        unspent_coins = dict()
        for block in self.test_blocks:
            block.update_outputs(unspent_coins)
        assert unspent_coins == {self.all_trx[-1].__hash__: self.all_trx[-1].outputs}, \
            "Problem in update the unspent coin from transactions"

    @pytest.mark.parametrize("setUp_chain_trx", [1, 2, 3], indirect=True)
    def test_validation_block_transactions(self, setUp_chain_trx):
        """test checking validation of transactions for 1, 2, 3 transactions"""
        unspent_coins = dict()
        for block in self.test_blocks:
            assert block.check_trx(unspent_coins), "Problem in validation of transaction"
            block.update_outputs(unspent_coins)

    @pytest.mark.parametrize("setUp_chain_trx", [2], indirect=True)
    def test_bad_input_coin_in_block_transaction(self, setUp_chain_trx):
        unspent_coins = dict()
        for i, block in enumerate(self.test_blocks):
            if i == (len(self.test_blocks) - 1):
                block.transactions[0].inputs[0].trx_hash = ""  # destroy input coin
                assert not (block.check_trx(self.unspent_coins)), \
                    "Problem in return True for bad input coin of a transaction"
            block.update_outputs(unspent_coins)

    @pytest.mark.parametrize("setUp_chain_trx", [2], indirect=True)
    def test_bad_value_coin_in_block_transaction(self, setUp_chain_trx):
        block = self.test_blocks[-1]
        block.transactions[0].inputs[0].value += 10  # destroy value coin
        assert not (block.check_trx(self.unspent_coins)), \
            "Problem in return True for bad value coin of a transaction"

    @pytest.mark.parametrize("setUp_chain_trx", [2], indirect=True)
    def test_bad_time_coin_in_block_transaction(self, setUp_chain_trx):
        block = self.test_blocks[-1]
        block.transactions[0].time = datetime(2021, 1, 1).timestamp()  # set a bad time
        assert not (block.check_trx(self.unspent_coins)), \
            "Problem in return True for bad time of a transaction"

    @pytest.mark.parametrize("setUp_chain_trx", [2], indirect=True)
    def test_is_valid_block(self, setUp_chain_trx):
        last_block = self.test_blocks[-1]
        new_block = Block(last_block.previous_hash, len(self.test_blocks) + 1)
        pre_hash = self.test_blocks[-2].__hash__
        validation = new_block.is_valid_block(self.unspent_coins, pre_hash=pre_hash, difficulty=conf.settings.glob.difficulty)
        all = BlockValidationLevel.ALL(except_validations=BlockValidationLevel.DIFFICULTY)
        assert validation == all

    @pytest.mark.parametrize("setUp_chain_trx", [2], indirect=True)
    def test_is_not_valid_block(self, setUp_chain_trx):
        block = self.test_blocks[-1]
        block.transactions[0].inputs[0].value += 10
        assert block.is_valid_block(
            self.unspent_coins, pre_hash=self.test_blocks[-2].__hash__
        ) != BlockValidationLevel.ALL()
