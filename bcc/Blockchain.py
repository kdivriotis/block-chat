from typing import List, TypedDict, Optional

from bcc.Block import Block, BlockDict
from bcc.Transaction import Transaction


class BlockchainDict(TypedDict):
    chain: List[BlockDict]


class Blockchain:
    """
    Class describing the BlockChat blockchain.

    Public methods:
    - get_chain_length -- Get number of blocks in the chain
    - get_last_block -- Get last inserted block in the chain
    - get_block -- Get a specific block in the chain (by index)
    - add_block -- Add a block to the chain
    - has_transaction -- Check if a transaction exists in the chain
    - to_dict -- Transform the chain to a dictionary
    """

    def __init__(self):
        """
        Creates a new empty blockchain
        """
        self._chain: List[Block] = []

    """
    Utility methods
    """

    def get_chain_length(self) -> int:
        """
        Returns the current length of the blockchain
        """
        return len(self._chain)

    def get_last_block(self) -> Optional[Block]:
        """
        Returns the last block of the blockchain or
        None if the chain is empty
        """
        chain_length = self.get_chain_length()
        if chain_length == 0:
            return None

        return self._chain[chain_length - 1]

    def get_block(self, index: int) -> Optional[Block]:
        """
        Returns the block with given index from the blockchain;

        If given index is invalid, returns None.

        Keyword arguments:
        - index -- Incremental index of the block in the chain
        """
        if index >= self.get_chain_length() or index < 0:
            return None

        return self._chain[index]

    def add_block(self, block: Block):
        """
        Adds a new block to the chain.

        Keyword arguments:
        - block -- The block to be arred in the chain
        """
        self._chain.append(block)

    def has_transaction(self, transaction: Transaction) -> bool:
        """
        Checks if a certain transaction already exists in the chain.

        Returns True or False correspondingly.

        Keyword arguments:
        - transaction -- The transaction to be found
        """
        for block in reversed(self._chain):
            if block.has_transaction(transaction):
                return True

        return False

    """
    Getters & Setters
    """

    def get_chain(self) -> List[Block]:
        return self._chain

    def to_dict(self) -> BlockchainDict:
        """
        Returns the blockchain as a dictionary.
        """
        return {
            "chain": [b.to_dict() for b in self._chain],
        }

    @classmethod
    def from_dict(cls, data: BlockchainDict):
        """
        Creates and returns a new Blockchain object from
        a dictionary.

        Keyword arguments:
        - data -- The dictionary that contains the chain
        """
        c: Blockchain = cls()
        c._chain = [Block.from_dict(b) for b in data["chain"]]
        return c
