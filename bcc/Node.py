import os
from dotenv import load_dotenv
from datetime import datetime
import json
import threading
import copy
import random
from typing import TypedDict, Optional, List

from kafka import KafkaProducer, KafkaConsumer

from bcc.Blockchain import Blockchain, BlockchainDict
from bcc.Block import Block, BlockDict
from bcc.Transaction import Transaction, TransactionType
from bcc.crypto import (
    Wallet,
    generate_wallet,
    decrypt_message,
    sign_message,
    verify_message,
)
from bcc.utils import CustomEncoder

TOPICS = [
    {"name": "connect", "partitions": 1, "retention": 60 * 1000},
    {"name": "init", "partitions": 1, "retention": 60 * 1000},
    {"name": "transaction", "partitions": 1, "retention": 60 * 1000},
    {"name": "block", "partitions": 1, "retention": 60 * 1000},
]


class NodeInfo(TypedDict):
    id: int
    public_key: str
    coins: float
    stake: float


class Node:
    """
    Class describing a node of the BlockChat blockchain.

    Public methods:
    - get_info -- Get node's info, along with information for all connected nodes.
    - create_transaction -- Send a transaction to the blockchain
    - get_block -- Get info of block with given index
    - get_blockchain -- Get the entire blockchain in ascending order
    - wait_until_initialized -- Returns only after initialization step is completed
    """

    def __init__(self):
        """
        Creates a new node in the system.

        The node generates his own wallet and sends connection request to
        the bootstrap node, in order to receive a unique (incremental) ID.
        """
        self._initialize_config()

        # Start the listener thread
        self._listener = threading.Thread(target=self._receive_message)
        self._listener._stop_event = threading.Event()
        self._listener.start()

        # Send the public key to the broker (connect topic)
        payload = {"type": "request", "public_key": self._wallet["public_key"]}
        self._send_message(topic="connect", message=payload)

    def _initialize_config(self):
        """
        Initializes the node and info about the connection to the broker.
        """
        load_dotenv()

        # Initialize node's info
        self._wallet: Wallet = generate_wallet()
        self._id: int = None
        self._nonce: int = 0
        self._validator: Optional[str] = None

        # Initialize the empty blockchain & list of nodes
        self._blockchain: Blockchain = Blockchain()
        self._current_block: Block = None
        self._total_nodes = int(os.getenv("NUMBER_OF_NODES"))
        self._initial_stake = float(os.getenv("INITIAL_STAKE"))
        self._nodes: List[NodeInfo] = []
        self._temp_state: List[NodeInfo] = []
        self._transaction_queue: List[Transaction] = []

        # Initialize mutex lock
        self._mutex = threading.Lock()
        self._initialization_mutex = threading.Lock()
        self._initialization_mutex.acquire()

        # Get Kafka broker's info (IP & port)
        broker_ip = os.getenv("BROKER_IP")
        broker_port = os.getenv("BROKER_PORT")
        self._kafka_broker = f"{broker_ip}:{broker_port}"

    """
    Public API methods (for web view, CLI etc.)
    """

    def get_info(self):
        """
        Returns node's info, along with information for all connected nodes.

        If the node has not yet been initialized, it returns None.
        """
        if len(self._temp_state) == 0:
            return None

        info: NodeInfo | None = None
        nodes: List[NodeInfo] = []
        for node in self._temp_state:
            if node["public_key"] == self._wallet["public_key"]:
                info = node
            else:
                nodes.append(node)

        return {
            "node": info,
            "broker": self._kafka_broker,
            "connected_nodes": len(self._temp_state),
            "total_nodes": self._total_nodes,
            "nodes": nodes,
            "chain_length": self._blockchain.get_chain_length(),
        }

    def create_transaction(
        self,
        recipient_address: str,
        type_of_transaction: TransactionType,
        amount: float,
        message: str,
    ) -> Optional[bool]:
        """
        Creates and sends a new transaction with the given parameters, and
        increments the nonce counter by 1.

        If the block is full, returns None.

        Otherwise returns True or False depending on the transaction's validity.

        Keyword arguments:
        - recipient_address -- The public key of the recipient of this transaction
        - type_of_transaction -- The transaction's type (either COINS or MESSAGE)
        - amount -- The amount of BCC to be sent (only if type is COINS)
        - message -- The message to be sent (only if type is MESSAGE)
        """

        transaction = Transaction(
            sender_address=self._wallet["public_key"],
            recipient_address=recipient_address,
            type_of_transaction=type_of_transaction,
            nonce=self._nonce,
            amount=amount,
            message=message,
        )
        self._sign_transaction(transaction)
        self._nonce += 1

        self._mutex.acquire()

        # If block is full (waiting for validator's block), add to transaction queue
        if self._validator is not None or self._current_block.is_full():
            self._transaction_queue.append(transaction)
            self._mutex.release()
            return None

        if not self._validate_transaction(transaction):
            self._mutex.release()
            return False

        # Send the transaction to the broker (transaction topic)
        payload = {"transaction": transaction.to_dict()}
        self._send_message(topic="transaction", message=payload)

        self._add_transaction_to_block(transaction)
        self._mutex.release()

        return True

    def get_block(self, index: Optional[int]) -> tuple[BlockDict | None, int]:
        """
        Returns the block with given index from
        the blockchain and the chain's length.

        If given index is None, returns the current block.

        If given index is invalid, returns None as the block.

        Keyword arguments:
        - index -- Incremental index of the block in the chain, or None
        if the current block is requested
        """
        block_dict: BlockDict = None
        chain_length: int = self._blockchain.get_chain_length()
        if index is None:
            block_dict = self._current_block.to_dict()
        else:
            block: Block = self._blockchain.get_block(index)
            if block is None:
                return (None, chain_length)
            block_dict = block.to_dict()

        block_dict["validator"] = self._public_key_to_id(block_dict["validator"])

        if block_dict["current_hash"] is None:
            block_dict["current_hash"] = "-"

        if block_dict["timestamp"] is not None:
            block_dict["timestamp"] = datetime.fromtimestamp(
                block_dict["timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S %z")
        else:
            block_dict["timestamp"] = "-"

        for transaction in block_dict["transactions"]:
            if transaction["sender_address"] == "0":
                transaction["sender_address"] = "Genesis"
            else:
                transaction["sender_address"] = self._public_key_to_id(
                    transaction["sender_address"]
                )

            transaction["recipient_address"] = self._public_key_to_id(
                transaction["recipient_address"]
            )

            if transaction["type_of_transaction"] == TransactionType.COINS.value:
                if transaction["recipient_address"] == "-":
                    transaction["type_of_transaction"] = "Stake"
                else:
                    transaction["type_of_transaction"] = "Coin Transfer"
            else:
                transaction["type_of_transaction"] = "Message"

        return block_dict, chain_length

    def get_blockchain(self) -> BlockchainDict | None:
        """
        Returns the entire blockchain in ascending order.
        """

        def transaction_to_str(transaction: Transaction) -> str:
            """
            Returns a short string to describe the transaction

            Keyword arguments:
            - transaction -- The transaction to be described
            """
            sender_id: str = self._public_key_to_id(transaction.get_sender_address())
            recipient_id: str = self._public_key_to_id(
                transaction.get_recipient_address()
            )
            if transaction.is_genesis():
                return f"Node {recipient_id} received {transaction.get_amount()} BCC from Genesis"
            elif transaction.is_stake():
                return (
                    f"Node {sender_id} set his stake to {transaction.get_amount()} BCC"
                )
            elif transaction.get_type() == TransactionType.COINS:
                return f"Node {sender_id} sent {transaction.get_amount()} BCC to node {recipient_id}"
            else:
                return f"Node {sender_id} sent a message (cost {transaction.get_fee()} BCC) to node {recipient_id}"

        blockchain_dict: BlockchainDict = self._blockchain.to_dict()
        for block_dict in blockchain_dict["chain"]:
            block_dict["validator"] = self._public_key_to_id(block_dict["validator"])
            block_dict["timestamp"] = datetime.fromtimestamp(
                block_dict["timestamp"]
            ).strftime("%Y-%m-%d %H:%M:%S %z")
            # Add a field for total fees in the block
            transactions: List[Transaction] = [
                Transaction.from_dict(t) for t in block_dict["transactions"]
            ]
            block_dict["fees"] = sum(t.get_fee() for t in transactions)
            block_dict["transactions"] = [transaction_to_str(t) for t in transactions]

        return blockchain_dict["chain"]

    def wait_until_initialized(self):
        """
        Dummy method, only used to force client(s) to wait until
        the node has successfully been initialized before starting any
        transactions.
        """
        print("Waiting until all nodes are initialized...")
        self._initialization_mutex.acquire()
        self._initialization_mutex.release()
        print("All nodes have been initialized.")

    """
    Transaction related methods
    """

    def _sign_transaction(self, transaction: Transaction):
        """
        Signs a transaction with node's signature.

        Keyword arguments:
        - transaction -- The transaction to be signed
        """
        signature: str = sign_message(
            message=transaction.get_id(), private_key=self._wallet["private_key"]
        )
        transaction.set_signature(signature=signature)

    def _verify_signature(self, transaction: Transaction) -> bool:
        """
        Verifies a transaction's signature. Returns True if the
        signature is valid, otherwise False.

        Keyword arguments:
        - transaction -- The transaction to be verified
        """
        return verify_message(
            message=transaction.get_id(),
            signature=transaction.get_signature(),
            public_key=transaction.get_sender_address(),
        )

    def _validate_transaction(self, transaction: Transaction) -> bool:
        """
        Validates a transaction by verifying the signature and the sender's
        available coins (minus stake).

        Returns True if the transaction is valid, otherwise False.

        If the transaction is valid, it also updates the sender's and
        recipient's coins.

        Keyword arguments:
        - transaction -- The transaction to be validated
        """
        # Verify signature (unless it's the genesis block's transaction)
        if not transaction.is_genesis() and not self._verify_signature(transaction):
            return False

        # Sender cannot be the same as the recipient
        if transaction.get_sender_address() == transaction.get_recipient_address():
            return False

        # Check whether the transaction already exists in the blockchain or in the current block
        if self._blockchain.has_transaction(transaction):
            return False

        # Find sender & recipient's info inside list of nodes
        sender_info: NodeInfo = None
        recipient_info: NodeInfo = None
        for node in self._temp_state:
            if node["public_key"] == transaction.get_sender_address():
                sender_info = node
            elif node["public_key"] == transaction.get_recipient_address():
                recipient_info = node
            # Both sender and recipient were found - exit loop
            if sender_info is not None and recipient_info is not None:
                break

        # If sender's or recipient's public key is not in the list, invalidate the transaction
        if sender_info is None and not transaction.is_genesis():
            return False

        if recipient_info is None and not transaction.is_stake():
            return False

        # Check if sender node has enough coins for this transaction
        transaction_cost: float = transaction.get_cost()
        if not transaction.is_genesis():
            sender_available_coins: float = sender_info["coins"] - sender_info["stake"]
            if transaction.is_stake():
                sender_available_coins: float = sender_info["coins"]

            if sender_available_coins < transaction_cost:
                return False

        # Node has enough money - Update available coins/stake and return True
        if not transaction.is_genesis() and not transaction.is_stake():
            sender_info["coins"] += transaction.get_coins_earned(
                sender_info["public_key"]
            )

        if not transaction.is_stake():
            recipient_info["coins"] += transaction.get_coins_earned(
                recipient_info["public_key"]
            )
        else:
            sender_info["stake"] = transaction.get_cost()
        return True

    """
    Block related methods
    """

    def _initialize_block(self):
        """
        Initialize node's current block.

        If the chain is empty, it will set the block to None.
        """
        self._temp_state = copy.deepcopy(self._nodes)
        chain_length = self._blockchain.get_chain_length()
        if chain_length == 0:
            self._current_block = None
            return
        last_block = self._blockchain.get_last_block()
        previous_hash: str = last_block.get_current_hash()
        self._current_block: Block = Block(
            index=chain_length, previous_hash=previous_hash
        )

        # Use transactions from the transaction queue
        while len(self._transaction_queue) > 0:
            if self._validator is not None or self._current_block.is_full():
                break

            transaction: Transaction = self._transaction_queue.pop(0)
            if self._validate_transaction(transaction):
                # Send the transaction to the broker (transaction topic)
                # (if this is the sender of the transaction)
                if transaction.get_sender_address() == self._wallet["public_key"]:
                    payload = {"transaction": transaction.to_dict()}
                    self._send_message(topic="transaction", message=payload)

                # Add it to the current block
                self._add_transaction_to_block(transaction)

    def _commit_block(self):
        """
        Commits current block to the blockchain and re-initializes the
        current block
        """
        self._validator = None
        if self._current_block is None:
            return
        self._blockchain.add_block(self._current_block)

        # Add the block's fees to the validator's account
        for node in self._temp_state:
            if node["public_key"] == self._current_block.get_validator():
                for transaction in self._current_block.get_transactions():
                    node["coins"] += transaction.get_fee()
                break

        self._nodes = copy.deepcopy(self._temp_state)

        self._initialize_block()

    def _add_transaction_to_block(self, transaction: Transaction):
        """
        Adds a new transaction to the current block.
        If the block is full, it initiates the Proof-of-Stake algorithm
        to find the next validator.

        If the validator is this node, mints the current block and
        broadcasts it to all nodes.

        Keyword arguments:
        - transaction -- The transaction to be added to the next block
        """
        block_is_full: bool = self._current_block.add_transaction(transaction)
        if not block_is_full:
            return

        # Get the next block's validator (and keep in memory)
        self._validator = self._mint_block()

        if self._validator != self._wallet["public_key"]:
            return

        # If this node is the validator, broadcast the block to all other nodes
        self._current_block.set_timestamp(timestamp=self._get_timestamp())
        self._current_block.set_validator(self._wallet["public_key"])
        hash: str = self._current_block.calculate_hash()
        self._current_block.set_current_hash(hash=hash)

        # Send the block to the broker (block topic)
        payload = {"block": self._current_block.to_dict()}
        self._send_message(topic="block", message=payload)

        # Commit the block to the chain
        self._commit_block()

    def _mint_block(self) -> str:
        """
        Finds the next block's validator by using Proof-of-Stake consensus
        mechanism, and return his public key.

        Each node's probability to become the validator is equal to the
        percentage of the total stake that he possesses.
        """
        # Set the seed equal to the hash of the last block
        seed: str = self._current_block.get_previous_hash()
        random.seed(seed)

        # Find the validator based on stake
        total_stake: float = sum(node["stake"] for node in self._nodes)

        # If total stake = 0, assume the validator should be a random node
        if total_stake == 0:
            selected_node: int = random.randint(0, len(self._nodes) - 1)
            return self._nodes[selected_node]["public_key"]

        # Calculate a random threshold [0, total_stake], and find the first node for
        # whom the cumulative stake exceeds the threshold
        threshold_stake: float = random.uniform(0, total_stake)
        cumulative_stake: float = 0.0
        for node in self._nodes:
            cumulative_stake += node["stake"]
            if cumulative_stake >= threshold_stake:
                return node["public_key"]

    def _validate_block(self, block: Block, validator: Optional[str] = None) -> bool:
        """
        Validates a block by verifying the expected validator and
        the previous hash.

        Also validates all transactions in the block and if the
        block is valid, it also updates all nodes' coins.

        Returns True if the block is valid, otherwise False.

        Keyword arguments:
        - block -- The block to be validated
        - validator -- The expected validator (or None if unknown)
        """
        # Incorrect validator
        if validator is not None and validator != block.get_validator():
            return False

        # Incorrect value of the previous hash
        if (
            not block.is_genesis()
            and block.get_previous_hash()
            != self._blockchain.get_last_block().get_current_hash()
        ):
            return False

        # Validate all transactions
        for transaction in block.get_transactions():
            # Invalid transaction
            if not self._validate_transaction(transaction):
                return False

        # Move transactions that don't exist on the received block to the transaction queue
        if self._current_block is not None:
            for transaction in reversed(self._current_block.get_transactions()):
                if not block.has_transaction(transaction):
                    self._transaction_queue.insert(0, transaction)

        # Remove transactions that exist on the received block from the transaction queue
        self._transaction_queue = [
            t for t in self._transaction_queue if not block.has_transaction(t)
        ]

        self._current_block = block
        return True

    """
    Chain related methods
    """

    def _validate_blockchain(self, blockchain: Blockchain):
        """
        Validates a chain by verifying all the existing blocks.

        Discards the previous chain and state and updates all nodes' coins
        according to the new blockchain.

        Returns True if the blockchain is valid, otherwise False.

        Keyword arguments:
        - blockchain -- The blockchain to be validated
        """
        # Keep the previous state in case a rollback is required
        prev_state: List[NodeInfo] = copy.deepcopy(self._nodes)
        prev_temp_state: List[NodeInfo] = copy.deepcopy(self._temp_state)
        prev_block: Block = copy.deepcopy(self._current_block)
        prev_chain: Blockchain = copy.deepcopy(self._blockchain)

        # Discard previous state
        self._blockchain: Blockchain = Blockchain()
        for node in self._nodes:
            node["coins"] = 0.0
            node["stake"] = self._initial_stake

        for node in self._temp_state:
            node["coins"] = 0.0
            node["stake"] = self._initial_stake

        for block in blockchain.get_chain():
            # Invalid transaction
            if not self._validate_block(block):
                # Rollback changes
                self._nodes = copy.deepcopy(prev_state)
                self._temp_state = copy.deepcopy(prev_temp_state)
                self._current_block = copy.deepcopy(prev_block)
                self._blockchain = copy.deepcopy(prev_chain)
                return False

            # Add the block to the chain
            self._commit_block()

        return True

    """
    Received Messages Handling methods
    """

    def _receive_id(self, id: str):
        """
        Handles the message from bootstrap node, responding to the
        request for an ID.

        Decrypts the received ID and sets the private _id value.

        Keyword arguments:
        - id -- Unique ID assigned from bootstrap, encrypted with the node's public key
        """
        self._mutex.acquire()
        decrypted_id = decrypt_message(id, self._wallet["private_key"])
        try:
            self._id = int(decrypted_id)
            print(f"Received ID {decrypted_id}")
            self._mutex.release()
        except ValueError:
            self._mutex.release()
            exit(-1)

    def _receive_initialization_message(self, nodes: List[NodeInfo], chain: Blockchain):
        """
        Handles the initialization message received from bootstrap node.

        Keyword arguments:
        - nodes -- List of all nodes that have been connected to bootstrap
        - chain -- Current state of the blockchain
        """
        self._mutex.acquire()
        self._temp_state = nodes
        self._validate_blockchain(chain)
        self._initialization_mutex.release()
        self._initialize_block()
        self._mutex.release()

    def _receive_transaction(self, transaction: Transaction):
        """
        Handles a transaction received from another node.

        Validates the transaction and adds it to the current block.

        Keyword arguments:
        - transaction -- The transaction that was received from the broker
        """
        self._mutex.acquire()
        # If block is full (waiting for validator's block), add to transaction queue
        if self._validator is not None or self._current_block.is_full():
            self._transaction_queue.append(transaction)
            self._mutex.release()
            return

        if not self._validate_transaction(transaction):
            self._mutex.release()
            return
        self._add_transaction_to_block(transaction)
        self._mutex.release()

    def _receive_block(self, block: Block):
        """
        Handles a block received from another node (the validator node).

        Validates the block and adds it to the chain.

        Keyword arguments:
        - block -- The block that was received from the broker
        """
        self._mutex.acquire()

        # Keep the previous state in case a rollback is required
        prev_state: List[NodeInfo] = copy.deepcopy(self._temp_state)
        self._temp_state = copy.deepcopy(self._nodes)

        # No block is expected to be received
        if self._validator is None:
            self._mutex.release()
            # Rollback changes
            self._temp_state = copy.deepcopy(prev_state)
            return

        if not self._validate_block(block, self._validator):
            self._mutex.release()
            return
        self._commit_block()
        self._mutex.release()

    """
    Communication related methods
    """

    def _send_message(self, topic: str, message: any):
        """
        Sends given message (of any type) to the specified topic of the broker.

        Keyword arguments:
        - topic -- The broker's topic where the message should be sent
        - message -- The message that should be sent (needs to be JSON serializable)
        """
        producer = KafkaProducer(
            bootstrap_servers=self._kafka_broker,
            value_serializer=lambda m: json.dumps(m, cls=CustomEncoder).encode("utf-8"),
        )
        producer.send(topic, message)
        producer.flush()

    def _receive_message(self):
        """
        Listens to messages on all topics.

        Whenever a new message is received, handles
        it appropriately depending on the topic.

        NOTE: Messages received from self should be ignored
        """
        consumer = KafkaConsumer(
            bootstrap_servers=self._kafka_broker,
            auto_offset_reset="latest",
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        consumer.subscribe([topic["name"] for topic in TOPICS])
        for message in consumer:
            # Stop signal received - Close the consumer
            if self._listener._stop_event.is_set():
                consumer.close()
                break
            topic: str = message.topic
            value = message.value

            # Message received on topic "connect"
            if topic == "connect":
                # Check if the message is sent to this node
                if (
                    value["type"] == "response"
                    and value["public_key"] == self._wallet["public_key"]
                ):
                    self._receive_id(id=value["id"])
            # Initialization message received from bootstrap
            elif topic == "init":
                nodes: List[NodeInfo] = value["nodes"]
                chain: Blockchain = Blockchain.from_dict(value["chain"])
                self._receive_initialization_message(nodes, chain)
            # New transaction message received
            elif topic == "transaction":
                transaction = Transaction.from_dict(value["transaction"])
                # Ignore transactions sent from self
                if transaction.get_sender_address() != self._wallet["public_key"]:
                    self._receive_transaction(transaction)
            # New block message received
            elif topic == "block":
                block = Block.from_dict(value["block"])
                # Ignore blocks sent from self
                if block.get_validator() != self._wallet["public_key"]:
                    self._receive_block(block)

    """
    Helper methods
    """

    def _get_timestamp(self) -> float:
        """
        Returns the current timestamp
        """
        return datetime.now().timestamp()

    def _public_key_to_id(self, public_key: str) -> str:
        """
        Converts a node's public key to the corresponding ID.

        If public key does not exist, it returns -

        Keyword arguments:
        - public_key -- The public key to be converted to ID
        """
        if public_key is None:
            return "-"

        for node in self._temp_state:
            if node["public_key"] == public_key:
                return str(node["id"])

        return "-"

    def __del__(self):
        """
        Destructor: Close the consumer
        """
        # Stop
        self._listener._stop_event.set()
        self._listener.join()
