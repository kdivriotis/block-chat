from enum import Enum
import json
from typing import TypedDict

from bcc.crypto import calculate_hash

BCC_MESSAGE_FEE_PER_CHAR = 1.0  # Message cost: 1 BCC per character
BCC_TRANSFER_FEE = 3.0  # Transfer fee for COINS transactions: 3 %


class TransactionType(Enum):
    COINS = "Coins"
    MESSAGE = "Message"


class TransactionDict(TypedDict):
    id: str
    sender_address: str
    recipient_address: str
    type_of_transaction: int
    nonce: int
    signature: str
    amount: float
    message: str


class Transaction:
    """
    Class describing a transaction of the blockchain.

    Public methods:
    - is_stake -- Check if this is a Stake transaction
    - is_genesis -- Check if this is the genesis block's transaction
    - get_fee -- Get the fee cost of this transaction
    - get_cost -- Get the cost of this transaction (fee included)
    - get_coins_earned -- Get how many coins a certain node earned from this transaction
    - to_dict -- Transform the transaction to a dictionary

    Getters:
    - get_id -- Get the transaction's unique ID
    - get_signature -- Get the transaction's signature
    - get_sender_address -- Get the public key of the sender
    - get_recipient_address -- Get the public key of the recipient
    - get_type -- Get the transaction's type
    - get_nonce -- Get the transaction sender's nonce
    - get_amount -- Get the amount sent in the transaction

    Setters:
    - set_signature -- Set the transaction's signature
    """

    def __init__(
        self,
        sender_address: str,
        recipient_address: str,
        type_of_transaction: TransactionType,
        nonce: int,
        amount: int,
        message: str,
    ):
        """
        Creates a new Transaction object.
        Each transaction should have either an amount of coins or a message,
        depending on type_of_transaction

        Keyword arguments:
        sender_address -- the public key of the transaction's sender
        recipient_address -- the public key of the transaction's recipient
        type_of_transaction -- the transaction's type - either send coins or a message
        nonce -- counter of messages sent by the sender (increments after each transaction)
        amount -- the amount of coins to be sent (default=None, if no coins should be sent - message only)
        message -- the message to be sent (default=None, if no message should be sent - coins only)
        """
        self._sender_address = sender_address
        self._recipient_address = recipient_address
        self._type_of_transaction = type_of_transaction

        self._nonce = nonce
        self._signature = None

        if type_of_transaction == TransactionType.COINS:
            self._amount = amount
            self._message = None
        elif type_of_transaction == TransactionType.MESSAGE:
            self._amount = None
            self._message = message
        else:
            self._amount = None
            self._message = None

        self._id = self._calculate_hash()

    """
    Utility methods
    """

    def _calculate_hash(self) -> str:
        """
        Returns the hash of the transaction, based on its fields' values.

        Specifically, the hash (ID) of the transaction is the combination
        of the sender address (public key) and the nonce counter.
        """
        id = {"sender_address": self._sender_address, "nonce": self._nonce}
        transaction_json: str = json.dumps(id)
        return calculate_hash(transaction_json)

    def is_stake(self) -> bool:
        """
        Retruns True if this is a stake transaction,
        otherwise False
        """
        return (
            self._recipient_address == "0"
            and self._type_of_transaction == TransactionType.COINS
        )

    def is_genesis(self) -> bool:
        """
        Returns True if this is the genesis block's transaction,
        otherwise False
        """
        return self._sender_address == "0" and self._nonce == 0

    def get_fee(self) -> float:
        """
        Returns a transaction's fee, which depends on the transaction's type:
        - COINS : amount + fee % of sent amount (unless it's a stake transaction - no fees)
        - MESSAGE : number of characters * cost per character
        """
        if self._type_of_transaction == TransactionType.COINS and not self.is_stake():
            return BCC_TRANSFER_FEE / 100.0 * self._amount
        elif self._type_of_transaction == TransactionType.MESSAGE:
            return float(BCC_MESSAGE_FEE_PER_CHAR * len(self._message))
        else:
            return 0.0

    def get_cost(self) -> float:
        """
        Returns a transaction's total cost, which depends on the transaction's
        fee and the amount of coins being sent (if transaction type is coins)
        """
        if self.is_stake():
            return self._amount
        elif self._type_of_transaction == TransactionType.COINS:
            return self._amount + self.get_fee()
        elif self._type_of_transaction == TransactionType.MESSAGE:
            return self.get_fee()

        return 0.0

    def get_coins_earned(self, public_key: str) -> float:
        """
        Returns the amount of coins a user earned or spent
        on this transaction.
        If user earned coins, return value is > 0
        If user spent coins, return value is < 0
        If user is not involved or it is a stake transaction, return value is 0

        Keyword arguments:
        - public_key -- The public key of the user's wallet
        """
        # User is not involved in this transaction
        if self._sender_address != public_key and self._recipient_address != public_key:
            return 0.0

        # User is the sender (spent BCCs)
        if self._sender_address == public_key:
            return -self.get_cost()

        # User is the recipient of a COINS type of transaction (earned BCCs)
        if (
            self._recipient_address == public_key
            and self._type_of_transaction == TransactionType.COINS
        ):
            return self._amount

        # User received a message or unknown type of transaction - no coins received
        return 0.0

    """
    Getters & Setters
    """

    def get_id(self) -> str:
        return self._id

    def get_signature(self) -> str:
        return self._signature

    def get_sender_address(self) -> str:
        return self._sender_address

    def get_recipient_address(self) -> str:
        return self._recipient_address

    def get_type(self) -> TransactionType:
        return self._type_of_transaction

    def get_nonce(self) -> int:
        return self._nonce

    def get_amount(self) -> float:
        return self._amount

    def set_signature(self, signature: str):
        """
        Sets the transaction signature to given value

        Keyword arguments:
        - signature -- The signature to be set for the transaction (set by the sender)
        """
        self._signature = signature

    def to_dict(self) -> TransactionDict:
        """
        Returns a transaction as a dictionary
        """
        return {
            "id": self._id,
            "sender_address": self._sender_address,
            "recipient_address": self._recipient_address,
            "type_of_transaction": self._type_of_transaction.value,
            "nonce": self._nonce,
            "signature": self._signature,
            "amount": self._amount,
            "message": self._message,
        }

    @classmethod
    def from_dict(cls, data: TransactionDict):
        """
        Creates and returns a new Transaction object from
        a dictionary

        Keyword arguments:
        - data -- The dictionary that contains the transaction
        """
        t: Transaction = cls(
            sender_address=data["sender_address"],
            recipient_address=data["recipient_address"],
            type_of_transaction=TransactionType(data["type_of_transaction"]),
            nonce=data["nonce"],
            amount=data["amount"],
            message=data["message"],
        )
        t._signature = data["signature"]
        return t
