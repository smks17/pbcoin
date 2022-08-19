# pbcoin
it is a simple blockchain with POW Consensus

## run
Note: this project just was tested in python >= 3.8 and project is in development.

first install requirenments
```console
    $ pip install -r requirements.txt
```

example of running 2 nodes

#### nod 1:
```console
    $ python3 pbcoin.py --host 127.0.0.1 --port 8989
```
#### nod 2:
```console
    $ python3 pbcoin.py --host 127.0.0.2 --port 8989 --seeds 127.0.0.1:8989
```
you can run n nodes...

also you can use --help for print usage message

## cli

after running the node get you Cli for interactions to make a transaction, get balance, and get block data. for example for sending 25 coins to an arbitrary address '4d7387d434b2ba8e089eee2af708dde' (it's fake), you can do like this:
```console
    > trx 4d7387d434b2ba8e089eee2af708dde 25
```
for more help type help in cli

## Block
each block contains:

header:
- hash: block hash
- height: block height (number of blocks before this block)
- nonce: a random number that makes block hash less than difficulty
- number trx: number of transactions in this block
- merkle_root: merkle tree root hash of transactions
- trx_hashes: list of transactions hash
- previous_hash
- time: the time that is mined

other:
- trx: list of all block transactions
- size: size of data (block)

## Transaction
each transaction contains:
- inputs: the input coins
- output: the output coins
- value: amount of coins are sended
- time: the time is create this trx
- include_block: this trx is in which block in blockchain
- hash: if with_hash is True, then put trx hash too

and coin contains:
- value: the amount of this coin
- owner: who is (or was) this coin for
- trx_hash: exists in which transaction
- index: index of transaction in the block that contains this transaction

## TODO

- [ ] full node and not SVP
- [ ] implement key and sign
- [ ] unittest
- [ ] dockerize
- [ ] separate wallet and node
- [ ] database
