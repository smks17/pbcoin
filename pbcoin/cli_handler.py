from __future__ import annotations

import asyncio
import json
import socket
import os
import logging
import traceback
from sys import platform
from typing import List, Tuple

import pbcoin
from .cliflag import CliErrorCode, CliCommandCode

class CliServer():
    def __init__(self, socket_path_) -> None:
        self.is_unix = socket.AF_UNIX != None
        self.socket_path = socket_path_

    async def handle_cli_command(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """handle the user input cli from receive data socket"""
        recv = await reader.readuntil(b'\n')
        recv = recv.decode()
        # TODO: better receive (make a buffer clas)
        args = recv.split()
        command = args.pop(0)
        result, errors = await self.parse_args(int(command), args)
        writer.write(result.encode()+b'\n')
        await writer.drain()
        writer.write(f'{errors.value}\n'.encode())
        await writer.drain()
        writer.close()

    async def start(self):
        if self.is_unix:
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)
            server = await asyncio.start_unix_server(self.handle_cli_command, self.socket_path)
            os.chmod(self.socket_path, 0o666)
            loop = asyncio.get_event_loop()
            async with server:
                try:
                    await server.serve_forever()
                except:
                    logging.error("cli server is broken for some reason")
                finally:
                    server.close()
                    await server.wait_closed()
        elif platform == "win32":
            # TODO
            raise NotImplementedError()
        else:
            raise NotImplementedError()


    async def parse_args(self, command: int, args: List[str]) -> Tuple[str, CliErrorCode]:
        """parse the argument base on command input from user and do the command"""
        result = ""
        errors = CliErrorCode.NOTHING
        if command == CliCommandCode.TRX:
            # TODO: get sender key
            recipient = ''
            amount = 0
            try:
                recipient = args[0]
                amount = int(args[1])
            except:
                errors |= CliErrorCode.BAD_USAGE
                res = await pbcoin.WALLET.send_coin(recipient, amount)
                if not res:
                    errors |= CliErrorCode.TRX_PROBLEM
        elif command == CliCommandCode.BALANCE:
            result += str(pbcoin.WALLET.n_amount)
        elif command == CliCommandCode.BLOCK:
            try:
                if args[0] == '--last':
                    last_block = pbcoin.BLOCK_CHAIN.last_block
                    if last_block:
                        block_data = last_block.get_data(is_POSIX_timestamp=False)
                        result += json.dumps(block_data)
                    else:
                        errors |= CliErrorCode.NOT_FOUND
                else:
                    index_block = pbcoin.BLOCK_CHAIN.search(args[0])
                    if index_block:
                        block_data = pbcoin.BLOCK_CHAIN.blocks[index_block].getData(is_POSIX_timestamp=False)
                        result += json.dumps(block_data)
                    else:
                        errors |= CliErrorCode.NOT_FOUND
            except:
                errors |= CliErrorCode.BAD_USAGE
                traceback.print_exc()
        elif command == CliCommandCode.MEMPOOL:
            result += str(pbcoin.MINER.mempool)
        elif command == CliCommandCode.NEIGHBORS:
            result += str(pbcoin.NETWORK.neighbors.values())
        elif command == CliCommandCode.MINING:
            arg = args.pop()
            if arg == 'on':
                if pbcoin.MINER.stop_mining:
                    pbcoin.MINER.stop_mining = False
                else:
                    errors |= CliErrorCode.MINING_ON
            elif arg == 'off':
                if not pbcoin.MINER.stop_mining:
                    pbcoin.MINER.stop_mining = True
                else:
                    errors |= CliErrorCode.MINING_OFF
            elif arg == 'state':
                state =  "stoped" if pbcoin.MINER.stop_mining else "running"
                result += state
            else:
                errors |= CliErrorCode.BAD_USAGE
        else:
            errors |= CliErrorCode.BAD_USAGE
        return result, errors
