from hashlib import sha256

from pbcoin.merkle_tree import MerkleTreeNode

some_hashes = [
    "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f",
    "39bb4d76bdc7e63cca27e0e1383190348f42f0cc393cbb777e876c01d08dcfff",
    "cb8ca8f71968818ce0c2b729d7e2f2575139300e52bc64ebcbec091d87671c8e",
    "c741146db62d3facb809d0e57ef2ca982799dc566e438839051bff56dba0da28",
    "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"
]

def checking_merkleTree(root: MerkleTreeNode):
    left = root.left
    right = root.right
    if left == None or right == None:
        return root.hash
    else:
        return sha256((checking_merkleTree(left) + checking_merkleTree(right)).encode()).hexdigest()

class TestMerkleTree:
    def test_build_tree_one_element(self):
        one_hash = some_hashes[:1]
        root = MerkleTreeNode.build_merkle_tree(one_hash)
        assert root.hash == some_hashes[0], "could not handle one element hash"
    
    def test_build_tree_even_elements(self):
        four_element = some_hashes[:4]
        root = MerkleTreeNode.build_merkle_tree(four_element)
        assert four_element == [leaf.hash for leaf in root.find_leaves()]
        assert checking_merkleTree(root) == root.hash, "could not handle even element hash"
    
    def test_build_tree_odd_elements(self):
        five_element = some_hashes[:5]
        root = MerkleTreeNode.build_merkle_tree(five_element)
        assert five_element == [leaf.hash for leaf in root.find_leaves()]
        assert checking_merkleTree(root) == root.hash, "could not handle odd element hash"
    
    def test_proof_first_element(self):
        root = MerkleTreeNode.build_merkle_tree(some_hashes)
        need_hashes, bits = MerkleTreeNode.get_proof(root, some_hashes[0])
        is_exist, proof_root = MerkleTreeNode.proof_of_exist(need_hashes, bits, root.hash)
        assert is_exist
        assert proof_root.hash, root.hash

    def test_proof_last_element(self):
        root = MerkleTreeNode.build_merkle_tree(some_hashes)
        need_hashes, bits = MerkleTreeNode.get_proof(root, some_hashes[4])
        is_exist, proof_root = MerkleTreeNode.proof_of_exist(need_hashes, bits, root.hash)
        assert is_exist
        assert proof_root.hash == root.hash

    def test_proof_not_exist(self):
        root = MerkleTreeNode.build_merkle_tree(some_hashes)
        need_hashes, bits = MerkleTreeNode.get_proof(root, some_hashes[2])
        need_hashes[0] = 'some thing else'
        is_exist, proof_root = MerkleTreeNode.proof_of_exist(need_hashes, bits, root.hash)
        assert not is_exist