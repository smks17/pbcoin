from __future__ import annotations

import argparse
import sys

import pbcoin.config as conf


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pbcoin",
        description="Run a pbcoin blockchain node.",
    )
    parser.add_argument("--host", dest="ip", metavar="IPV4", help="ipv4 for host")
    parser.add_argument("--port", type=int, help="port number for host")
    parser.add_argument(
        "--seeds",
        type=lambda s: s.split(","),
        help="comma-separated IP:PORT list to connect to the blockchain network",
    )
    parser.add_argument(
        "--full-node",
        dest="is_full_node",
        action="store_true",
        help="keep all data of the blockchain",
    )
    parser.add_argument("--debug", action="store_true", help="log more things")
    parser.add_argument(
        "--cache",
        type=float,
        metavar="NUMBER",
        help="cache size to allocate, in kb",
    )
    parser.add_argument(
        "--socket-path",
        metavar="PATH",
        help="UNIX/pipe (Windows) socket path the CLI uses to connect to this node",
    )
    parser.add_argument(
        "--logging-filename",
        metavar="PATH",
        help="file to write logs to",
    )
    parser.add_argument(
        "--no-logging",
        dest="logging",
        action="store_false",
        help="disable all logging",
    )
    parser.add_argument(
        "--difficulty",
        type=int,
        help=argparse.SUPPRESS,  # test-only override, kept out of --help on purpose
    )
    return parser


def parse_argv(argv: list[str]) -> dict:
    parser = build_arg_parser()
    namespace = parser.parse_args(argv[1:])
    return {k: v for k, v in vars(namespace).items() if v is not None}


def main() -> None:
    argv = sys.argv
    option = parse_argv(argv)
    conf.settings.update(option)
    from pbcoin.core import Pbcoin
    pbcoin = Pbcoin.initialize()
    pbcoin.run()


if __name__ == "__main__":
    main()
