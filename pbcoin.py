import sys

import pbcoin

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
        else:
            print(f"Error: unknown option {argv[i]}", file=sys.stderr)
            usage()
            sys.exit(-1)
        i += 1
    
    return option

def main(argv):
    option = parseArgv(argv)
    pbcoin.setup(option)


if __name__ == "__main__":
    main(sys.argv)
