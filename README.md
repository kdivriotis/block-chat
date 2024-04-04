# BlockChat

**BlockChat** is a blockchain-based messaging platform for safe messaging and transactions between users.

Each user can send coins or messages to another user, using BlockChat's cryptocurrency, `BCC` (_BlockChat Coin_).

## Implementation

### Communication

Communication between nodes in the blockchain is achieved with [Apache Kafka](https://kafka.apache.org/) broker.

Different types of messages should be send to their corresponding topic:

- **connect**: Whenever a new node wants to connect to the system, he needs to send a message to the bootstrap node
in order to receive an ID
- **init**: After all nodes have been connected, the bootstrap node send an initialization message to all nodes
with info about the other nodes and the blockchain
- **transaction**: Send new transaction messages to all other nodes
- **block**: Validator node broadcasts the validated block to all other nodes

### Consensus

[Proof-of-Stake](https://en.wikipedia.org/wiki/Proof_of_stake) protocol is used as the consensus mechanism of the blockchain.

## How to run

### Configuration

Configure the application's parameters (_.env_ file):

- **BROKER_IP** : Kafka broker's IP address
- **BROKER_PORT** : Kafka broker's port
- **DEFAULT_PORT** : Default port where the Flask Application should run (if not defined otherwise)
- **NUMBER_OF_NODES** : Number of nodes that will be inserted in the blockchain
- **INITIAL_COINS** : Initial BCC that each node will receive from the bootstrap node (after Genesis block)
- **INITIAL_STAKE** : If no stake transaction has been done, we assume the node has a default stake (for initialization purposes & testing)
- **BLOCK_CAPACITY** : Number of transaction that should be included in a block before it's considered full

### Setup Apache Kafka with Zookeeper

Download Apache Kafka (3.3.1) from the [official website](https://downloads.apache.org/kafka/3.3.1/kafka_2.13-3.3.1.tgz), or by executing the command `wget https://dlcdn.apache.org/kafka/3.3.1/kafka_2.13-3.3.1.tgz`.
Full installation guide for Ubuntu 22.04 can be found [here](https://tecadmin.net/how-to-install-apache-kafka-on-ubuntu-22-04/).

Start the Zookeeper and then the Apache Kafka server on the local machine. If the instructions on the tutorial above were followed, the server should be running on _localhost:9092_.

### Bootstrap node

The bootstrap node needs to be started before any other node is started.

In order to run the Client, _Python_ needs to be installed - version _3.11.8_ was used for development.

Navigate to the project's directory, run `pip install -r requirements.txt` to install all required dependencies.

In order to start the bootstrap node you can run:  
`python Client.py -b`  
or in order to start the bootstrap node in a specific port:  
`python Client.py -b -p <port>`  

### Other nodes

After bootstrap node has been started, all other nodes can be started as well.  
Make sure to run each node on a different port if they are running as processes on the same host.

`python Client.py -p <port>`

All nodes provide a web interface that is accessible on `localhost:<port>`

