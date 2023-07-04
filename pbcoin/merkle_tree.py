from __future__ import annotations

import math
import queue
from hashlib import sha256


class MerkleTreeNode:
    """
    A node of Merkle tree (or a leaf)

    Merkle tree is a hash tree that is each node has a left and right child.
    Each parent is its children hashing. \\
    more info: https://en.wikipedia.org/wiki/Merkle_tree

    Attributes
    ----------
        right: MerkleTree
            right child of node
        left: MerkleTree
            left child of node
        parent: MerkleTree
            parent node
        hash: str
            this node hash
        depth: int:
            the height of tree from this node (longest branch)
    """
    def __init__(self, _hash=''):
        self.right: MerkleTreeNode = None
        self.left: MerkleTreeNode = None
        self.parent: MerkleTreeNode = None
        self.hash = _hash
        self.depth = 1

    def compute_hash(self):
        """calculate parents hash"""
        if self.left is None:  # if left is none so right is none too
            return self.hash
        child_hash = self.left.compute_hash() + self.right.compute_hash()
        self.hash = sha256(child_hash.encode()).hexdigest()
        return self.hash

    def find_leaves(self):
        if self.left is None:
            return [self]
        leaves = self.left.find_leaves() + self.right.find_leaves()
        return leaves

    @staticmethod
    def build_merkle_tree(values: list[str]) -> 'MerkleTreeNode':
        """make merkle tree from _values that are hashes of trx"""
        if len(values) == 0:
            return MerkleTreeNode()
        values = values.copy()
        # make a queue MerkleTreeNodes from hash values
        q = queue.Queue(len(values))
        for h in values:
            q.put(MerkleTreeNode(h))
        # do (make) until reach root
        while q.qsize() > 1:
            # check is it odd in this level
            q_size = q.qsize()
            is_odd = False
            if q_size != 0 and q_size % 2 != 0:
                is_odd = True
            for i in range(q_size // 2):
                # make a node from 2 nodes (or leaf) and put it to queue
                left = q.get()
                right = q.get()
                parent = MerkleTreeNode()
                left.parent = parent
                right.parent = parent
                parent.left = left
                parent.right = right
                parent.depth += left.depth
                q.put(parent)
            # handle odd number
            # if nodes are odd we hash two by two and the last one is added without
            # hashing and doing any thing to the queue
            if is_odd:
                q.put(q.get())

        root = q.get()
        root.compute_hash()
        return root

    def get_proof(self, key_hash=None, index=None):
        """
            finds needed hashes and correct path in the pre-order walk for finding key_hash

            Args
            ----
                key_hash: str
                    hash of key that you want proof
                index: int
                    if it is not None means that don't need find the leaf and
                    uses the index for find the leaf

            return
            ------
            list[str]:
                hashes of nodes that are not in the path so we need their hashes to prove
            list[int]:
                bits that show that we are on the correct path or not
        """
        leaves = self.find_leaves()
        hashes = []
        bits = []

        def trace(leaf: MerkleTreeNode):
            hashes.append(leaf.hash)
            parent = leaf.parent
            current = leaf
            while parent is not None:
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

        if index is None:
            for leaf in leaves:
                if leaf.hash == key_hash:
                    return trace(leaf)
        else:
            return trace(leaves[index])

    @staticmethod
    def proof_of_exist(
        hashes: list[str],
        bits: list[int],
        merkle_tree_root_hash: str
    ) -> tuple[bool, MerkleTreeNode]:
        """
            rebuilds the Merkle tree with hashes and bits for proof that the root hash is
            as same as merkle_tree_root_hash or not

            args
            ----
            hashes: list[str]:
                list of hashes that are neighbors in our path and require rebuilding
            bits: list[int]:
                for showing the correct path for the pre-order walk
            merkle_tree_root_hash: str
                expected root hash for checking proof

            return
            ------
            bool:
                show prove exists
            MerkleTree:
                return the rebuilt Merkle tree (is not complete)

        """
        max_depth = math.ceil(math.log2(len(hashes)-1))+1

        def construct(depth: int):
            bit = bits.pop()
            node = None
            if depth == max_depth:
                if len(hashes) > 0:
                    node_hash = hashes.pop(0)
                    node = MerkleTreeNode(node_hash)
            elif bit == 1:
                node = MerkleTreeNode()
                node.left = construct(depth + 1)
                node.right = construct(depth + 1)
            else:
                if len(hashes) > 0:
                    node_hash = hashes.pop(0)
                    node = MerkleTreeNode(node_hash)
            return node

        root = construct(0)
        if len(bits) > 0 or len(hashes):
            raise Exception
        root.compute_hash()
        return root.hash == merkle_tree_root_hash, root
