import asyncio

import pytest

from pbcoin.block import Block
from pbcoin.blockchain import BlockChain
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.mempool import Mempool
from pbcoin.mine import Mine
from pbcoin.netbase import Addr, ConnectionCode, Message
from pbcoin.network import Node
from pbcoin.process_handler import ProcessingHandler
from pbcoin.wallet import Wallet

class TestNetworkBase:
    BASE_IP = '127.0.0'
    SENDER_IP = f'{BASE_IP}.1'
    RECEIVER_IP = f'{BASE_IP}.2'
    PORT = 8989

    @pytest.fixture
    async def run_nodes(self, request):
        """it runs n nodes that n come from request param then save nodes and
        tasks (that is runners of nodes as async) in self.nodes and self.tasks.
        also, adds the close function of nodes in the finalizer that will be run
        after doing each test
        """
        self.__class__.nodes = []
        for i in range(request.param):
            addr = Addr(ip=f"{self.BASE_IP}.{i+1}",
                        port=self.PORT,
                        pub_key=f"0x2{i+1}")  # TODO: make a valid public key with Key class
            blockchain = BlockChain([])
            unspent_coins = dict()
            wallet = Wallet()
            proc_handler = ProcessingHandler(blockchain, unspent_coins, wallet)
            node = Node(addr, proc_handler, 1)
            self.nodes.append(node)
        self.__class__.tasks = []
        for node in self.nodes:
            task = asyncio.create_task(node.listen())
            self.tasks.append(task)
            if node.addr.ip == self.SENDER_IP:
                continue
            #! TODO: find a better way
            #! just use for waiting process message by receiver and then check out things
            await asyncio.sleep(0.4)
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
                # TODO: better check neighbors when neighbors is more than TOTAL_NUMBER_CONNECTIONS
                assert node.neighbors.items() <= actual_neighbors(node.addr).items()
        return check

    @pytest.mark.parametrize("run_nodes", [2], ids=["two nodes"], indirect=True)
    async def test_is_up_and_interactable(self, run_nodes):
        """run 2 nodes and check they connected or not"""
        sender = self.nodes[0]
        receiver = self.nodes[1]
        request = Message(True, ConnectionCode.PING, sender.addr)
        try:
            rec = await sender.connect_and_send(receiver.addr,
                                                request.create_message(sender.addr),
                                                wait_for_receive=True)
            assert rec != None and rec != b'', "Bad response"
            assert Message.from_str(rec.decode()).status, "Could not response request"
        except ConnectionError:
            assert False, "Could not connect to receiver"
        except Exception:
            assert False, "Bad response"

    
    @pytest.mark.parametrize(
        "run_nodes", [2, 4], ids = ["two nodes", "four nodes"], indirect = True
    )
    async def test_find_neighbors_more_total_connection_nodes(self, run_nodes, actual_neighbors):
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

class TestHandlerMessage(TestNetworkBase):
    @pytest.fixture(scope="class", autouse=True)
    def set_difficulty(self):
        import pbcoin.config as conf
        conf.settings.update({"difficulty": (2 ** 512 - 1) >> (2)})
    
    @pytest.mark.parametrize("run_nodes", [2], ids=["two nodes"], indirect=True)
    async def test_handling_mined_block(self, run_nodes):
        new_block = Block("", 1)
        mem = Mempool()
        sender = self.nodes[0]
        receiver = self.nodes[1]
        miner = Mine(sender.proc_handler.blockchain, sender.proc_handler.wallet, mem)
        await miner.mine(setup_block=new_block, send_network=False)
        await sender.send_mined_block(new_block)
        #! TODO: find a better way ()
        #! just use for waiting process message by receiver and then check out things
        await asyncio.sleep(0.2)
        # assertions
        assert receiver.proc_handler.blockchain.height == 1, "Didn't received mined block"
        assert receiver.proc_handler.blockchain.last_block == new_block, "Received block is not same with mined block"

    @pytest.mark.parametrize("run_nodes", [2], ids=["two nodes"], indirect=True)
    async def test_handling_bad_mined_block(self, run_nodes):
        new_block = Block("Bluh", 1)
        mem = Mempool()
        sender = self.nodes[0]
        receiver = self.nodes[1]
        miner = Mine(sender.proc_handler.blockchain, sender.proc_handler.wallet, mem)
        await miner.mine(setup_block=new_block, send_network=False)
        await sender.send_mined_block(new_block)
        await sender.send_mined_block(new_block)
        #! TODO: find a better way ()
        #! just use for waiting process message by receiver and then check out things
        await asyncio.sleep(0.2)
        # assertion
        assert receiver.proc_handler.blockchain.height == 0, "it received bad mined block"

    @pytest.mark.parametrize("run_nodes", [2], ids=["two nodes"], indirect=True)
    async def test_resolving_blockchain(self, run_nodes):
        mem = Mempool()
        sender = self.nodes[0]
        receiver = self.nodes[1]
        new_block = Block("", 1)
        sender_miner = Mine(sender.proc_handler.blockchain,
                            sender.proc_handler.wallet, mem)
        receiver_miner = Mine(receiver.proc_handler.blockchain,
                              receiver.proc_handler.wallet, mem)
        await sender_miner.mine(setup_block=new_block, send_network=False)
        await receiver_miner.mine(setup_block=new_block, send_network=False)
        odd_block = Block(new_block.__hash__, 2)
        await sender_miner.mine(setup_block=odd_block, send_network=False)
        last_two_blocks = sender_miner.blockchain.get_last_blocks(2)
        message = Message(True,
                    ConnectionCode.MINED_BLOCK,
                    receiver.addr,
                    {"block": [block.get_data() for block in last_two_blocks]})
        await sender.connect_and_send(receiver.addr,
                                      message.create_message(sender.addr),
                                      False)
        # assertions
        assert(receiver.proc_handler.blockchain.height == 2,
               "Didn't received new block or didn't resolve new blockchain")
        assert(receiver.proc_handler.blockchain.last_block == odd_block,
               "Last Resolved block is not same with mined block")
