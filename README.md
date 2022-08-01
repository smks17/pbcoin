# pbcoin
it is a simple blockchain with POW

## run
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

also you can --help for print help message

and have cli for interactions with node

## TODO
[ ] full node and not SVP
[ ] implement key and sign
[ ] unittest
[ ] dockerize
[ ] separate wallet and node
[ ] database