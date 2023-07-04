from copy import deepcopy
from time import sleep
from typing import List

import pytest

from pbcoin.block import Block
from pbcoin.blockchain import BlockChain
from pbcoin.trx import Coin, Trx


class TestBlockchain:
    DIFFICULTY = (2 ** 512 - 1) >> (2)

    @pytest.fixture
    def setup_blockchains(self, request):
        """make n blockchain from request param and result save in self.blockchains

        param
        -----
        n_blockchains: int
            how many blockchains should be made
        n_same_blocks int
            it is for number of first blocks that in both blockchains are same
        n_parallel_blocks: Tuple[int]:
            it is a tuple in which the first element is for the number of
            the last blocks in the first blockchain that is different from
            the other blockchain and the second for the second blockchain
        """
        n_blockchains, n_same_blocks, n_parallel_blocks = request.param
        blocks: List[List[Block]] = []
        temp_blocks: List[Block] = []
        for i in range(n_same_blocks):
            pre_hash = ""
            if i != 0:
                pre_hash = temp_blocks[-1].__hash__
            temp_blocks.append(Block(pre_hash, i+1))
            while True:
                temp_blocks[-1].set_mined()
                if int(temp_blocks[-1].calculate_hash(), 16) <= self.DIFFICULTY:
                    break
                temp_blocks[-1].set_nonce(temp_blocks[-1].nonce+1)
        for i in range(n_blockchains):
            blocks.append(deepcopy(temp_blocks))

        for index, n_blocks in enumerate(n_parallel_blocks):
            for i in range(n_blocks):
                blockchain = blocks[index]
                if len(blockchain) == 0:
                    pre_hash = ""
                    height = 1
                else:
                    pre_hash = blockchain[-1].__hash__
                    height = blockchain[-1].block_height + 1
                blockchain.append(Block(pre_hash, height))
                while True:
                    blockchain[-1].set_mined()
                    if int(blockchain[-1].calculate_hash(), 16) <= self.DIFFICULTY:
                        break
                    blockchain[-1].set_nonce(blockchain[-1].nonce+1)
            sleep(0.001)
        self.blockchains = []
        for i in range(n_blockchains):
            self.blockchains.append(BlockChain(blocks[i]))

    @pytest.mark.parametrize(
        "setup_blockchains",
        [(1, 3, (0,))],
        ids=["one blockchain with 3 blocks"],
        indirect = True
    )
    def test_blockchain_checker(self, setup_blockchains):
        res = BlockChain.check_blockchain(self.blockchains[0].blocks, {}, self.DIFFICULTY)
        assert res == (True, None)

    @pytest.mark.parametrize("setup_blockchains", [(1, 3, (0,))], indirect = True)
    def test_bad_hash_blockchain_block_checker(self, setup_blockchains):
        self.blockchains[0].last_block.block_hash = hex(self.DIFFICULTY + 2)
        res = BlockChain.check_blockchain(self.blockchains[0].blocks, {}, self.DIFFICULTY)
        assert res == (False, 2)

    @pytest.mark.parametrize("setup_blockchains", [(1, 3, (0,))], indirect = True)
    def test_bad_previous_hash_blockchain_block_checker(self, setup_blockchains):
        self.blockchains[0].blocks[1].previous_hash = "0"
        res = BlockChain.check_blockchain(self.blockchains[0].blocks, {}, self.DIFFICULTY)
        assert res == (False, 1)

    @pytest.mark.parametrize("setup_blockchains", [(1, 3, (0,))], indirect = True)
    def test_bad_trx_hash_blockchain_block_checker(self, setup_blockchains):
        self.blockchains[0].blocks[1].add_trx(
            Trx(2, "owner", [Coin("owner1", 0)], [Coin("owner2", 0, value_=20)]))
        pre_hash = self.blockchains[0].blocks[1].calculate_hash()
        self.blockchains[0].blocks[1].previous_hash = pre_hash
        res = BlockChain.check_blockchain(self.blockchains[0].blocks, {}, self.DIFFICULTY)
        assert res == (False, 1)

    @pytest.mark.parametrize(
        "setup_blockchains",
        [
            # case 1: parallel
            # chain1: A-B-C-D
            # chain2: A-E-F
            (2, 1, (2, 3)),
            (2, 2, (2, 5)),
            # case 2: part_different
            # chain1: A-B-C
            # chain2: A-B
            (2, 2, (0, 1)),
            (2, 1, (0, 5)),
            # case 3: fully_different
            # chain1: A-B
            # chain2: C-D
            (2, 0, (0, 1)),
            (2, 0, (2, 5)),
        ],
        ids=[
            'parallel 1', 'parallel 2',
            'part_different 1', 'part_different 2',
            'fully_different 1 ', 'fully_different 2'
        ],
        indirect=True
    )
    def test_resolve(self, setup_blockchains):
        res = self.blockchains[0].resolve(self.blockchains[1].blocks, {}, self.DIFFICULTY)
        assert res == (True, None), \
            "Problem in resolve blockchain"
        assert self.blockchains[0].blocks == self.blockchains[1].blocks, \
            "Problem in blocks added after resolve"

    @pytest.mark.parametrize(
        "setup_blockchains",
        [(2, 1, (1, 2)), (2, 0, (3, 3))],
        indirect=True
    )
    def test_do_not_resolve_bad_chain(self, setup_blockchains):
        last_block = self.blockchains[1].blocks[-1]
        last_block.previous_hash = "nonsense"  # bad previous hash
        result = self.blockchains[0].resolve(self.blockchains[1].blocks, {}, self.DIFFICULTY)
        assert (False, 2) == result, "Problem in checking other blockchain for resolving"
        assert self.blockchains[0].blocks != self.blockchains[1].blocks, \
            "Problem in blocks added after resolve"

    def test_last_block(self):
        chain = BlockChain([])
        assert chain.last_block is None, "Last block in empty blockchain is not None"
        assert chain.height == 0, "height of empty blockchain is not 0"
        chain.add_new_block(Block("", 1), {}, ignore_validation=True)
        chain.blocks[0].set_mined()
        assert chain.last_block == chain.blocks[0], "Last block in blockchain is not correct"
        assert chain.height == 1, "height of block in blockchain is not correct"
