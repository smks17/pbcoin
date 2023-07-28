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

after running the node you can run pbcoin-cli in env folder for interactions to make a transaction, get balance, and get block data. for example for sending 25 coins to an arbitrary address 'jYzY2JkMTdiN2JlNDRkY2YzZTQwNTRlZGY=' (it's fake), you can do like this:
## Windows
```console
    ./env/Scripts/pbcoin_cli.exe --socket-path \\.\pipe\node1_socket trx jYzY2JkMTdiN2JlNDRkY2YzZTQwNTRlZGY= 25
```
## Linux
```console
    ./env/bin/pbcoin_cli --socket-path .\node1_socket.s trx jYzY2JkMTdiN2JlNDRkY2YzZTQwNTRlZGY= 25
```
you can use --help for print usage cli

# Block
each block contains:

## header
- hash: Hash string of this block (in hex).
- height: Determines this block is the nth block that has been mined.
- nonce: The number that is added to block hash to be less than difficulty.
- number trx: Number of transactions in this block
- merkle_root: Merkle tree root hash of transactions
- trx_hashes: List of all trx hash
- previous_hash: Hash of previous block in blockchain.
- time: Time that this block mined in POSIX timestamp format.

## other
- trx: List of all block transactions data
- size: size of data (block)

# Transaction
each transaction contains:
- inputs: List of coins that the sender provides for recipients. They are unspent coins.
- output: The list of coins which their owner could use for sending to others.
- value: The amount of coins which have been sent.
- time: Time which trx is made
- include_block: This trx is in which block of the blockchain.
- hash: Trx string of this block (in hex).

## Coin
and coin contains:
- hash: calculated of coin hash
- value: The value of the coin.
- owner: The Address of the coin owner.
- created_trx_hash: The transaction hash that in which has been created.
- out_index: The index in the transaction in which the coin has been created.

and if the coin was spent in addition:
- trx_hash: The hash of trx in which coin has been spent.
- in_index: The index in the transaction in which the coin has been spent.

# TODO

- [ ] full node and not SVP
- [x] implement key and sign
- [ ] unittest
- [ ] dockerize
- [ ] separate wallet and node
- [x] database
- [ ] modular
- [ ] add test mode for unittests
- [ ] write doc for unittest
