from __future__ import annotations

import asyncio
import json
import socket
import os
import traceback
from sys import platform
from typing import List, Tuple

if os.name == 'nt':
    import win32pipe
    import win32file

import pbcoin.core as core
from .constants import PIPE_BUFFER_SIZE
from .cliflag import CliErrorCode, CliCommandCode
from .logger import getLogger


logging = getLogger(__name__)

class CliServer():
    def __init__(self, socket_path_) -> None:
        """
        socket_path_ for unix os is a path to unix socket like: './node_socket.s'
        but for windows os is a path to pipe socket like: '//./pipe/node_socket'
        """
        try:
            self.is_unix = socket.AF_UNIX != None
            self.socket_path = socket_path_
        except:
            self.is_unix = False
            self.pipe_path = socket_path_

    async def handle_cli_command_unix(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """handle the user input cli from receive data UNIX socket"""
        recv = await reader.readuntil(b'\n')
        recv = recv.decode()
        # TODO: better receive (make a buffer class)
        args = recv.split()
        command = args.pop(0)
        result, errors = await self.parse_args(int(command), args)
        writer.write(result.encode()+b'\n')
        await writer.drain()
        writer.write(f'{errors.value}\n'.encode())
        await writer.drain()
        writer.close()

    async def handle_cli_command_win(self, pipe):
        """handle the user input cli from receive data Windows pipe socket"""
        # TODO: better receive (make a buffer class)
        buffer_size = 2048
        buffer = ""
        _, recv = win32file.ReadFile(pipe, buffer_size)
        buffer = recv
        while len(recv) == buffer_size:
            _, recv = win32file.ReadFile(pipe, buffer_size)
            buffer += recv
        # TODO: handle this multi line
        buffer = buffer.decode()
        line = buffer.split("\n")[0]
        args = line.split()
        command = args.pop(0)
        result, errors = await self.parse_args(int(command), args)
        win32file.WriteFile(pipe, f'{result}\n{errors.value}\n'.encode())

    async def start(self):
        # using AF_UNIX for cli api
        if self.is_unix:
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)
            server = await asyncio.start_unix_server(self.handle_cli_command_unix, self.socket_path)
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
        # use windows pipe socket for cli api
        elif platform == "win32":
            while True:
                pipe = win32pipe.CreateNamedPipe(
                    self.pipe_path,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE |win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_NOWAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,  # nMaxInstances
                    PIPE_BUFFER_SIZE,  # nOutBufferSize
                    PIPE_BUFFER_SIZE,  # nInBufferSize
                    win32pipe.NMPWAIT_USE_DEFAULT_WAIT, # 50ms timeout (the default)
                    None # securityAttributes
                )
                if pipe == None:
                    raise Exception()
                try:
                    win32pipe.ConnectNamedPipe(pipe, None)
                    await self.handle_cli_command_win(pipe)
                except:
                    await asyncio.sleep(0.5)
                finally:
                    win32file.CloseHandle(pipe)
        else:
            raise NotImplementedError("Your os doesn't recognize for cli api")

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
            res = await core.WALLET.send_coin(recipient, amount)
            if not res:
                errors |= CliErrorCode.TRX_PROBLEM
        elif command == CliCommandCode.BALANCE:
            result += str(core.WALLET.n_amount)
        elif command == CliCommandCode.BLOCK:
            try:
                if args[0] == '--last':
                    last_block = core.BLOCK_CHAIN.last_block
                    if last_block:
                        block_data = last_block.get_data(is_POSIX_timestamp=False)
                        result += json.dumps(block_data)
                    else:
                        errors |= CliErrorCode.NOT_FOUND
                else:
                    index_block = core.BLOCK_CHAIN.search(args[0])
                    if index_block:
                        block_data = core.BLOCK_CHAIN.blocks[index_block].getData(is_POSIX_timestamp=False)
                        result += json.dumps(block_data)
                    else:
                        errors |= CliErrorCode.NOT_FOUND
            except:
                errors |= CliErrorCode.BAD_USAGE
                traceback.print_exc()
        elif command == CliCommandCode.MEMPOOL:
            result += str(core.MINER.mempool)
        elif command == CliCommandCode.NEIGHBORS:
            result += str(core.NETWORK.neighbors.values())
        elif command == CliCommandCode.MINING:
            arg = args.pop()
            if arg == 'on':
                if core.MINER.stop_mining:
                    core.MINER.stop_mining = False
                else:
                    errors |= CliErrorCode.MINING_ON
            elif arg == 'off':
                if not core.MINER.stop_mining:
                    core.MINER.stop_mining = True
                else:
                    errors |= CliErrorCode.MINING_OFF
            elif arg == 'state':
                state =  "stopped" if core.MINER.stop_mining else "running"
                result += state
            else:
                errors |= CliErrorCode.BAD_USAGE
        else:
            errors |= CliErrorCode.BAD_USAGE
        return result, errors
