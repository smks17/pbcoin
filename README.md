# pbcoin
it is a simple blockchain with POW without any extra package

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

also you can --help for print help message