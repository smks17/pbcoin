from __future__ import annotations

import asyncio
import json
from copy import copy, deepcopy
from sys import getsizeof
from random import shuffle
from enum import IntEnum, auto
from hashlib import md5
from socket import *
from typing import (
    Any,
    Dict,
    List,
    NewType,
    Optional,
    Tuple,
    Union
)

from ellipticcurve.publicKey import PublicKey
from ellipticcurve.signature import Signature

from .block import Block
from .blockchain import BlockChain, BlockValidationLevel
from .config import NetworkCfg
from .constants import TOTAL_NUMBER_CONNECTIONS, NETWORK_DATA_SIZE
from .logger import getLogger
from .mempool import Mempool
from .trx import Coin, Trx
from .wallet import Wallet


logging = getLogger(__name__)

AsyncWriter = NewType("AsyncWriter", asyncio.StreamWriter)
AsyncReader = NewType("AsyncReader", asyncio.StreamReader)

class ConnectionCode(IntEnum):
    NEW_NEIGHBOR = auto()  # send information node as a new neighbors
    NEW_NEIGHBORS_REQUEST = auto()  # request some new nodes for neighbors
    NEW_NEIGHBORS_FIND = auto()  # declare find new neighbors ()
    NOT_NEIGHBOR = auto()  # not be neighbors anymore!
    MINED_BLOCK = auto()  # declare other nodes find a new block
    RESOLVE_BLOCKCHAIN = auto()  # for resolving blockchain of 2 nodes
    GET_BLOCKS = auto()  # request for get some blocks
    SEND_BLOCKS = auto()  # responds to GET_BLOCKS
    ADD_TRX = auto()  # new trx for add to mempool
    PING = auto()  # For pinging other nodes and check connection


class Node:
    """
    Attribute
    ---------
        ip: str
            the ip host
        port: int
            node port
        uid: str
            a uniq string for each node
        neighbors: Dict[str, Tuple[str, int]]
            list of neighbors for declaring mine block or mempool
    """

    def __init__(self, blockchain: BlockChain, wallet: Wallet, mempool: Mempool,
                unspent_coins: Dict[str, Coin], ip: str, port: int):
        self.ip = ip
        self.port = port
        if not self.ip:
            self.ip = NetworkCfg.ip
        if not self.port:
            self.prt = NetworkCfg.port
        self.uid = self.calculate_uid(ip, str(port))  # TODO: use public key
        self.neighbors: Dict[str, Tuple[str, int]] = dict()
        self.is_listening = False
        self.blockchain = blockchain
        self.wallet = wallet
        self.mempool = mempool
        self.unspent_coins = unspent_coins

    async def connect_to(
        self,
        dst_ip: str,
        dst_port: str
    ) -> Tuple[AsyncReader, AsyncWriter]:
        """make a connection to destination ip and port and return stream reader and writer"""
        try:
            reader, writer = await asyncio.open_connection(dst_ip, int(dst_port))
            logging.debug(f"from {self.ip} Connect to {dst_ip}:{dst_port}")
        except ConnectionError:
            logging.error("Error Connection", exc_info=True)
            raise ConnectionError
        return reader, writer

    async def connect_and_send(
        self,
        dst_ip: str,
        dst_port: int,
        data: str,
        wait_for_receive=True
    ) -> bytes:
        """
        make a connection to the destination ip and port then send data and close the connection
        
        Parameters
        ----------
            dst_ip: str
                the destination ip you want connect
            dst_port: int
                connect to which destination's port
            data: str
                data which you want to send
            wait_for_receive: bool:
                if True, wait for receive data from destination

        Returns
        -------
            bytes: if wait_for_receive is True, then it returns the data,
            otherwise, it returns an empty byte

        """
        rec_data = b''
        try:
            reader, writer = await self.connect_to(dst_ip, dst_port)
            if not await self.write(writer, data):
                return rec_data
            if wait_for_receive:
                size_data = await reader.read(NETWORK_DATA_SIZE)
                size_data = int(size_data)
                rec_data = await reader.read(size_data)
                logging.debug(
                    f'receive data from {dst_ip}:{dst_port} {rec_data.decode()}')
            writer.close()
            await writer.wait_closed()
        except ConnectionError:
            logging.error("Error Connection error", exc_info=True)
            raise ConnectionError
        except Exception as exception:
            logging.error(
                f"Problem in sending and receiving from {dst_ip}", exc_info=True)
        finally:
            return rec_data

    async def listen(self):
        """start listening requests from other nodes and callback handle_requests"""
        self.server = await asyncio.start_server(
            self.handle_requests, host=self.ip, port=self.port)
        if not self.server:
            raise ConnectionError
        logging.info(
            f"node connection is serve on {self.server.sockets[0].getsockname()}")
        async with self.server:
            try:
                self.is_listening = True
                await self.server.serve_forever()
            except:
                logging.error("Serving is broken")
            finally:
                # await self.server.wait_closed()
                self.is_listening = False

    async def write(self, writer: AsyncWriter, data: Union[str, bytes], flush=True) -> bool:
        """write data from writer to destination and if successfully return true
        otherwise return False
        """
        sizeof = lambda input_data : '{:>08d}'.format(getsizeof(input_data)).encode()

        if isinstance(data, str):
            data = data.encode()
        try:
            writer.write(sizeof(data))
            writer.write(data)
            if flush:
                await writer.drain()
        except:
            return False  # TODO: explain what err and log it and also callers handle err
        return True

    def reset(self, close=True):
        """delete its neighbors and is close is True close the listening"""
        self.neighbors = dict()
        if close:
            self.close()
            self.is_listening = False

    def close(self):
        """close the listening from other nodes"""
        if self.is_listening:
            self.server.close()
            self.is_listening = False

    async def handle_requests(self, reader: AsyncReader, writer: AsyncWriter):
        """ handle requests that receive from other nodes """
        size = int(await reader.read(NETWORK_DATA_SIZE))
        data = await reader.read(size)
        logging.debug(f'receive data: {data.decode()}')
        data = json.loads(data.decode())
        #TODO: check that request is from neighbors or not
        _type = data['type']
        if _type == ConnectionCode.NEW_NEIGHBOR:
            await self.handle_new_neighbor(data)
        elif _type == ConnectionCode.NEW_NEIGHBORS_REQUEST:
            await self.handle_request_new_node(data, writer)
        elif _type == ConnectionCode.NOT_NEIGHBOR:
            await self.handle_delete_neighbor(data, writer)
        elif _type == ConnectionCode.MINED_BLOCK:
            await self.handle_mined_block(data)
        elif _type == ConnectionCode.GET_BLOCKS:
            await self.handle_get_blocks(data, writer)
        elif _type == ConnectionCode.ADD_TRX:
            await self.handle_new_trx(data)
        elif _type == ConnectionCode.PING:
            await self.handle_ping(data, writer)
        else:
            raise NotImplementedError  # TODO
        writer.close()
        await writer.wait_closed()

    async def handle_new_neighbor(self, data: Dict[str, Any]):
        """ add new node to neighbors nodes """
        new_node_ip, new_node_port = data["new_node"].split(":")
        uid = data["uid"]
        self.neighbors[uid] = (new_node_ip, int(new_node_port))
        logging.info(f"new neighbor for {self.ip} : {new_node_ip}")

    async def handle_request_new_node(self, data: Dict[str, Any], writer: AsyncWriter):
        """handle a new node for add to the network by finding new neighbors for it"""
        final_request: Optional[Dict[str, any]] = None
        n_connections = data["number_connections_requests"]
        data["passed_nodes"].append(self.ip)
        final_request = {
            "status": True,
            "uid": self.uid,
            "type": ConnectionCode.NEW_NEIGHBORS_REQUEST,
            "src_ip": f'{self.ip}:{self.port}',
            "dst_ip": data["src_ip"],
            "number_connections_requests": n_connections,  # how many neighbors you want
            "p2p_nodes": data["p2p_nodes"],  # nodes that are util found
            # this request passes from what nodes for searching
            "passed_nodes": data["passed_nodes"]
        }
        # add the new neighbor to itself if its capacity neighbors are not filled yet
        if len(self.neighbors) < TOTAL_NUMBER_CONNECTIONS:
            n_connections -= 1
            final_request["number_connections_requests"] = n_connections
            final_request["p2p_nodes"].append(f"{self.ip}:{self.port}")
        # if still need new neighbors
        if n_connections != 0:
            # prepare message to send other nodes for search
            if final_request != None:
                new_request = final_request.copy()
            else:
                new_request = data.copy()
            new_request['src_ip'] = f'{self.ip}:{self.port}'
            for uid in list(self.neighbors):
                addr = self.neighbors.get(uid)
                if addr == None:
                    continue
                ip, port = addr
                # doesn't send data to the repetitious node then stuck in a loop
                if ip not in new_request['passed_nodes']:
                    new_request['dst_ip'] = ip
                    try:
                        response = await self.connect_and_send(ip, port, json.dumps(new_request))
                        final_request = json.loads(response.decode())
                        n_connections = final_request['number_connections_requests']
                    except ConnectionError:
                        # TODO: checking for connection that neighbor is online yet?
                        logging.error("", exc_info=True)
                if n_connections == 0:
                    break

        # resolve connections if can not find Any neighbors for it
        # delete own neighbor then we have 2 free connections for neighbors
        if n_connections == TOTAL_NUMBER_CONNECTIONS and len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS:
            neighbors_uid = list(self.neighbors.keys())
            shuffle(neighbors_uid)
            for uid in neighbors_uid:
                ip, port = self.neighbors[uid]
                request = {
                    "status": True,
                    "type": ConnectionCode.NOT_NEIGHBOR,
                    "dst_ip": ip,
                    "src_ip": f'{self.ip}:{self.port}',
                    "uid": self.uid
                }
                response = await self.connect_and_send(ip, port, json.dumps(request))
                response = json.loads(response.decode())
                if response['status'] == True:
                    self.neighbors.pop(uid, None)
                    logging.info(f"delete neighbor for {self.ip} : {ip}")
                    new_nodes = [f"{self.ip}:{self.port}", f"{ip}:{port}"]
                    final_request["p2p_nodes"] += new_nodes
                    final_request['number_connections_requests'] -= 2
                    break

        if final_request != None:
            final_request['src_ip'] = f'{self.ip}:{self.port}'
            final_request['type'] = ConnectionCode.NEW_NEIGHBORS_FIND
            if final_request['number_connections_requests'] == 0:
                final_request['status'] = True
            else:
                final_request['status'] = False
        else:
            raise NotImplementedError  # TODO

        # send the result
        bytes_data = json.dumps(final_request).encode()
        await self.write(writer, bytes_data)

    async def handle_delete_neighbor(self, data: Dict[str, Any], writer: AsyncWriter):
        """delete neighbor"""
        ip, port = data["src_ip"].split(':')
        uid = data["uid"]
        data = {
            "status": False,
            "dst_ip": ip,
            "src_ip": f'{self.ip}:{self.port}',
        }
        if len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS:
            self.neighbors.pop(uid, None)
            logging.info(f"delete neighbor for {self.ip} : {ip}")
            data['status'] = True
        bytes_data = json.dumps(data).encode()
        await self.write(writer, bytes_data, False)

    async def handle_mined_block(self, data: Dict[str, Any]):
        """handle for request finder new block"""
        block_data = data['block']
        logging.debug(f"mine block from {data['src_ip']}: {block_data}")
        block = Block.from_json_data_full(block_data)
        # checking which blockchain is longer, own or its?
        if block.block_height > self.blockchain.height:
            number_new_blocks = block.block_height - self.blockchain.height
            if number_new_blocks == 1:
                # just this block is new
                done = self.blockchain.add_new_block(block, self.unspent_coins)
                if done != BlockValidationLevel.ALL():
                    # TODO: send why receive data is a bad request
                    logging.error(f"Bad request mined block from {data['src_ip']} validation: {done}")
                else:
                    last = self.blockchain.last_block
                    last.update_outputs(self.unspent_coins)
                    self.wallet.updateBalance(deepcopy(last.transactions))
                    logging.info(f"New mined block from {data['src_ip']}")
                    logging.debug(
                        f"info mined block from {data['src_ip']}: {block.get_data()}")
            else:
                # request for get n block before this block for add to its blockchain and resolve
                request = {
                    "type": ConnectionCode.GET_BLOCKS,
                    "src_ip": f'{self.ip}:{self.port}',
                    "dst_ip": data['src_ip'],
                    "number_block": number_new_blocks
                }
                ip, port = data['src_ip'].split(':')
                res = await self.connect_and_send(ip, int(port), json.dumps(request))
                res = json.loads(res.decode())
                if res['status']:
                    blocks = res['blocks']
                    blocks = [Block.from_json_data_full(
                        block) for block in blocks]
                    result = self.blockchain.resolve(blocks, self.unspent_coins)
                    # TODO: send problem to node if result is False
                else:
                    # TODO
                    logging.error("Bad request send for get blocks")
        else:
            # TODO: current blockchain is longer so declare other for resolve that
            logging.error("Not implemented resolve shorter blockchain")
            pass

        logging.debug(f"new block chian: {self.blockchain.get_hashes()}")

    async def handle_get_blocks(self, data: Dict[str, Any], writer: AsyncWriter):
        """handle for request another node for getting block"""
        copy_blockchain = copy(self.blockchain)
        first_index: Optional[int] = None
        hash_block = data.pop('hash_block', None)
        if hash_block:
            first_index = copy_blockchain.search(hash_block)
        else:
            first_index = data.pop('first_index', None)
        if first_index == None:
            # doesn't have this specific chain
            logging.error("doesn't have self chain!")
        else:
            request = {
                "status": True,
                "type": ConnectionCode.SEND_BLOCKS,
                "src_ip": f'{self.ip}:{self.port}',
                "dst_ip": data['src_ip'],
                "blocks": copy_blockchain.get_data(first_index)
            }
            bytes_data = json.dumps(request).encode()
            await self.write(writer, bytes_data, False)

    async def handle_new_trx(self, data: Dict[str, Any]):
        data['passed_nodes'].append(self.ip)
        pubKey = PublicKey.fromString(data['public_key'])
        sig = Signature.fromBase64(data['signature'].encode())
        trx_data = data['trx']
        trx_inputs = trx_data['inputs']
        trx_outputs = trx_data['outputs']
        inputs = []
        outputs = []
        # make trx from receive data
        for in_coin in trx_inputs:
            inputs.append(Coin(
                in_coin["owner"], in_coin["index"], in_coin["trx_hash"], in_coin["value"]))
        for out_coin in trx_outputs:
            outputs.append(Coin(
                out_coin["owner"], out_coin["index"], out_coin["trx_hash"], out_coin["value"]))
        time = trx_data['time']
        new_trx = Trx(
            self.blockchain.height, self.wallet.public_key, inputs, outputs, time)
        # add to mempool and send other nodes
        if self.mempool.add_new_transaction(new_trx, self.blockchain.last_block,
                                            sig, pubKey, self.unspent_coins):
            for uid in self.neighbors:
                ip, port = self.neighbors[uid]
                if not ip in data['passed_nodes']:
                    msg = copy(data)
                    msg['src_ip'] = msg['dst_ip']
                    msg['dst_ip'] = ip
                    await self.connect_and_send(ip, port, json.dumps(msg), False)
        else:
            pass  # TODO

    async def handle_ping(self, data: Dict[str, Any], writer: AsyncWriter):
        bytes_data = json.dumps({
            "status": True,
            "src_ip": self.ip,
            "dst_ip": data["src_ip"],
        }).encode()
        await self.write(writer, bytes_data)

    async def start_up(self, seeds: List[str], get_blockchain = True):
        """begin to find new neighbors and connect to the blockchain network"""
        nodes = []
        for seed in seeds:
            ip, port = seed.split(':')
            port = int(port)
            request = {
                "status": True,
                "uid": self.uid,
                "type": ConnectionCode.NEW_NEIGHBORS_REQUEST,
                "src_ip": f'{self.ip}:{self.port}',
                "dst_ip": seed,
                # how many neighbors do you need
                "number_connections_requests": TOTAL_NUMBER_CONNECTIONS,
                "p2p_nodes": [],  # what nodes are found
                "passed_nodes": [self.ip]  # passes from what nodes
            }
            data = json.dumps(request)
            response = await self.connect_and_send(ip, port, data)
            response = json.loads(response.decode())
            nodes += response['p2p_nodes']
            # checking find all neighbors
            if (
                response['status'] == True
                and response['number_connections_requests'] == 0
                and response['type'] == ConnectionCode.NEW_NEIGHBORS_FIND
            ):
                break

        # sending found nodes for requesting neighbors
        for node in nodes:
            ip, port = node.split(":")
            request = {
                "status": True,
                "uid": self.uid,
                "type": ConnectionCode.NEW_NEIGHBOR,
                "src_ip": f'{self.ip}:{self.port}',
                "dst_ip": node,
                "new_node": f"{self.ip}:{self.port}"
            }
            await self.connect_and_send(ip, port, json.dumps(request), False)
            self.neighbors[self.calculate_uid(ip, str(port))] = (ip, int(port))
            logging.info(f"new neighbors for {self.ip} : {ip}")

            if get_blockchain:
                # get block chain from other nodes
                #TODO: resolve blockchain
                request_blockchain = {
                    "type": ConnectionCode.GET_BLOCKS,
                    "src_ip": f'{self.ip}:{self.port}',
                    "dst_ip": node,
                    'first_index': 0  # zero means whole blockchain
                }
                rec = await self.connect_and_send(ip, port, json.dumps(request_blockchain))
                rec = json.loads(rec.decode())
                if rec['status']:
                    blockchain = BlockChain.json_to_blockchain(
                        rec['blocks'])
                    if self.blockchain.height < blockchain.height:
                        self.blockchain = blockchain
                else:
                    raise NotImplementedError()
                logging.debug(f"blockchain: {rec}")

    async def send_mined_block(self, block_: Block):
        """declare other nodes for find new block"""
        data = {
            "type": ConnectionCode.MINED_BLOCK,
            "src_ip": f'{self.ip}:{self.port}',
            "dst_ip": '',
            "block": block_.get_data()
        }
        for uid in self.neighbors:
            ip, port = self.neighbors[uid]
            port = int(port)
            data['dst_ip'] = ip
            await self.connect_and_send(ip, port, json.dumps(data), False)

    async def send_new_trx(self, trx_: Trx):
        """declare other neighbors new transaction for adding to mempool"""
        msg = {
            "type": ConnectionCode.ADD_TRX,
            "src_ip": f'{self.ip}:{self.port}',
            'dst_ip': '',
            "trx": trx_.get_data(with_hash=True),
            "signature": self.wallet.base64Sign(trx_),
            "public_key": self.wallet.public_key,
            "passed_nodes": [self.ip]
        }
        for uid in self.neighbors:
            ip, port = self.neighbors[uid]
            msg['dst_ip'] = ip
            await self.connect_and_send(ip, port, json.dumps(msg), False)

    @staticmethod
    def calculate_uid(ip, port):
        return md5((ip + str(port)).encode()).hexdigest()
