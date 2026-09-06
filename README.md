# pbcoin

A blockchain implemented from scratch in Python — no blockchain framework, no ORM,
no third-party crypto or networking library. Proof-of-Work consensus, Merkle-tree
transaction validation, and peer-to-peer networking over raw sockets, all written
by hand.

> **Status:** in development / learning project. See [Design goals](#design-goals)
> and [Known limitations](#known-limitations) before judging it as production code —
> it isn't meant to be.
>
> **NOTE:** tests are not valid after the latest refactoring commit. Do not trust
> `pytest` output until this line is removed.

## Why no libraries?

Two different decisions are bundled under "no third-party dependencies," for two
different reasons:

- **No ORM.** There's no database-backed object model to map in the first place —
  the blockchain lives as an in-memory structure (see [`BlockChain`](#blockchain)).
  Where persistence exists, it's handled directly rather than through an ORM layer.
- **No blockchain, crypto, or networking framework.** This was deliberate, not an
  oversight. The point of the project was to understand what those tools normally
  do *for* you — Proof-of-Work consensus, chain reconciliation, Merkle-tree
  integrity checks, and node-to-node communication — by implementing each one
  directly instead of importing a solved version of it.

This is a reasonable way to learn how a blockchain actually works under the hood.
It is **not** a substitute for audited, production-grade cryptography or consensus
code, and this project doesn't claim to be one. If you're evaluating this as
engineering work rather than as a learning exercise: judge it on whether the
hand-rolled parts are understood and reasoned about, not on whether they'd survive
adversarial conditions in the wild — they haven't been tested against that bar,
and weren't meant to be yet.

## What's actually implemented

Based on the current source:

- **`Block`** — holds a list of transactions, a previous-block hash, a nonce, and
  a Merkle tree of its own transaction hashes. Hashing is SHA-256 over
  `merkle_root + nonce + previous_hash + time`. Validation
  (`is_valid_block`) checks three independent things — difficulty, transaction
  validity, and previous-hash linkage — via a `Flag` enum
  (`BlockValidationLevel`), so a block's validity isn't just a bool; you can see
  *which* check(s) it failed.
- **`BlockChain`** — an in-memory list of blocks. `add_new_block` validates (or
  skips validation, for locally-mined blocks) and appends. `resolve` compares an
  incoming candidate chain against the local one and can reorganize onto a
  different fork if the incoming chain validates. Non-full nodes cap how much
  chain data they keep in memory via a configured cache size.
- **`Mine`** — Proof-of-Work mining. Given a block, it increments the nonce in a
  loop until the block's hash is numerically at or below the difficulty target,
  picking up newly arrived mempool transactions mid-search. On success it adds the
  block to the chain and, if a node is attached, sends it to peers.
- **CLI** — a local control socket (UNIX domain socket, or a named pipe on
  Windows) that a separate `pbcoin_cli` command talks to, for checking balance,
  sending a transaction, inspecting a block, listing neighbors, and toggling
  mining on/off.

## Known limitations

Being direct about the current state, rather than glossing over it:

- The test suite is currently broken following a refactor (see the warning at the
  top of this file) — treat any passing/failing test result as unverified until
  this note is removed.
- This is a from-scratch cryptographic and networking implementation that has not
  been security-audited. Don't use it to hold anything of value.
- Some CLI paths are less exercised than others — for instance, looking up a block
  by hash (rather than `--last`) goes through a different code path than the
  common case and hasn't been verified the same way.

## Run

Tested on Python >= 3.8.

### Linux / Unix

```bash
python3 -m venv env
source env/bin/activate
pip3 install --editable .
```

Run two nodes:

```bash
# node 1
./env/bin/node --host 127.0.0.1 --port 8989 --socket-path ./node1_socket.s --logging-filename ./node1.log

# node 2
./env/bin/node --host 127.0.0.2 --port 8989 --seeds 127.0.0.1:8989 --socket-path ./node2_socket.s --logging-filename ./node2.log
```

You can run more than two nodes this way. Use `--help` for the full option list.

### Windows

```powershell
python -m venv env
./env/Scripts/Activate.ps1
pip install --editable .
```

```powershell
# node 1
./env/Scripts/node.exe --host 127.0.0.1 --port 8989 --socket-path \\.\pipe\node1_socket --logging-filename .\node1.log

# node 2
./env/Scripts/node.exe --host 127.0.0.2 --port 8989 --seeds 127.0.0.1:8989 --socket-path \\.\pipe\node2_socket --logging-filename .\node2.log
```

## CLI

After a node is running, use `pbcoin_cli` (pointed at the same socket path) to
interact with it — send a transaction, check balance, inspect a block.

```bash
# Linux
./env/bin/pbcoin_cli --socket-path ./node1_socket.s trx <recipient-address> 25

# Windows
./env/Scripts/pbcoin_cli.exe --socket-path \\.\pipe\node1_socket trx <recipient-address> 25
```

Use `--help` for the full command list.

## Data model

### Block

**Header**
- `hash` — hex hash of this block
- `height` — position of this block in the chain
- `nonce` — the value found to make the block hash satisfy the difficulty target
- `number_trx` — number of transactions in the block
- `merkle_root` — Merkle-tree root hash of the block's transactions
- `trx_hashes` — hashes of every transaction in the block
- `previous_hash` — hash of the preceding block
- `time` — when the block was mined (POSIX timestamp)

**Body**
- `trx` — the block's transaction data
- `size` — size of the block data

### Transaction

- `inputs` — unspent coins the sender is spending
- `outputs` — coins created for recipients (and change, if any)
- `value` — amount transferred
- `time` — when the transaction was created
- `include_block` — which block this transaction was included in
- `hash` — hex hash of the transaction

### Coin

- `hash` — coin hash
- `value` — coin amount
- `owner` — address of the current owner
- `created_trx_hash` — transaction that created this coin
- `out_index` — this coin's index in that transaction's outputs

Once spent, a coin additionally has:
- `trx_hash` — the transaction that spent it
- `in_index` — this coin's index in that transaction's inputs

## TODO

- [ ] Full node vs. lightweight/SPV client as a real, separable mode
- [x] Key generation and transaction signing
- [ ] Fix and re-validate the unit test suite after the recent refactor
- [ ] Dockerize
- [ ] Separate wallet and node more cleanly
- [x] Persistent storage backend
- [ ] Reduce coupling between modules (see `# TODO` markers throughout `blockchain.py`
      and `block.py` for specifics — several `TODO: Not do operation inplace` /
      `TODO: Relocated this method` notes already flag where)
- [ ] Test-mode support for the unit tests
- [ ] Document the unit test setup

## License

MIT — see `LICENCE`.