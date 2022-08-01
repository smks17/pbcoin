import asyncio
import sys
import threading
from pprint import pprint

from numpy import block

import pbcoin

has_cli = True

def usage():
    print("usage python pbcoin.py [option]")
    print("options:")
    print("  --h,--help              show usage")
    print("  --debug                 logging more things")
    print("  --host <IPV4>           ipv4 for host")
    print("  --port <PORT>           port number for host")
    print("  --seeds <IP>:<PORT>     for connect to network of blockchain")
    print("  --full-node             keep all data of blockchain")
    print("  --cache <NUMBER>        allocate for cache (number is in kb)")
    print("  --no-cli                Could not have interaction with app")

def parseArgv(argv: list[str]):
    option = pbcoin.argvOption()
    i = 1
    while i < len(argv):
        if argv[i] == '--host':
            i += 1
            option.ip = argv[i]
        elif argv[i] == '--port':
            i += 1
            option.port = int(argv[i])
        elif argv[i] == '--seeds':
            i += 1
            option.seeds = argv[i].split(",")
        elif argv[i] == '--help' or argv[i] == '-h':
            usage()
            sys.exit(0)
        elif argv[i] == '--debug':
            option.debug = True
        elif argv[i] == '--full-node':
            option.is_fullNode = True
        elif argv[i] == '--cache':
            i += 1
            option.cache = float(argv[i])
        elif argv[i] == '--no-cli':
            global has_cli
            has_cli = False
        else:
            print(f"Error: unknown option {argv[i]}", file=sys.stderr)
            usage()
            sys.exit(-1)
        i += 1
    
    return option

async def cli(option):
    #TODO: print beautiful
    while True:
        args = input('> ').split()
        command = args.pop(0)
        if command == 'trx':
            try:
                recipient = args[0]
                amount = int(args[1])
            except:
                print("ERROR: bad usage")
            res = await pbcoin.wallet.sendCoin(recipient, amount)
            if res:
                print("Successful")
            else:
                print("ERROR: Could not have been send coins")
        elif command == 'balance':
            print(f"Your balance: {pbcoin.wallet.nAmount}")
        elif command == 'block':
            try:
                if args[0] == 'last':
                    last_block = pbcoin.BLOCK_CHAIN.last_block
                    if last_block:
                        pprint(f"Block: {last_block.getData(is_POSIX_timestamp=False)}")
                    else:
                        print("ERROR: No Block has been mined yet!")
                else:
                    index_block = pbcoin.BLOCK_CHAIN.search(args[0])
                    if index_block:
                        pprint(f"Block: {block[index_block].getData(is_POSIX_timestamp=False)}")
                    else:
                        print("ERROR: Not exist block")
            except:
                print("ERROR: bad usage")
        elif command == 'stop-mining':
            if option.mining:
                if pbcoin.MINER.stop_mining == False:
                    pbcoin.MINER.stop_mining = True
                    print("Mining stop")
                else:
                    print("ERROR: Mining already has been stopped!")
            else:
                print("ERROR: Mining is not available")
        elif command == 'start-mining':
            if option.mining:
                if pbcoin.MINER.stop_mining == True:
                    pbcoin.MINER.stop_mining = False
                    print("Mining start...")
                else:
                    print("ERROR: Mining already has been started!")
            else:
                print("ERROR: Mining is not available")
        elif command == "mine-status":
            print("Has been stopped" if pbcoin.MINER.stop_mining else "Mining")
        elif command == 'mempool':
            pprint(pbcoin.MINER.mempool)
        elif command == 'neighbors':
            pprint(list(pbcoin.NETWORK.neighbors.values()))
        elif command == 'help':
            print("help                              print usage")
            print("trx <RECIPIENT-KEY> <AMOUNT>      send amount from wallet to others")
            print("balance                           print wallet balance that you could spend")
            print("block <BLOCK-HASH>|last           print specific block data")
            print("stop-mining                       stop mining while you start again it")
            print("start-mining                      continue mining again (not start over again)")
            print("mine-status                       mining or not")
            print("mempool                           print list of mempool trx")
            print("neighbors                         print neighbors node addr")
        else:
            print(f"ERROR: Unknown command: {command}")

def main(argv):
    option = parseArgv(argv)
    if has_cli:
        threading.Thread(target=pbcoin.setup, args=[option]).start()
        threading.Thread(target=asyncio.run, args=[cli(option)]).start()
    else:
        pbcoin.setup(option)

if __name__ == "__main__":
    main(sys.argv)
