# BlockChat

**BlockChat** is a blockchain-based messaging platform for safe messaging and transactions between users.

Each user can send coins or messages to another user, using BlockChat's cryptocurrency, `BCC` (_BlockChat Coin_).

## Implementation

### Communication

Communication between nodes in the blockchain is achieved with [Apache Kafka](https://kafka.apache.org/) broker.

Different types of messages should be sent to their corresponding topic:

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

Download Apache Kafka (3.5.2) from the [official website](https://downloads.apache.org/kafka/3.5.2/kafka_2.13-3.5.2.tgz), or by executing the command `wget https://dlcdn.apache.org/kafka/3.5.2/kafka_2.13-3.5.2.tgz`.
Full installation guide for Ubuntu 22.04 can be found [here](https://tecadmin.net/how-to-install-apache-kafka-on-ubuntu-22-04/).

NOTE: Be sure to replace 3.2.0 with 3.5.2 in the above guide, since version 3.2.0 is deprecated.

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

### Test cases

The Client can also be started to run a test case with predefined transactions, by using the `-t <test case>` argument like:

`python Client.py -b -t <test case>`

Test case files should be added under _./tests_ directory, e.g. _./tests/(test case)_ .  
Inside this directory, a _.txt_ file can be defined with transactions for each node,
named _trans(node ID).txt_.

The text file is expected to contain one line per transaction, in the following format:  
id<recipient ID> message

_NOTE:_ Only message transactions are supported

## Run with Docker Containers

Three different Docker configurations (docker-compose.yaml) have been predefined, in order to run tests
with various configurations and number on nodes in the system.

The three different docker configurations are saved in files **docker-compose.1.yaml**, **docker-compose.2.yaml** and
**docker-compose.3.yaml**.  
Tests 1, 3 use the env file _./envs/test1.env_ and test 2 uses the env file _./envs/test2.env_.  

In order to use, copy the contents of the desired test in the **docker-compose.yaml** file, and
then run by using the command `sudo docker-compose up`.

The container can be stopped at any time with `Ctrl+C` and then using `sudo docker-compose down` to remove the container.
