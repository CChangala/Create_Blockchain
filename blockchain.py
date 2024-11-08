"""
In this assignment you will extend and implement a class framework to create a simple but functional blockchain that combines the ideas of proof-of-work, transactions, blocks, and blockchains.
You may create new member functions, but DO NOT MODIFY any existing APIs.  These are the interface into your blockchain.


This blockchain has the following consensus rules (it is a little different from Bitcoin to make testing easier):

Blockchain

1. There are no consensus rules pertaining to the minimum proof-of-work of any blocks.  That is it has no "difficulty adjustment algorithm".
Instead, your code will be expected to properly place blocks of different difficulty into the correct place in the blockchain and discover the most-work tip.

2. A block with no transactions (no coinbase) is valid (this will help us isolate tests).

3. If a block as > 0 transactions, the first transaction MUST be the coinbase transaction.

Block Merkle Tree

1. You must use sha256 hash 
2. You must use 0 if additional items are needed to pad odd merkle levels
(more specific information is included below)

Transactions

1. A transaction with inputs==None is a valid mint (coinbase) transaction.  The coins created must not exceed the per-block "minting" maximum.

2. If the transaction is not a coinbase transaction, coins cannot be created.  In other words, coins spent (inputs) must be >= coins sent (outputs).

3. Constraint scripts (permission to spend) are implemented via python lambda expressions (anonymous functions).  These constraint scripts must accept a list of parameters, and return True if
   permission to spend is granted.  If execution of the constraint script throws an exception or returns anything except True do not allow spending!

461: You may assume that every submitted transaction is correct.
     This means that you should just make the Transaction validate() function return True
     You do not need to worry about tracking the UTXO (unspent transaction outputs) set.

661: You need to verify transactions, their constraint and satisfier scripts, and track the UTXO set.


Some useful library functions:

Read about hashlib.sha256() to do sha256 hashing in python.
Convert the sha256 array of bytes to a big endian integer via: int.from_bytes(bunchOfBytes,"big")

Read about the "dill" library to serialize objects automatically (dill.dumps()).  "Dill" is like "pickle", but it can serialize python lambda functions, which you need to install via "pip3 install dill".  The autograder has this library pre-installed.
You'll probably need this when calculating a transaction id.

"""
import sys
assert sys.version_info >= (3, 6)
import hashlib
import pdb
import copy
import json
# pip3 install dill
import dill as serializer

class Output:
    """ This models a transaction output """
    def __init__(self, constraint = None, amount = 0):
        """ constraint is a function that takes 1 argument which is a list of 
            objects and returns True if the output can be spent.  For example:
            Allow spending without any constraints (the "satisfier" in the Input object can be anything)
            lambda x: True

            Allow spending if the spender can add to 100 (example: satisfier = [40,60]):
            lambda x: x[0] + x[1] == 100

            If the constraint function throws an exception, do not allow spending.
            For example, if the satisfier = ["a","b"] was passed to the previous constraint script

            If the constraint is None, then allow spending without constraint

            amount is the quantity of tokens associated with this output """
        self.constraint = constraint
        self.amount = amount

    def can_be_spent(self, satisfier):
        if self.constraint is None:
            return True
        try:
            return self.constraint(satisfier)
        except Exception:
            return False


class Input:
    """ This models an input (what is being spent) to a blockchain transaction """
    def __init__(self, txHash, txIdx, satisfier):
        """ This input references a prior output by txHash and txIdx.
            txHash is therefore the prior transaction hash
            txIdx identifies which output in that prior transaction is being spent.  It is a 0-based index.
            satisfier is a list of objects that is be passed to the Output constraint script to prove that the output is spendable.
        """
        self.txHash = txHash
        self.txIdx = txIdx
        self.satisfier = satisfier

class Transaction:
    """ This is a blockchain transaction """
    def __init__(self, inputs=None, outputs=None, data = None):
        """ Initialize a transaction from the provided parameters.
            inputs is a list of Input objects that refer to unspent outputs.
            outputs is a list of Output objects.
            data is a byte array to let the transaction creator put some 
              arbitrary info in their transaction.
        """
        self.inputs = inputs
        self.outputs = outputs
        self.data = data

    def getHash(self):
        """Return this transaction's probabilistically unique identifier as a big-endian integer"""
         # Serialize the transaction data (inputs, outputs, and any additional data)
        serialized_data = serializer.dumps((self.inputs, self.outputs, self.data))
        
        # Compute the SHA-256 hash of the serialized data
        hash_bytes = hashlib.sha256(serialized_data).digest()

        # Convert the hash (byte array) to a big-endian integer
        transaction_id = int.from_bytes(hash_bytes, 'big')

        return transaction_id

    def getInputs(self):
        """ return a list of all inputs that are being spent """
        return self.inputs if self.inputs else []

    def getOutput(self, n):
        """ Return the output at a particular index """
        if self.outputs and 0 <= n < len(self.outputs):
            return self.outputs[n]
        return None
    
    def validateMint(self, maxCoinsToCreate):
        """ Validate a mint (coin creation) transaction.
            A coin creation transaction should have no inputs,
            and the sum of the coins it creates must be less than maxCoinsToCreate.
        """
        if self.inputs is not None:
            return False  # Mint transactions should have no inputs
        if self.outputs:
            coins_created = sum(output.amount for output in self.outputs)
            return coins_created <= maxCoinsToCreate
        return False

    def validate(self, unspentOutputDict):
    # Keep existing coinbase check
        if not self.inputs:
            return True

        if not self.outputs:
            return False

        input_sum = 0
        output_sum = 0

        # Verify each input exists and can be spent
        for inp in self.inputs:
            utxo_key = (inp.txHash, inp.txIdx)
            if utxo_key not in unspentOutputDict:
                return False
                
            utxo = unspentOutputDict[utxo_key]
            if not utxo.can_be_spent(inp.satisfier):
                return False
                
            input_sum += utxo.amount

        # Calculate output sum
        for out in self.outputs:
            output_sum += out.amount

        return input_sum >= output_sum


class HashableMerkleTree:
    """ A merkle tree of hashable objects.

        If no transaction or leaf exists, use 32 bytes of 0.
        The list of objects that are passed must have a member function named
        .getHash() that returns the object's sha256 hash as an big endian integer.

        Your merkle tree must use sha256 as your hash algorithm and big endian
        conversion to integers so that the tree root is the same for everybody.
        This will make it easy to test.

        If a level has an odd number of elements, append a 0 value element.
        if the merkle tree has no elements, return 0.

    """

    def __init__(self, hashableList = None):
        self.objects = hashableList if hashableList else []
        self.hashableList = [i.getHash() for i in self.objects] if hashableList else []

    def calcMerkleRoot(self):
        """ Calculate the merkle root of this tree."""
        if not self.hashableList:
            return 0
        current_level = self.hashableList
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else 0
                combined = left.to_bytes(32, 'big') + right.to_bytes(32, 'big')
                next_level.append(int.from_bytes(hashlib.sha256(combined).digest(), 'big'))
            current_level = next_level
        return current_level[0]


class BlockContents:
    """ The contents of the block (merkle tree of transactions)
        This class isn't really needed.  I added it so the project could be cut into
        just the blockchain logic, and the blockchain + transaction logic.
    """
    def __init__(self):
        self.data = HashableMerkleTree()

    def setData(self, d):
        self.data = d

    def getData(self):
        return self.data

    def calcMerkleRoot(self):
        return self.data.calcMerkleRoot()

class Block:
    """ This class should represent a blockchain block.
        It should have the normal fields needed in a block and also an instance of "BlockContents"
        where we will store a merkle tree of transactions.
    """
    def __init__(self):
        # Hint, beyond the normal block header fields what extra data can you keep track of per block to make implementing other APIs easier?
        self.prior_block_hash = None
        self.version = None
        self.merkle_tree = None
        self.target = None
        self.nonce = 0
        self.block_contents = BlockContents()
        self.timestamp = None 

    def getContents(self):
        """ Return the Block content (a BlockContents object)"""
        return self.block_contents

    def setContents(self, data):
        """ set the contents of this block's merkle tree to the list of objects in the data parameter """
        merkle_tree = HashableMerkleTree(data)
        self.block_contents.setData(merkle_tree)
        self.merkle_tree = merkle_tree

    def setTarget(self, target):
        """ Set the difficulty target of this block """
        self.target = target

    def getTarget(self):
        """ Return the difficulty target of this block """
        return self.target

    def getHash(self):
        """ Calculate the hash of this block. Return as an integer """
        header_data = (str(self.prior_block_hash) + str(self.block_contents.calcMerkleRoot()) + 
                      str(self.timestamp) + str(self.nonce) + str(self.target)).encode()
        return int.from_bytes(hashlib.sha256(header_data).digest(), 'big')
        

    def setPriorBlockHash(self, priorHash):
        """ Assign the parent block hash """
        self.prior_block_hash = priorHash

    def getPriorBlockHash(self):
        """ Return the parent block hash """
        return self.prior_block_hash

    def mine(self,tgt):
        """Update the block header to the passed target (tgt) and then search for a nonce which produces a block who's hash is less than the passed target, "solving" the block"""
        self.setTarget(tgt)
        self.nonce = 0
        while self.getHash() >= tgt:
            self.nonce += 1
        

    def validate(self, unspentOutputs, maxMint): ##check this once 
        """ Given a dictionary of unspent outputs, and the maximum amount of
            coins that this block can create, determine whether this block is valid.
            Valid blocks satisfy the POW puzzle, have a valid coinbase tx, and have valid transactions (if any exist).

            Return None if the block is invalid.

            Return something else if the block is valid

            661 hint: you may want to return a new unspent output object (UTXO set) with the transactions in this
            block applied, for your own use when implementing other APIs.

            461: you can ignore the unspentOutputs field (just pass {} when calling this function)
        """
        if self.getHash() >= self.target:
            return None

        current_utxos = copy.deepcopy(unspentOutputs)
        transactions = self.block_contents.getData().objects if (self.block_contents and 
                      self.block_contents.getData() and hasattr(self.block_contents.getData(), 'objects')) else []

        if not transactions:
            return current_utxos

        spent = set()
        for idx, tx in enumerate(transactions):
            if idx == 0 and transactions:
                if tx.inputs is not None or (tx.outputs and not tx.validateMint(maxMint)):
                    return None
            else:
                if tx.inputs is None:
                    return None
                for inp in tx.inputs:
                    utxo_key = (inp.txHash, inp.txIdx)
                    if utxo_key in spent or utxo_key not in current_utxos:
                        return None
                    if not current_utxos[utxo_key].can_be_spent(inp.satisfier):
                        return None
                    spent.add(utxo_key)

            if tx.outputs:
                tx_hash = tx.getHash()
                for idx, out in enumerate(tx.outputs):
                    current_utxos[(tx_hash, idx)] = out

        for utxo_key in spent:
            del current_utxos[utxo_key]

        return current_utxos


class Blockchain(object):
    
    def __init__(self, genesisTarget, maxMintCoinsPerTx): ##check
        """ Initialize a new blockchain and create a genesis block.
            genesisTarget is the difficulty target of the genesis block (that you should create as part of this initialization).
            maxMintCoinsPerTx is a consensus parameter -- don't let any block into the chain that creates more coins than this!
        """
        self.maxMintCoinsPerTx = maxMintCoinsPerTx
        self.blocks = {}
        self.block_heights = {}
        self.cumulative_work = {}
        self.utxo_sets = {}
        self.genesisTarget = genesisTarget
        
        genesis = Block()
        genesis.setTarget(genesisTarget)
        genesis.setPriorBlockHash(0)
        genesis.mine(genesisTarget)
        
        genesis_hash = genesis.getHash()
        self.blocks[genesis_hash] = genesis
        self.block_heights[0] = [genesis_hash]
        self.cumulative_work[genesis_hash] = self.getWork(genesisTarget)
        self.utxo_sets[genesis_hash] = genesis.validate({}, self.maxMintCoinsPerTx)

    def getTip(self):
        """Return the block at the tip of the chain with the most cumulative work."""
        max_work = -1
        tip = None
        for block_hash, work in self.cumulative_work.items():
            if work > max_work:
                max_work = work
                tip = self.blocks[block_hash]
        return tip

    def extend(self, block):
        """Add a block to the blockchain if valid."""
        if not block or block.getPriorBlockHash() is None:
            return False
            
        prior_hash = block.getPriorBlockHash()
        if prior_hash not in self.blocks:
            return False

        parent_utxos = self.utxo_sets.get(prior_hash)
        if parent_utxos is None:
            return False

        new_utxos = block.validate(parent_utxos, self.maxMintCoinsPerTx)
        if new_utxos is None:
            return False

        block_hash = block.getHash()
        self.blocks[block_hash] = block
        self.utxo_sets[block_hash] = new_utxos
        
        parent_height = next(h for h, blocks in self.block_heights.items() 
                           if prior_hash in blocks)
        height = parent_height + 1
        
        if height not in self.block_heights:
            self.block_heights[height] = []
        self.block_heights[height].append(block_hash)
        
        self.cumulative_work[block_hash] = (
            self.cumulative_work[prior_hash] + 
            self.getWork(block.getTarget())
        )
        
        return True

    
    def getWork(self, target):
        """Calculate work based on target."""
        if target == 0:
            return float('inf')
        return self.genesisTarget / target

    def getCumulativeWork(self, blkHash):
        """Return cumulative work for a block hash."""
        return self.cumulative_work.get(blkHash)

    def getBlocksAtHeight(self, height):
        """Return list of blocks at given height."""
        return [self.blocks[h] for h in self.block_heights.get(height, [])]

# --------------------------------------------
# You should make a bunch of your own tests before wasting time submitting stuff to gradescope.
# Its a LOT faster to test locally.  Try to write a test for every API and think about weird cases.

# Let me get you started:
def Test():
    # test creating blocks, mining them, and verify that mining with a lower target results in a lower hash
    b1 = Block()
    b1.mine(int("F"*64,16))
    h1 = b1.getHash()
    b2 = Block()
    b2.mine(int("F"*63,16))
    h2 = b2.getHash()
    assert h2 < h1

    t0 = Transaction(None, [Output(lambda x: True, 100)])
    # Negative test: minted too many coins
    assert t0.validateMint(50) == False, "1 output: tx minted too many coins"
    # Positive test: minted the right number of coins
    assert t0.validateMint(100) == True, "1 output: tx minted the right number of coins"

    class GivesHash:
        def __init__(self, hash):
            self.hash = hash
        def getHash(self):
            return self.hash

    assert HashableMerkleTree([GivesHash(x) for x in [106874969902263813231722716312951672277654786095989753245644957127312510061509]]).calcMerkleRoot().to_bytes(32,"big").hex() == "ec4916dd28fc4c10d78e287ca5d9cc51ee1ae73cbfde08c6b37324cbfaac8bc5"

    assert HashableMerkleTree([GivesHash(x) for x in [106874969902263813231722716312951672277654786095989753245644957127312510061509, 66221123338548294768926909213040317907064779196821799240800307624498097778386, 98188062817386391176748233602659695679763360599522475501622752979264247167302]]).calcMerkleRoot().to_bytes(32,"big").hex() == "ea670d796aa1f950025c4d9e7caf6b92a5c56ebeb37b95b072ca92bc99011c20"

    print ("yay local tests passed")