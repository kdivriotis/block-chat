import os
import json
import threading
import copy

from kafka import KafkaConsumer

from bcc.utils import initialize_broker
from bcc.Node import Node, NodeInfo, TOPICS
from bcc.crypto import encrypt_message
from bcc.Block import Block
from bcc.Transaction import Transaction, TransactionType


class Bootstrap(Node):
    """
    Class describing the Bootstrap node of the BlockChat blockchain.

    Public methods:
    - get_info -- Get node's info, along with information for all connected nodes.
    - create_transaction -- Send a transaction to the blockchain
    - get_block -- Get info of block with given index
    - get_blockchain -- Get the entire blockchain in ascending order.
    """

    def __init__(self):
        """
        Initializes the bootstrap node and the Kafka broker
        """
        self._initialize_config()

        # Start the listener thread
        self._listener = threading.Thread(target=self._receive_message)
        self._listener._stop_event = threading.Event()
        self._listener.start()

    def _initialize_config(self):
        """
        Initializes the node and info about connection to the broker.

        Also creates the needed topics for Kafka and the Genesis block.
        """
        super()._initialize_config()
        self._id: int = 0

        self._initial_coins = float(os.getenv("INITIAL_COINS"))

        # Add info to list of nodes
        info: NodeInfo = {
            "id": 0,
            "public_key": self._wallet["public_key"],
            "coins": 0.0,
            "stake": self._initial_stake,
        }
        self._nodes.append(info)

        # Create the topics needed for Kafka broker
        try:
            initialize_broker(server=self._kafka_broker, topics=TOPICS)
        except Exception:
            print("Something went wrong while initializing Kafka")
            exit(-1)

        # Create the genesis block and add it to the blockchain
        self._initialize_block()
        self._commit_block()

    """
    Block related methods
    """

    def _initialize_block(self):
        """
        Initialize node's current block.

        If the chain is empty, it will set the block to the genesis block.
        """
        super()._initialize_block()
        if self._current_block is None:
            self._temp_state = copy.deepcopy(self._nodes)
            self._current_block = self._create_genesis_block()

    def _create_genesis_block(self) -> Block:
        """
        Generates and returns the genesis block.

        The genesis block contains only one transaction,
        that gives INITIAL_COINS*n BCC (n = number of nodes) to
        the bootstrap node.

        The previous hash of the block is set to 1 and the
        validator is set to 0
        """
        # Create the genesis block's single transaction
        genesis_transaction: Transaction = Transaction(
            sender_address="0",  # Sender address = 0
            recipient_address=self._wallet["public_key"],
            type_of_transaction=TransactionType.COINS,
            nonce=0,
            amount=self._initial_coins * self._total_nodes,
            message="",
        )
        genesis_transaction.set_signature("")  # No signature for genesis transaction
        self._validate_transaction(genesis_transaction)

        # Create the genesis block
        genesis_block: Block = Block(
            index=self._blockchain.get_chain_length(), previous_hash="1"
        )
        genesis_block.add_transaction(transaction=genesis_transaction)
        genesis_block.set_timestamp(timestamp=self._get_timestamp())
        genesis_block.set_validator("0")
        hash: str = genesis_block.calculate_hash()
        genesis_block.set_current_hash(hash=hash)
        return genesis_block

    """
    Received Messages Handling methods
    """

    def _add_node(self, public_key: str):
        """
        Creates a new node and adds him to the list of connected nodes.

        If given data is invalid or node already exists, it skips the message.

        Otherwise it sends the incremental ID of the node, encrypted
        with the node's public key.

        If the last node was inserted, it also sends a message in the init topic
        to notify all the nodes about the current blockchain and the list of all
        nodes in the system.

        Keyword arguments:
        - public_key -- The public key of the new node
        """
        # Check if node already exists (same public key as existing node)
        for node in self._temp_state:
            if node["public_key"] == public_key:
                return

        # Otherwise add info to list of nodes
        id: int = len(self._temp_state)
        info: NodeInfo = {
            "id": id,
            "public_key": public_key,
            "coins": 0.0,
            "stake": self._initial_stake,
        }
        self._temp_state.append(info)

        # Create a new transaction to send money to the insterted node
        transaction: Transaction = Transaction(
            sender_address=self._wallet["public_key"],
            recipient_address=public_key,
            type_of_transaction=TransactionType.COINS,
            nonce=self._nonce,
            amount=self._initial_coins,
            message="",
        )
        self._sign_transaction(transaction)
        self._validate_transaction(transaction)
        self._nonce += 1

        # Add it to the current block and check if the block's capacity is full
        if self._current_block.add_transaction(transaction=transaction):
            self._current_block.set_timestamp(timestamp=self._get_timestamp())
            self._current_block.set_validator(self._wallet["public_key"])
            hash: str = self._current_block.calculate_hash()
            self._current_block.set_current_hash(hash=hash)
            self._commit_block()

        # Send the id and the public key to the broker (connect topic)
        encrypted_id: str = encrypt_message(str(id), public_key)
        payload = {
            "type": "response",
            "public_key": public_key,
            "id": encrypted_id,
        }
        self._send_message(topic="connect", message=payload)

        # Check if last node is inserted
        is_last_node: bool = len(self._temp_state) == self._total_nodes
        if not is_last_node:
            return

        # Commit the current block (if it's not empty) in order to be able to send the full blockchain to all nodes
        if is_last_node and len(self._current_block.get_transactions()) > 0:
            self._current_block.set_timestamp(timestamp=self._get_timestamp())
            self._current_block.set_validator(self._wallet["public_key"])
            hash: str = self._current_block.calculate_hash()
            self._current_block.set_current_hash(hash=hash)
            self._commit_block()

        # Send the init message after all nodes have been inserted
        payload = {"nodes": self._nodes, "chain": self._blockchain.to_dict()}
        self._send_message(topic="init", message=payload)
        self._initialization_ok = True

    """
    Communication related methods
    """

    def _receive_message(self):
        """
        Listens to messages on all topics.

        Whenever a new message is received, handles
        it appropriately depending on the topic.
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
                break
            topic: str = message.topic
            value = message.value
            # Message received on topic "connect"
            if topic == "connect":
                # Check if the message is sent to this node
                if value["type"] == "request":
                    self._add_node(public_key=value["public_key"])
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
