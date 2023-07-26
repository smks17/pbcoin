# pbcoin
It is a simple blockchain with POW Consensus

# run
Note: this project just was tested in python >= 3.8 and also is in development.

## in Windows

First make venv folder for python apps in powershell and then install the apps:
```console
    python -m venv env
    ./env/Scripts/Activate.ps1
    pip install --editable .
```
Now you can run program node or pbcoin-cli. For example for running two nodes:

#### nod 1:
```console
    ./env/Scripts/node.exe --host 127.0.0.1 --port 8989 --socket-path \\.\pipe\node1_socket --logging-filename .\node1.log
```
#### nod 2:
```console
    ./env/Scripts/node.exe --host 127.0.0.2 --port 8989 --seeds 127.0.0.1:8989 --socket-path \\.\pipe\node2_socket --logging-filename .\node2.log
```

## in Linux (or Unix)
First make venv folder for python apps in powershell and then install the apps:
```console
    python3 -m venv env
    source env/bin/activate
    pip3 install --editable . 
```
Now you can run program node or pbcoin-cli. For example for running two nodes:

#### nod 1:
```console
    ./env/bin/node --host 127.0.0.1 --port 8989 --socket-path .\node1_socket.s --logging-filename .\node1.log
```
#### nod 2:
```console
    ./env/bin/node --host 127.0.0.2 --port 8989 --seeds 127.0.0.1:8989 --socket-path .\node2_socket.s --logging-filename .\node2.log
```
you can run another n nodes... also you can use --help for print usage message.

# cli

after running the node you can run pbcoin-cli in env folder for interactions to make a transaction, get balance, and get block data. for example for sending 25 coins to an arbitrary address '4d7387d434b2ba8e089eee2af708dde' (it's fake), you can do like this:
## Windows
```console
    ./env/Scripts/pbcoin_cli.exe --socket-path \\.\pipe\node1_socket trx 4d7387d434b2ba8e089eee2af708dde 25
```
## Linux
```console
    ./env/bin/pbcoin_cli --socket-path .\node1_socket.s trx 4d7387d434b2ba8e089eee2af708dde 25
```
you can use --help for print usage cli

# Block
each block contains:

## header
- hash: block hash
- height: block height (number of blocks before this block)
- nonce: a random number that makes block hash less than difficulty
- number trx: number of transactions in this block
- merkle_root: merkle tree root hash of transactions
- trx_hashes: list of transactions hash
- previous_hash
- time: the time that is mined

## other
- trx: list of all block transactions
- size: size of data (block)

# Transaction
each transaction contains:
- inputs: the input coins
- output: the output coins
- value: amount of coins are sended
- time: the time is create this trx
- include_block: this trx is in which block in blockchain
- hash: if with_hash is True, then put trx hash too

## Coin
and coin contains:
- hash: calculated of coin hash
- value: the amount of this coin
- owner: who is (or was) this coin for
- created_trx_hash: was created in which transaction
- out_index: index of transaction in the block that was created

and if the coin was spent in addition:
- trx_hash: the hash of trx which spent in
- in_index: index of transaction in the block that was spent

# TODO

- [ ] full node and not SVP
- [x] implement key and sign
- [ ] unittest
- [ ] dockerize
- [ ] separate wallet and node
- [x] database
- [ ] modular
- [ ] add test mode for unittests
