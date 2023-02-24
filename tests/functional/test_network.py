import asyncio

import pytest

from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.netbase import Addr, ConnectionCode, Message
from pbcoin.network import Node
from pbcoin.process_handler import ProcessingHandler


class TestNetworkBase:
    BASE_IP = '127.0.0'
    SENDER_IP = f'{BASE_IP}.1'
    RECEIVER_IP = f'{BASE_IP}.2'
    PORT = 8989
    MAX_WORKERS = 6

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
            proc_handler = ProcessingHandler()
            node = Node(addr, proc_handler)
            self.nodes.append(node)
        self.__class__.tasks = []
        for node in self.nodes:
            task = asyncio.create_task(node.listen())
            self.tasks.append(task)
            if node.addr.ip == self.SENDER_IP:
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
