import sys
import socket
import os
import traceback
from typing import IO, List, Optional

if os.name == 'nt':
    import win32pipe
    import win32file
    import win32api

import pbcoin
from pbcoin.cliflag import CliCommandCode, CliErrorCode


def usage():
    print("options:")
    print("    --socket-path                     the node UNIX/pipe(for windows) socket path which is used for cli to connect to")
    print("    --help                            print usage")
    print("usage:")
    print("    trx <RECIPIENT-KEY> <AMOUNT>      send amount from wallet to others")
    print("    balance                           print wallet balance that you could spend")
    print("    block <BLOCK-HASH>| --last        print specific block data")
    print("    mining stop                       stop mining while you start again it")
    print("    mining start                      continue mining again (not start over again)")
    print("    mining state                      mining or not")
    print("    mempool                           print list of mempool trx")
    print("    neighbors                         print neighbors node addr")

def cli_unix(command_code, args: List[str], socket_path: Optional[str]=None):
    if socket_path == None:
        socket_path=pbcoin.SOCKET_PATH
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock_io: IO
    try:
        sock.connect(socket_path)
        sock_io = sock.makefile('wr')
    except:
        print(
            "ERROR: Could not connect node. node probably is not running.", file=sys.stderr)
    try:
        sock_io.write(f"{command_code} {' '.join(args)}\n")
        sock_io.flush()
        result = sock_io.readline()
        errors = sock_io.readline()
        errors = CliErrorCode(int(errors))
        if errors == CliErrorCode.NOTHING:
            print(result)
        else:
            print(errors.message())
            print()
            print(usage())
    except:
        print("ERROR: No response from node", file=sys.stderr)
        traceback.print_exc()

def cli_win(command_code, args: List[str], pipe_path: Optional[str]=None):
    if pipe_path == None:
        pipe_path=pbcoin.PIPE_PATH
    handle = None
    while True:
    try:
        handle = win32file.CreateFile(
            pipe_path,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,  # dwDesiredAccess
            0,  # dwShareMode
            None,  # lpSecurityAttributes
                win32file.CREATE_ALWAYS,  # dwCreationDisposition
            0,  # dwFlagsAndAttributes
            None
        )
            if handle == None:
                raise Exception()
            
        win32pipe.SetNamedPipeHandleState(
                handle, win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT, None, None)
            
    except:
            err = win32api.GetLastError()
            if err == 2:
                continue
            else:
        print("ERROR: Could not connect node. node probably is not running.", file=sys.stderr)
                traceback.print_exc()

    try:
        win32file.WriteFile(
            handle, f"{command_code} {' '.join(args)}\n".encode())
        buffer_size = 64*1024
        _, recv = win32file.ReadFile(handle, buffer_size)
        buffer = recv
        while len(recv) == buffer_size:
            _, recv = win32file.ReadFile(handle, buffer_size)
            buffer += recv
        buffer = buffer.decode()
        lines = buffer.split('\n')
        result = lines[0]
        errors = CliErrorCode(int(lines[1]))
        if errors == CliErrorCode.NOTHING:
            print(result)
        else:
            print(errors.message())
            print()
            print(usage())
            break
    except:
            err = win32api.GetLastError()
            if err == 109 or err == 232:
                continue
            else:
        print("ERROR: No response from node", file=sys.stderr)
                print(win32api.GetLastError())
        traceback.print_exc()


def cli():
    args = sys.argv
    args.pop(0)  # pop filename
    command_str = args.pop(0)
    command_code = CliCommandCode.getCode(command_str)
    socket_path = None
    if command_str == '--socket-path':
        socket_path = args.pop(0)
        command_str = args.pop(0)
        command_code = CliCommandCode.getCode(command_str)

    if command_str == '--help':
        usage()
    else:
        if pbcoin.OS_TYPE == 'unix':
            cli_unix(command_code, args, socket_path)
        elif pbcoin.OS_TYPE == 'win':
            cli_win(command_code, args, socket_path)
        else:
            raise NotImplementedError("Your os does not recognize")


if __name__ == '__main__':
    cli()
