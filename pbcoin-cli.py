import sys
import socket
from typing import IO

from pbcoin import SOCKET_PATH
from pbcoin.cliflag import CliCommandCode, CliErrorCode

def usage():
    print("usage:")
    print("    help                              print usage")
    print("    trx <RECIPIENT-KEY> <AMOUNT>      send amount from wallet to others")
    print("    balance                           print wallet balance that you could spend")
    print("    block <BLOCK-HASH>|last           print specific block data")
    print("    mining stop                       stop mining while you start again it")
    print("    mining start                      continue mining again (not start over again)")
    print("    mineing state                     mining or not")
    print("    mempool                           print list of mempool trx")
    print("    neighbors                         print neighbors node addr")

def cli():
    args = sys.argv
    args.pop(0)  # pop filename
    command_str = args.pop(0)
    command_code = CliCommandCode.getCode(command_str)
    if command_str == 'help':
        usage()
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock_io: IO
        try:
            sock.connect(SOCKET_PATH)
            sock_io = sock.makefile('wr')
        except:
            print("ERROR: Could not connect node. node probely is not running.", file=sys.stderr)
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
            print(sys.exc_info())

if __name__ == '__main__':
    cli()
