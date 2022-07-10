import asyncio
from copy import copy
import json
import logging
from sys import getsizeof
from random import shuffle
from enum import IntEnum, auto
from hashlib import md5
from socket import *

import pbcoin
import pbcoin.block as pbBlock
import pbcoin.blockchain as pbBlockchain
import pbcoin.mine as mine

DEFAULT_PORT = 8989
DEFAULT_HOST = '127.0.0.1'

#! log not to be here
log = logging.getLogger()
log.setLevel(logging.DEBUG)

TOTAL_NUMBER_CONNECTIONS = 2
MAX_BYTE_SIZE = 8

def sizeof(data):
    return '{:>08d}'.format(getsizeof(data))

class ConnectionCode(IntEnum):
    NEW_NEIGHBOR = auto()  # send information node as a new neighbors
    NEW_NEIGHBORS_REQUEST = auto()  # request some new nodes for neighbors
    NEW_NEIGHBORS_FIND = auto()  # declare find new neighbors ()
    NOT_NEIGHBOR = auto()  # not be neighbors anymore!
    MINED_BLOCK = auto()  # declare other nodes find a new block
    RESOLVE_BLOCKCHAIN = auto()
    GET_BLOCKS = auto()
    SEND_BLOCKS = auto()

class Node:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        if not self.ip:
            self.ip = DEFAULT_HOST
        if not self.port:
            self.prt = DEFAULT_PORT
        self.uid = self.calculate_uid(ip, str(port)) # TODO: use public key
        self.neighbors: dict[str, tuple[str, int]] = dict()

    async def connectTo(self, dst_ip, dst_port):
        try:
            reader, writer = await asyncio.open_connection(dst_ip, int(dst_port))
            log.debug(f"from {self.ip} Connect to {dst_ip}:{dst_port}")
        except ConnectionError:
            log.error("Error Connection", exc_info=True)
            raise ConnectionError
        return reader, writer

    async def connectAndSend(self, dst_ip: str, dst_port: int, data: str, wait_for_receive = True):
        rec_data = b''
        try:
            reader, writer = await self.connectTo(dst_ip, dst_port)
            writer.write(bytes(sizeof(data).encode()))
            writer.write(bytes(data.encode()))
            await writer.drain()
            if wait_for_receive:
                size_data = await reader.read(MAX_BYTE_SIZE)
                size_data = int(size_data)
                rec_data = await reader.read(size_data)
                log.debug(f'receive data from {dst_ip}:{dst_port} {rec_data.decode()}')
            writer.close()
            await writer.wait_closed()
        except ConnectionError:
            log.error("Error Connection", exc_info=True)
            raise ConnectionError
        finally:
            return rec_data

    async def listen(self):
        """start listening request from other nodes and callback handleRequest"""
        server = await asyncio.start_server(self.handleRequest, host=self.ip, port=self.port)
        if not server:
            raise ConnectionError
        log.info(f"node connection is serve on {server.sockets[0].getsockname()}")
        loop = asyncio.get_event_loop()
        async with server:
            try:
                await server.serve_forever()
            except:
                log.error("connection is lost")
            finally:
                server.close()
                await server.wait_closed()

    async def handleRequest(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """ handle requests that receive other nodes """
        size = int(await reader.read(MAX_BYTE_SIZE))
        data = await reader.read(size)
        log.debug(f'receive data: {data.decode()}')
        data = json.loads(data.decode())

        #TODO
        assert len(ConnectionCode) == 8, "some requests are not implemented yet!"
        _type = data['type']
        if _type == ConnectionCode.NEW_NEIGHBOR:
            await self.handleNewNeighbor(data)
        elif _type == ConnectionCode.NEW_NEIGHBORS_REQUEST:
            await self.handleRequestNewNode(data, reader, writer)
        elif _type == ConnectionCode.NEW_NEIGHBORS_FIND:
            # TODO: this type implemented in startup
            log.warn("bad request for find new node")
        elif _type == ConnectionCode.NOT_NEIGHBOR:
            await self.handleNotNeighbor(data, writer)
        elif _type == ConnectionCode.MINED_BLOCK:
            await self.handleMinedBlock(data)
        elif _type == ConnectionCode.GET_BLOCKS:
            await self.handleGetBlock(data, writer)
        elif _type == ConnectionCode.GetNewBlockChain:
            await self.handleBlockchainRequest(data, writer)
        elif _type == ConnectionCode.RESOLVE_BLOCKCHAIN:
            # TODO:
            assert False, "Not implemented yet"
        else:
            raise NotImplementedError
        writer.close()
        await writer.wait_closed()

    async def handleNewNeighbor(self, data):
        """ add new node to neighbors nodes """
        new_node_ip, new_node_port = data["new_node"].split(":")
        uid = data["uid"]
        self.neighbors[uid] = (new_node_ip, int(new_node_port))
        log.info(f"new neighbor for {self.ip} : {new_node_ip}")

    async def handleRequestNewNode(self, data, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        final_req = None
        n_connections = data["number_connections_requests"]
        data["passed_nodes"].append(self.ip)
        final_req = {
            "status": True,
            "uid": self.uid,
            "type": ConnectionCode.NEW_NEIGHBORS_REQUEST,
            "src_ip": f'{self.ip}:{self.port}',
            "dst_ip": data["src_ip"],
            "number_connections_requests": n_connections,
            "p2p_nodes": data["p2p_nodes"],
            "passed_nodes": data["passed_nodes"]
        }
        if len(self.neighbors) < TOTAL_NUMBER_CONNECTIONS: # add new neighbor to itself
            n_connections -= 1
            final_req["number_connections_requests"] = n_connections
            final_req["p2p_nodes"].append(f"{self.ip}:{self.port}")
        # still need new neighbors
        if n_connections != 0:
            if final_req != None:
                addr_msg = final_req.copy()
            else:
                addr_msg = data.copy()
            addr_msg['src_ip'] = f'{self.ip}:{self.port}'
            for uid in list(self.neighbors):
                addr = self.neighbors.get(uid)
                if addr == None:
                    continue
                ip, port = addr
                # doesn't send data to repetitious node and stuck in a loop
                if ip not in addr_msg['passed_nodes']:
                    addr_msg['dst_ip'] = ip
                    try:
                        response = await self.connectAndSend(ip, port, json.dumps(addr_msg))
                        final_req = json.loads(response.decode())
                        n_connections = final_req['number_connections_requests']
                    except ConnectionError:
                        # TODO: checking for connection that neighbor is online yet?
                        log.error("", exc_info=True)
                if n_connections == 0:
                    break

        # resolve connections if can not find any neighbors for it
        # deleted own neighbors then we have 2 free place for neighbors
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
                response = await self.connectAndSend(ip, port, json.dumps(request))
                response = json.loads(response.decode())
                if response['status'] == True:
                    self.neighbors.pop(uid, None)
                    log.info(f"delete neighbor for {self.ip} : {ip}")
                    new_nodes = [f"{self.ip}:{self.port}", f"{ip}:{port}"]
                    final_req["p2p_nodes"] += new_nodes
                    final_req['number_connections_requests'] -= 2
                    break

        if final_req != None:
            final_req['src_ip'] = f'{self.ip}:{self.port}'
            final_req['type'] = ConnectionCode.NEW_NEIGHBORS_FIND
            if final_req['number_connections_requests'] == 0:
                final_req['status'] = True
            else:
                final_req['status'] = False
        else:
            raise NotImplementedError

        bytes_data = json.dumps(final_req).encode()
        writer.write(sizeof(bytes_data).encode())
        writer.write(bytes_data)

    async def handleNotNeighbor(self, data: dict[str, any], writer: asyncio.StreamWriter):
        """ delete neighbor """
        ip, port = data["src_ip"].split(':')
        uid = data["uid"]
        data = {
            "status": False,
            "dst_ip": ip,
            "src_ip": f'{self.ip}:{self.port}',
        }
        if len(self.neighbors) == TOTAL_NUMBER_CONNECTIONS:
            self.neighbors.pop(uid, None)
            log.info(f"delete neighbor for {self.ip} : {ip}")
            data['status'] = True
        bytes_data = json.dumps(data).encode()
        writer.write(sizeof(bytes_data).encode())
        writer.write(bytes_data)

    async def handleMinedBlock(self, data: dict[str, any]):
        """ handle for request finder new block"""
        mine.Mine.stop_mining = True
        blockData = data['block']
        log.info(f"mine block from {data['src_ip']}: {blockData}")
        block = pbBlock.Block.fromJsonDataFull(blockData)
        if block.blocHeight > pbcoin.BLOCK_CHAIN.height:
            number_new_blocks = block.blocHeight - pbcoin.BLOCK_CHAIN.height
            if number_new_blocks == 1:
                # just this block is new
                done = pbcoin.BLOCK_CHAIN.addNewBlock(block)
                if done != None:
                    # TODO: send why receive data is a bad request
                    log.error(f"bad request mined block from {data['src_ip']}")
                    pass
            else:
                # request for get n block before this block for add to its blockchain
                request = {
                    "type": ConnectionCode.GET_BLOCKS,
                    "src_ip": f'{self.ip}:{self.port}',
                    "dst_ip": data['src_ip'],
                    "number_block": number_new_blocks
                }
                ip, port = data['src_ip'].split(':')
                res = await self.connectAndSend(ip, int(port), json.dumps(request))
                res = json.loads(res.decode())
                if res['status']:
                    blocks = res['blocks']
                    blocks = [pbBlock.Block.fromJsonDataFull(block) for block in blocks]
                    pbcoin.BLOCK_CHAIN.resolve(blocks)
                    mine.Mine.start_over = True
                else:
                    # TODO
                    log.error("Bad request send for get blocks")
        else:
            # TODO: current blockchain is longer so declare other for resolve that
            pass
        
        log.debug(f"new block chian: {pbcoin.BLOCK_CHAIN.getHashes()}")
        mine.Mine.start_over = True

    async def handleGetBlock(self, data: dict[str, any], writer: asyncio.StreamWriter):
        copy_blockchain = copy(pbcoin.BLOCK_CHAIN)
        first_index = None
        hash_block = data.pop('hash_block', None)
        if hash_block:
            first_index = copy_blockchain.search(hash_block)
        else:
            first_index = data.pop('first_index', None)
        if first_index == None:
            # doesn't have this specific chain
            log.error("doesn't have self chain!")
        else:
            request = {
                "status": True,
                "type": ConnectionCode.SEND_BLOCKS,
                "src_ip": f'{self.ip}:{self.port}',
                "dst_ip": data['src_ip'],
                "blocks": copy_blockchain.getData(first_index)
            }
            bytes_data = json.dumps(request).encode()
            writer.write(sizeof(bytes_data).encode())
            writer.write(bytes_data)

    async def startUp(self, seeds: list[str]):
        """ begin to find new neighbors and connect to network"""
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
                "number_connections_requests": TOTAL_NUMBER_CONNECTIONS,
                "p2p_nodes": [],
                "passed_nodes": [self.ip]
            }
            data = json.dumps(request)
            response = await self.connectAndSend(ip, port, data)
            response = json.loads(response.decode())

            nodes += response['p2p_nodes']
            if (
                response['status'] == True
            and response['number_connections_requests'] == 0
            and response['type'] == ConnectionCode.NEW_NEIGHBORS_FIND
            ):
                break

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
            await self.connectAndSend(ip, port, json.dumps(request), False)
            self.neighbors[self.calculate_uid(ip, str(port))] = (ip, port)
            log.info(f"new neighbors for {self.ip} : {ip}")

            # get block chain from other
            request_blockchain = {
                "type": ConnectionCode.GET_BLOCKS,
                "src_ip": f'{self.ip}:{self.port}',
                "dst_ip": node,
                'first_index': 0 # whole blockchain
            }
            rec = await self.connectAndSend(ip, port, json.dumps(request_blockchain))
            rec = json.loads(rec.decode())
            if rec['status']:
                blockchain = pbBlockchain.BlockChain.jsonToBlockchain(rec['blocks'])
                if pbcoin.BLOCK_CHAIN.height < blockchain.height:
                    pbcoin.BlockChain = blockchain
            else:
                raise NotImplementedError()
            log.debug(f"blockchain: {rec}")

    async def sendMinedBlock(self, _block: pbBlock.Block):
        """ declare other nodes for find new block """
        data = {
            "type": ConnectionCode.MINED_BLOCK,
            "src_ip": f'{self.ip}:{self.port}',
            "dst_ip": '',
            "block": _block.getData()
        }
        for uid in self.neighbors:
            ip, port = self.neighbors[uid]
            port = int(port)
            data['dst_ip'] = ip
            await self.connectAndSend(ip, port, json.dumps(data), False)

    @staticmethod
    def calculate_uid(ip, port):
        return md5((ip + str(port)).encode()).hexdigest()