import asyncio
import json

import pytest

from pbcoin.blockchain import BlockChain
from pbcoin.constants import TOTAL_NUMBER_CONNECTIONS
from pbcoin.mine import Mine
from pbcoin.net import Node, ConnectionCode
from pbcoin.wallet import Wallet


class TestNetworkBase:
    BASE_IP = '127.0.0'
    SENDER_IP = f'{BASE_IP}.1'
    RECEIVER_IP = f'{BASE_IP}.2'

    @pytest.fixture
    async def run_nodes(self, request):
        """it runs n nodes that n come from request param then save nodes and
        tasks (that is runners of nodes as async) in self.nodes and self.tasks.
        also, adds the close function of nodes in the finalizer that will be run
        after doing each test
        """
        self.__class__.nodes = []
        for i in range(request.param):
            blockchain = BlockChain([])
            wallet = Wallet()
            node = None
            miner = Mine(blockchain, wallet, node, [])
            node = Node(
                blockchain,
                wallet,
                miner,
                dict(),
                f"127.0.0.{i+1}", 8989
            )
            self.nodes.append(node)
        self.__class__.tasks = []
        for node in self.nodes:
            task = asyncio.create_task(node.listen())
            self.tasks.append(task)
            if node.ip == self.SENDER_IP:
                continue
            await node.start_up(["127.0.0.1:8989"], False)
        
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
        def actual(ip):
            data = dict()
            for node in self.nodes:
                if node.ip != ip:
                    data[node.uid] = (node.ip, node.port)
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
                assert len(node.neighbors) == actual_len_neighbors, f"{node.ip}"
                # TODO: better check neighbors when neighbors is more than TOTAL_NUMBER_CONNECTIONS
                assert node.neighbors.items() <= actual_neighbors(node.ip).items()
        return check

    @pytest.mark.parametrize("run_nodes", [2], ids=["two nodes"], indirect=True)
    async def test_is_up_and_interactable(self, run_nodes):
        """run 2 nodes and check they connected or not"""
        data = {
            "type": ConnectionCode.PING,
            "src_ip": self.SENDER_IP,
            "dst_ip": self.RECEIVER_IP
        }
        sender = self.nodes[0]
        rec = await sender.connect_and_send(
            self.RECEIVER_IP, 8989, json.dumps(data), wait_for_receive=True)
        assert rec != None and rec != b'', "Bad response"
        assert json.loads(rec.decode())["status"], "Could not response request"

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
            assert len(node.neighbors) == actual_len_neighbors, f"{node.ip}"
            # TODO: better check neighbors when neighbors is more than TOTAL_NUMBER_CONNECTIONS
            assert node.neighbors.items() <= actual_neighbors(node.ip).items()

# TODO: test functionally message handling