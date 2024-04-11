import os
from dotenv import load_dotenv
import json
from typing import List, TypedDict, Optional

from bcc.crypto import calculate_hash
from bcc.Transaction import Transaction, TransactionDict


class BlockDict(TypedDict):
    index: int
    timestamp: Optional[int]
    previous_hash: str
    current_hash: Optional[str]
    validator: Optional[str]
    transactions: List[TransactionDict]


class Block:
    """
    Class describing a block of the blockchain.

    Public methods:
    - add_transaction -- Add a transaction to the block
    - calculate_hash -- Get the block's hash
    - is_genesis -- Check if this is the genesis block
    - is_full -- Check if the block is full
    - has_transaction -- Check if a transaction exists in the block
    - to_dict -- Transform the block to a dictionary

    Getters:
    - get_validator -- Get the block's validator
    - get_previous_hash -- Get the previous block's hash
    - get_current_hash -- Get the block's hash
    - get_transactions -- Get the block's list of transactions

    Setters:
    - set_validator -- Set the block's validator
    - set_current_hash -- Set the block's hash
    - set_timestamp -- Set the block's timestamp
    """

    def __init__(self, index: int, previous_hash: str):
        """
        Creates a new Block object.
        Each block should have an index and the hash of the previous hash.

        Keyword arguments:
        - index -- the incremental unique identifier of the block
        - previous_hash -- the hash of the previous block
        - is_genesis -- Check if this is the genesis block
        """
        load_dotenv()
        self._BLOCK_CAPACITY = int(os.getenv("BLOCK_CAPACITY"))

        self._index: int = index
        self._timestamp: float = None
        self._previous_hash: str = previous_hash
        self._current_hash: Optional[str] = None
        self._validator: Optional[str] = None
        self._transactions: List[Transaction] = []

    """
    Utility methods
    """

    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Adds a new transaction to the current block.

        Returns True if the block's maximum capacity has been reached,
        otherwise False

        Keyword arguments:
        - transaction -- The transaction to be added to the block
        """
        self._transactions.append(transaction)
        return len(self._transactions) >= self._BLOCK_CAPACITY

    def calculate_hash(self):
        """
        Returns the hash of the block, based on its fields' values
        """
        id = {
            "index": self._index,
            "previous_hash": self._previous_hash,
            "validator": self._validator,
            "transactions": [
                {"sender_address": t.get_sender_address(), "nonce": t.get_nonce()}
                for t in self._transactions
            ],
        }
        block_json: str = json.dumps(id)
        return calculate_hash(block_json)

    def is_genesis(self) -> bool:
        """
        Returns True if the block is the genesis block, otherwise False
        """
        # Genesis block: previous_hash = 1
        if self._previous_hash != "1":
            return False
        # Genesis block: validator = 0
        if self._validator != "0":
            return False
        # Genesis block: 1 transaction : 1000*n BCC to bootstrap node from wallet 0
        if len(self._transactions) < 1:
            return False
        # Genesis block: 1000*n BCC to bootstrap node from wallet 0 (info of the single existing transaction)
        genesis_transaction = self._transactions[0]
        if not genesis_transaction.is_genesis():
            return False

        return True

    def is_full(self) -> bool:
        """
        Returns True if the block is full (max transactions capacity reached)
        """
        return len(self._transactions) >= self._BLOCK_CAPACITY

    def has_transaction(self, transaction: Transaction) -> bool:
        """
        Checks if a certain transaction already exists in the chain.

        Returns True or False correspondingly.

        Assume that two transactions are considered equal if their
        IDs (sender & nonce) are equal, since there can only be one
        transaction with certain nonce value per sender.

        Keyword arguments:
        - transaction -- The transaction to be found.
        """
        for t in self._transactions:
            if t.get_id() == transaction.get_id():
                return True

        return False

    """
    Getters & Setters
    """

    def get_validator(self) -> Optional[str]:
        return self._validator

    def get_previous_hash(self) -> str:
        return self._previous_hash

    def get_current_hash(self) -> str:
        return self._current_hash

    def get_transactions(self) -> List[Transaction]:
        return self._transactions

    def set_validator(self, validator: str):
        self._validator = validator

    def set_current_hash(self, hash: str):
        self._current_hash = hash

    def set_timestamp(self, timestamp: float):
        self._timestamp = timestamp

    def to_dict(self) -> BlockDict:
        """
        Returns a block as a dictionary
        """
        return {
            "index": self._index,
            "timestamp": self._timestamp,
            "previous_hash": self._previous_hash,
            "current_hash": self._current_hash,
            "validator": self._validator,
            "transactions": [t.to_dict() for t in self._transactions],
        }

    @classmethod
    def from_dict(cls, data: BlockDict):
        """
        Creates and returns a new Block object from
        a dictionary

        Keyword arguments:
        - data -- The dictionary that contains the block
        """
        b: Block = cls(index=data["index"], previous_hash=data["previous_hash"])
        b._timestamp = data["timestamp"]
        b._current_hash = data["current_hash"]
        b._validator = data["validator"]
        b._transactions = [Transaction.from_dict(t) for t in data["transactions"]]
        return b
