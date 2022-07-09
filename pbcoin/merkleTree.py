import math
from hashlib import sha256
import queue

class MerkleTree:
    def __init__(self, _hash = ''):
        self.right = None
        self.left = None
        self.parent = None
        self.hash = _hash
        self.depth = 1

    def computeHash(self):
        if self.left == None: # if left is none so right is none too
            return self.hash
        childHahs = self.left.computeHash() + self.right.computeHash()
        self.hash = sha256(childHahs.encode()).hexdigest()
        return self.hash

    def findLeaves(self):
        if self.left == None:
            return [self]
        leaves = self.left.findLeaves() + self.right.findLeaves()
        return leaves

    @staticmethod
    def buildMerkleTree(_values: list[str]):
        """make merkle tree from _values that are hashes of trx"""
        values = _values.copy()
        q = queue.Queue(len(values))
        for h in values:
            q.put(MerkleTree(h))
        while q.qsize() > 1:
            q_size = q.qsize()
            is_odd = False
            if q_size != 0 and q_size % 2 != 0:
                is_odd = True
            for i in range(q_size // 2):
                left = q.get()
                right = q.get()
                parent = MerkleTree()
                left.parent = parent
                right.parent = parent
                parent.left = left
                parent.right = right
                parent.depth += left.depth
                q.put(parent)
            # handle odd number
            if is_odd:
                q.put(q.get())

        root = q.get()
        root.computeHash()
        return root

    def getProof(self, key_hash: str):
        """
            find require hashes and correct path in pre-order walk for finding key_hash

            args
            ----
            key_hash: str:
                hash of key that you want proof

            return
            ------
            list[str]:
                hashes of nodes that are not in the path so we need their hashes to prove
            list[int]:
                bits that show that we are on the correct path or not
        """
        leaves = self.findLeaves()
        hashes = []
        bits = []
        for leaf in leaves:
            if leaf.hash == key_hash:
                hashes.append(leaf.hash)
                parent = leaf.parent
                current = leaf
                while parent != None:
                    if current.hash == parent.left.hash:
                        hashes.append(parent.right.hash)
                        bits.append(1)
                        bits.insert(0, 0)
                    else:
                        hashes.insert(0, parent.left.hash)
                        bits.append(1)
                        bits.append(0)
                    current = parent
                    parent = current.parent
                
                bits.append(1)
                return hashes, bits


    @staticmethod
    def proofOfExist(
        _hashes: list[str],
        bits: list[int],
        merkleTreeRootHash: str
    ) -> tuple[bool, "MerkleTree"]:
        """
            rebuild the Merkle tree with _hashes and bits for proof that the root hash is
            as same as merkleTreeRootHash or not

            args
            ----
            _hashes: list[str]:
                list of hashes that are neighbors in our path and require rebuilding
            bits: list[int]:
                for showing the correct path for the pre-order walk
            merkleTreeRootHash: str
                excepted root hash for checking proof

            return
            ------
            bool:
                show prove exists
            MerkleTree:
                return the rebuilt Merkle tree is not complete

        """
        max_depth = math.ceil(math.log2(len(_hashes)))
        def construct(depth: int):
            bit = bits.pop()
            node = None
            if depth == max_depth:
                if len(_hashes) > 0:
                    node_hash = _hashes.pop(0)
                    node = MerkleTree(node_hash)
            elif bit == 1:
                node = MerkleTree()
                node.left = construct(depth + 1)
                node.right = construct(depth + 1)
            else:
                if len(_hashes) > 0:
                    node_hash = _hashes.pop(0)
                    node = MerkleTree(node_hash)
            return node

        root = construct(0)
        if len(bits) > 0 or len(_hashes):
            raise Exception
        root.computeHash()
        return root.hash == merkleTreeRootHash, root
