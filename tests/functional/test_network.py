import asyncio
from copy import deepcopy
import os

import pytest

from pbcoin.block import Block
from pbcoin.blockchain import BlockChain
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.mempool import Mempool
from pbcoin.mine import Mine
from pbcoin.netmessage import ConnectionCode, Errno, Message
from pbcoin.network import Node
from pbcoin.process_handler import ProcessingHandler
from pbcoin.trx import Trx
from pbcoin.utils.netbase import Addr
from pbcoin.wallet import Wallet


class TestNetworkBase:
    BASE_IP = '127.0.0'
    SENDER_IP = f'{BASE_IP}.1'
    RECEIVER_IP = f'{BASE_IP}.2'
    PORT = 8989

    @pytest.fixture
    async def run_nodes(self, request):
        """it runs n nodes that n come from request param also request has
        neighbor_finding for run or not start up for each node to find neighbors
        then save nodes and tasks (that is runners of nodes as async) in self.nodes
        and self.tasks Also, adds the close function of nodes in the finalizer
        that will be run after doing each test
        """
        self.__class__.nodes = []
        n, neighbor_finding = request.param
        for i in range(n):
            addr = Addr(ip=f"{self.BASE_IP}.{i+1}",
                        port=self.PORT,
                        pub_key=f"0x2{i+1}")  # TODO: make a valid public key with Key class
            blockchain = BlockChain([])
            unspent_coins = dict()
            wallet = Wallet(path_secret_key=os.environ["KEY_PATH"])
            mempool = Mempool()
            proc_handler = ProcessingHandler(blockchain, unspent_coins, wallet, mempool)
            node = Node(addr, proc_handler, 1)
            self.nodes.append(node)
        self.__class__.tasks = []
        for node in self.nodes:
            task = asyncio.create_task(node.listen())
            self.tasks.append(task)
            if not neighbor_finding or node.addr.ip == self.SENDER_IP:
                continue
            await node.start_up([f"{self.SENDER_IP}:{self.PORT}"], False)

        def close_nodes():
            for node in self.nodes:
                node.close()
            for task in self.tasks:
                task.cancel()
            self.tasks = []
        request.addfinalizer(close_nodes)


class TestMakeConnection(TestNetworkBase):
    @pytest.fixture
    def actual_neighbors(self):
        def actual(addr):
            data = dict()
            for node in self.nodes:
                if node.addr != addr:
                    data[node.addr.pub_key] = node.addr
            return data
        return actual

    @pytest.fixture
    def check_neighbors(self, actual_neighbors):
        def check():
            for node in self.nodes:
                assert len(node.neighbors) <= TOTAL_NUMBER_CONNECTIONS
                actual_len_neighbors = ((len(self.nodes) - 1)
                                        if (len(self.nodes)-1) <= TOTAL_NUMBER_CONNECTIONS
                                        else TOTAL_NUMBER_CONNECTIONS)
                assert len(node.neighbors) == actual_len_neighbors, f"{node.addr.hostname}"
                # TODO: better check neighbors when neighbors is more than CAPACITY
                assert node.neighbors.items() <= actual_neighbors(node.addr).items()
        return check

    @pytest.mark.parametrize(
        "run_nodes", [(2, False)], ids = ["two nodes"], indirect = True
    )
    async def test_is_up_and_interactable(self, run_nodes):
        """run 2 nodes and check they connected or not"""
        sender = self.nodes[0]
        receiver = self.nodes[1]
        assert await sender.send_ping_to(receiver.addr), "Could not make connection!"

    @pytest.mark.parametrize(
        "run_nodes", [(2, False)], ids = ["two nodes"], indirect = True
    )
    async def test_return_bad_message(self, run_nodes):
        """run 2 nodes and check they connected or not"""
        sender = self.nodes[0]
        receiver = self.nodes[1]
        message_res = await sender.connect_and_send(receiver.addr, b"Bluh", True)
        message_res = Message.from_str(message_res.decode())
        assert (not message_res.status) and (message_res.type_ == Errno.BAD_MESSAGE),  \
            "Other node hasn't understood that the message is wrong!"

    #! TODO: Handling four neighbors unittest should be implemented with
    #! the process or thread to run each node to avoid deadlock in async/await
    @pytest.mark.parametrize(
        "run_nodes", [(2, True)], ids = ["two nodes"], indirect = True
    )
    async def test_find_neighbors_more_total_connection_nodes(self,
                                                              run_nodes,
                                                              actual_neighbors):
        """run 2 and 4 nodes and check they handle neighbors even if more than
        total number connections for each nodes"""
        for node in self.nodes:
            assert len(node.neighbors) <= TOTAL_NUMBER_CONNECTIONS
            actual_len_neighbors = ((len(self.nodes) - 1)
                                    if (len(self.nodes)-1) <= TOTAL_NUMBER_CONNECTIONS
                                    else TOTAL_NUMBER_CONNECTIONS)
            assert len(node.neighbors) == actual_len_neighbors, f"{node.addr.hostname}"
            # TODO: better check neighbors when neighbors is more than TOTAL_NUMBER_CONNECTIONS
            assert node.neighbors.items() <= actual_neighbors(node.addr).items()


class TestProcessingHandler(TestNetworkBase):
    DIFFICULTY = (2 ** 256 - 1) >> 2

    @pytest.fixture(scope="class", autouse=True)
    def set_difficulty(self):
        import pbcoin.config as conf
        conf.settings.update({"difficulty": self.DIFFICULTY})

    @pytest.fixture
    def mine_some_blocks(self):
        async def inner(n_mine: int, node: Node, send_mined_block=False, subsidies=None):
            """try to mine n blocks (n_mine) for the node and if send_mined_block is True
            then send minded blocks too. Also it returns blocks and if send_mined_block is
            True, returns errors too.
            """
            miner = Mine(node.proc_handler.blockchain,
                         node.proc_handler.wallet,
                         Mempool())
            blocks = []
            errors = []
            for n in range(n_mine):
                pre_hash = ""
                if n != 0:
                    pre_hash = blocks[-1].__hash__
                if subsidies is not None and len(subsidies) > n:
                    new_block = Block(pre_hash, n+1, subsidies[n])
                else:
                    new_block = Block(pre_hash, n+1)
                await miner.mine(setup_block=new_block,
                                 unspent_coins=node.proc_handler.unspent_coins,
                                 send_network=False)
                if send_mined_block:
                    errors += await node.send_mined_block(new_block)
                blocks.append(new_block)
            if send_mined_block:
                return blocks, errors
            else:
                return blocks
        return inner

    @pytest.mark.parametrize("run_nodes", [(2, True)], ids=["two nodes"], indirect=True)
    async def test_handling_mined_block(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        blocks, errors = await mine_some_blocks(1, sender, True)
        receiver = self.nodes[1]
        # assertions
        assert errors == [], "Mined block probably wrong"
        assert receiver.proc_handler.blockchain.height == 1,  \
               "Didn't received mined block"
        assert receiver.proc_handler.blockchain.last_block == blocks[-1],  \
               "Received block is not same with mined block"

    @pytest.mark.parametrize("run_nodes", [(2, True)], ids=["two nodes"], indirect=True)
    async def test_handling_misplace_mined_block(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        blocks = await mine_some_blocks(2, sender, False)
        receiver = self.nodes[1]
        errors = await sender.send_mined_block(blocks[-1])
        # assertions
        assert errors == [], "Mined block probably wrong"
        assert receiver.proc_handler.blockchain.height == 2,  \
               "Didn't received mined block"
        assert receiver.proc_handler.blockchain.blocks == blocks,  \
               "Received block is not same with mined block"

    @pytest.mark.parametrize("run_nodes", [(2, True)], ids=["two nodes"], indirect=True)
    async def test_handling_bad_mined_block(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        blocks = await mine_some_blocks(1, sender, False)
        blocks[0].block_hash = hex(self.DIFFICULTY + 1)
        receiver = self.nodes[1]
        errors = await sender.send_mined_block(blocks[0])
        # assertion
        assert len(errors) != 0
        assert receiver.proc_handler.blockchain.height == 0, \
               "it received bad mined block"

    @pytest.mark.parametrize("run_nodes", [(2, False)], ids=["two nodes"], indirect=True)
    async def test_resolving_blockchain(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        receiver = self.nodes[1]
        sender_blocks = await mine_some_blocks(2, sender, False)
        _ = await mine_some_blocks(1, receiver, False)
        message = Message(True,
                          ConnectionCode.RESOLVE_BLOCKCHAIN,
                          receiver.addr,
                          {"blocks": [block.get_data() for block in sender_blocks]})
        rec = await sender.connect_and_send(receiver.addr,
                                            message.create_message(sender.addr),
                                            True)
        # assertions
        assert Message.from_str(rec.decode()).status, "Could not resolve"
        assert receiver.proc_handler.blockchain.height == 2, \
               "Didn't received new block or didn't resolve new blockchain"
        assert receiver.proc_handler.blockchain.last_block == sender_blocks[-1], \
               "Last Resolved block is not same with mined block"

    @pytest.mark.parametrize("run_nodes", [(2, False)], ids=["two nodes"], indirect=True)
    async def test_get_blocks_with_hash(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]  # send the blocks
        receiver = self.nodes[1]  # receive the blocks
        sender_blocks = await mine_some_blocks(2, sender, False)
        first_block = sender_blocks[0]
        message = Message(True,
                          ConnectionCode.GET_BLOCKS,
                          sender.addr,
                          {"hash_block": first_block.__hash__})
        response = await sender.connect_and_send(sender.addr,
                                                 message.create_message(receiver.addr),
                                                 True)
        response = Message.from_str(response.decode())
        # assertions
        assert (response.status is True
               and response.type_ == ConnectionCode.SEND_BLOCKS), \
               "Doesn't send proper message prototype"
        response_blocks = [Block.from_json_data_full(block)
                           for block in response.data["blocks"]]
        assert sender_blocks == response_blocks, "Didn't received correct blocks"

    @pytest.mark.parametrize("run_nodes", [(2, False)], ids=["two nodes"], indirect=True)
    async def test_get_blocks_with_bad_hash(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]  # send the blocks
        receiver = self.nodes[1]  # receive the blocks
        _ = await mine_some_blocks(2, sender, False)
        message = Message(True,
                          ConnectionCode.GET_BLOCKS,
                          sender.addr,
                          {"hash_block": "Bluh"})
        response = await sender.connect_and_send(sender.addr,
                                                 message.create_message(receiver.addr),
                                                 True)
        response = Message.from_str(response.decode())
        # assertions
        assert response.status is False \
               and response.type_ == Errno.BAD_BLOCK_VALIDATION, \
               "Sends the blocks for bad hash"

    @pytest.mark.parametrize("run_nodes", [(2, False)], ids=["two nodes"], indirect=True)
    async def test_get_blocks_with_index(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]  # send the blocks
        receiver = self.nodes[1]  # receive the blocks
        sender_blocks = await mine_some_blocks(2, sender, False)
        message = Message(True,
                          ConnectionCode.GET_BLOCKS,
                          sender.addr,
                          {"first_index": 0})
        response = await sender.connect_and_send(sender.addr,
                                                 message.create_message(receiver.addr),
                                                 True)
        response = Message.from_str(response.decode())
        # assertions
        assert (response.status is True
               and response.type_ == ConnectionCode.SEND_BLOCKS),  \
               "Doesn't send proper message prototype"
        response_blocks = [Block.from_json_data_full(block)
                           for block in response.data["blocks"]]
        assert sender_blocks == response_blocks, "Didn't received correct blocks"

    @pytest.mark.parametrize("run_nodes", [(2, False)], ids=["two nodes"], indirect=True)
    async def test_get_bad_blocks_with_index(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]  # send the blocks
        receiver = self.nodes[1]  # receive the blocks
        _ = await mine_some_blocks(2, sender, False)
        message = Message(True,
                          ConnectionCode.GET_BLOCKS,
                          sender.addr,
                          {"first_index": 1000})
        response = await sender.connect_and_send(sender.addr,
                                                 message.create_message(receiver.addr),
                                                 True)
        response = Message.from_str(response.decode())
        # assertions
        assert response.status is False \
               and response.type_ == Errno.BAD_BLOCK_VALIDATION, \
               "Sends the blocks for bad index"

    @pytest.mark.parametrize("run_nodes", [(2, True)], ids=["two nodes"], indirect=True)
    async def test_handling_new_trx(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        receiver = self.nodes[1]
        wallet = sender.proc_handler.wallet
        blockchain = sender.proc_handler.blockchain
        subsidy = Trx(blockchain.height, wallet.public_key)
        await mine_some_blocks(1, sender, True, [subsidy])
        wallet.updateBalance(deepcopy(blockchain.last_block.transactions))
        value = 25
        new_trx = None
        errors = []
        if value <= wallet.n_amount:
            new_trx = Trx.make_trx(sum(list(wallet.out_coins.values()), []),
                                   wallet.public_key, receiver.addr.pub_key, 25)
            mempool = sender.proc_handler.mempool
            result = mempool.add_new_transaction(new_trx,
                                                 wallet.sign(new_trx),
                                                 wallet.public_key,
                                                 sender.proc_handler.unspent_coins)
            assert result
            errors = await sender.send_new_trx(new_trx, wallet)
        assert errors == [], f"We have some errors in handling new trx: {errors}"
        assert receiver.proc_handler.mempool.is_exist(new_trx.hash_trx),  \
               "Didn't received new trx in mempool"

    @pytest.mark.parametrize("run_nodes", [(2, True)], ids=["two nodes"], indirect=True)
    async def test_handling_bad_new_trx(self, run_nodes, mine_some_blocks):
        sender = self.nodes[0]
        receiver = self.nodes[1]
        wallet = sender.proc_handler.wallet
        blockchain = sender.proc_handler.blockchain
        subsidy = Trx(blockchain.height, wallet.public_key)
        await mine_some_blocks(1, sender, True, [subsidy])
        wallet.updateBalance(deepcopy(blockchain.last_block.transactions))
        value = 25
        new_trx = None
        errors = []
        if value <= wallet.n_amount:
            new_trx = Trx.make_trx(sum(list(wallet.out_coins.values()), []),
                                   wallet.public_key, receiver.addr.pub_key, 25)
            new_trx.inputs[0].value += 1  # corrupting
            mempool = sender.proc_handler.mempool
            result = mempool.add_new_transaction(new_trx,
                                                 wallet.sign(new_trx),
                                                 wallet.public_key,
                                                 sender.proc_handler.unspent_coins)
            assert not result, "Could not add new trx in mempool"
            errors = await sender.send_new_trx(new_trx, wallet)
        assert len(errors) != 0, "We haven't catch errors in handle new bad trx"
        assert receiver.proc_handler.mempool.is_exist(new_trx.hash_trx) is False,  \
               "Didn't received new trx in mempool"
