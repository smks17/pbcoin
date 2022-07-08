import sys

import pbcoin

def usage():
    print("usage python pbcoin.py [option]")
    print("options:")
    print("  --h,--help              show usage")
    print("  --debug                 logging more things")
    print("  --host <IPV4>           ipv4 for host")
    print("  --port <PORT>           port number for host")
    print("  --seeds <ip>:<port>     for connect to network of blockchain")

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
