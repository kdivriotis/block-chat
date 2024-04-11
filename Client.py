import os
import time
import signal
import argparse
import threading

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, jsonify

from bcc.Node import Node
from bcc.Bootstrap import Bootstrap
from bcc.Transaction import BCC_MESSAGE_FEE_PER_CHAR, BCC_TRANSFER_FEE, TransactionType

load_dotenv()
DEFAULT_PORT = int(os.getenv("DEFAULT_PORT"))
NUMBER_OF_NODES = int(os.getenv("NUMBER_OF_NODES"))
BLOCK_CAPACITY = int(os.getenv("BLOCK_CAPACITY"))

app = Flask(__name__, static_url_path="/static")
app.config["DEBUG"] = False


def stop_node(sig, frame):
    print("Received Ctrl+C, shutting down...")
    global node
    del node
    exit(0)


""" Parse Command Line Arguments """

parser = argparse.ArgumentParser(
    prog="Client.py", description="REST API & Client for BlockChat", epilog=None
)
# Bootstrap flag
parser.add_argument(
    "-b",
    "--bootstrap",
    action="store_true",
    required=False,
    help="Set this as the bootstrap node's client",
)
# HTTP port
parser.add_argument(
    "-p",
    "--port",
    type=int,
    required=False,
    default=DEFAULT_PORT,
    help=f"HTTP port the client listens to ({DEFAULT_PORT}-65535)",
)
# Select Test case
parser.add_argument(
    "-t",
    "--test",
    type=str,
    required=False,
    default=None,
    help=f"Test case to be executed (./tests/<test>)",
)
args = parser.parse_args()
is_bootstrap: bool = args.bootstrap

port: int = args.port
if port < DEFAULT_PORT or port > 65535:
    parser.print_help()
    exit(-1)

test_case: str | None = args.test
if test_case is not None:
    test_case_dir = os.path.join("tests", test_case)
    if not os.path.isdir(test_case_dir):
        print(f"Directory {test_case_dir} does not exist")
        parser.print_help()
        exit(-1)


node = Bootstrap() if is_bootstrap else Node()
signal.signal(signal.SIGINT, stop_node)

""" Flask API Endpoints Definition """


@app.route("/", methods=["GET"])
def info():
    global node
    info = node.get_info()
    if info is None:
        return render_template("not_initialized.html")

    return render_template(
        "info.html",
        node=info["node"],
        broker=info["broker"],
        connected_nodes=info["connected_nodes"],
        total_nodes=info["total_nodes"],
        nodes=info["nodes"],
    )


@app.route("/transaction", methods=["GET", "PUT"])
def transaction():
    """
    Request type:
    - GET -- Display the transaction.html page to
    - PUT -- Receive a new transaction, validate it and send it to all nodes
    """
    global node
    info = node.get_info()
    if request.method == "GET":
        if info is None:
            return render_template("not_initialized.html")

        return render_template(
            "transaction.html",
            node=info["node"],
            broker=info["broker"],
            connected_nodes=info["connected_nodes"],
            total_nodes=info["total_nodes"],
            nodes=info["nodes"],
            BCC_per_char=BCC_MESSAGE_FEE_PER_CHAR,
            transfer_fee=BCC_TRANSFER_FEE,
        )
    elif request.method == "PUT":
        data = request.json

        # Check if all nodes have been connected
        if info["connected_nodes"] < info["total_nodes"]:
            return jsonify({"message": "Waiting for all nodes to connect"}), 400

        # Validate transaction type
        transaction_type: TransactionType = TransactionType.COINS
        if data["type"] == "message":
            transaction_type = TransactionType.MESSAGE
        elif data["type"] == "coins" or data["type"] == "stake":
            transaction_type = TransactionType.COINS
        else:
            return jsonify({"message": "Invalid transaction type"}), 400

        # Validate recipient address
        recipient: str = ""
        if data["recipient"] is None:
            return jsonify({"message": "Recipient address cannot be empty"}), 400
        elif data["type"] == "stake":
            if data["recipient"] != -1:
                return (
                    jsonify(
                        {"message": "Recipient address must be 0 for stake transaction"}
                    ),
                    400,
                )
            else:
                recipient = "0"
        elif data["type"] != "stake":
            if not any(n["id"] == data["recipient"] for n in info["nodes"]):
                return jsonify({"message": "Invalid recipient address"}), 400
            for n in info["nodes"]:
                if n["id"] == data["recipient"]:
                    recipient = n["public_key"]
                    break

        # Validate amount/message (depending on transaction type)
        amount: float = 0.0
        message: str = ""
        # Coin Transfer or Stake Transaction: Check for positive/non-negative number
        if transaction_type == TransactionType.COINS:
            if data["type"] == "coins" and data["amount"] <= 0:
                return jsonify({"message": "Amount must be a positive number"}), 400
            elif data["type"] == "stake" and data["amount"] < 0:
                return jsonify({"message": "Amount must be a non-negative number"}), 400
            amount = float(data["amount"])
        # Message Transaction" Check for non-empty message
        else:
            if len(data["message"]) == 0:
                return jsonify({"message": "Message cannot be empty"}), 400
            message = data["message"]

        # Create the transaction on node
        result: bool = node.create_transaction(
            recipient_address=recipient,
            type_of_transaction=transaction_type,
            amount=amount,
            message=message,
        )

        # Once processed, return a success response with status code 201
        if result:
            return jsonify({"message": "Transaction has been sent"}), 201
        else:
            return jsonify({"message": id}), 400


@app.route("/block", methods=["GET"])
@app.route("/block/<int:index>", methods=["GET"])
def block(index=None):
    global node
    info = node.get_info()
    if info is None:
        return render_template("not_initialized.html")

    if index is not None:
        try:
            index = int(index)
        except ValueError:
            return redirect(url_for("block"))

    block, chain_length = node.get_block(index)
    if block is None:
        return redirect(url_for("block"))

    next_block_url = "/block"
    if index is None:
        next_block_url = f"/block/{chain_length - 1}"
    elif index > 0:
        next_block_url = f"/block/{index - 1}"

    previous_block_url = "/block"
    if index is None:
        previous_block_url = "/block/0"
    elif index < chain_length - 1:
        previous_block_url = f"/block/{index + 1}"

    block_title = ""
    if index is None:
        block_title = "Current Block"
    elif index == 0:
        block_title = f"Genesis Block ({index+1}/{chain_length})"
    else:
        block_title = f"Block {index} ({index+1}/{chain_length})"

    return render_template(
        "block.html",
        block_title=block_title,
        previous_block_url=previous_block_url,
        next_block_url=next_block_url,
        block=block,
    )


@app.route("/blockchain", methods=["GET"])
def blockchain():
    global node
    info = node.get_info()
    if info is None:
        return render_template("not_initialized.html")

    chain = node.get_blockchain()

    return render_template("blockchain.html", chain=chain)


""" Run tests """

if test_case is not None:
    # Wait until node has been initialized
    thread = threading.Thread(target=node.wait_until_initialized)
    thread.start()
    thread.join()

    # Start tests
    node_info = node.get_info()
    id: int = node_info["node"]["id"]
    other_nodes = node_info["nodes"]
    id_public_key_dict = {n["id"]: n["public_key"] for n in other_nodes}

    file_path: str = os.path.join(test_case_dir, f"trans{id}.txt")
    line_cnt: int = 0
    processed_transactions: int = 0

    with open(file_path, "r") as file:
        start_time = time.time()
        for line in file:
            line_cnt += 1
            # Read the line and keep the required data (ID & Message)
            splitted_line = line.strip().split(" ", 1)
            if len(splitted_line) == 2:
                try:
                    # Parse the ID & translate it to public key
                    recipient_id = int(splitted_line[0][2:])
                    message = splitted_line[1]
                    recipient_public_key = id_public_key_dict[recipient_id]

                    # Create the transaction
                    result: bool | None = node.create_transaction(
                        recipient_address=recipient_public_key,
                        type_of_transaction=TransactionType.MESSAGE,
                        amount=0,
                        message=message,
                    )
                    processed_transactions += 1

                    if result is not None and not result:
                        print(f"Cannot execute transaction on line {line_cnt}")
                except KeyError:
                    print(f"Unknown ID {recipient_id}")
                    continue
                except ValueError:
                    print(f"Invalid ID {splitted_line[0][2:]}")
                    continue

            else:
                print(f"Invalid format on line {line_cnt}")

    # Wait until node has no more transactions in queue
    thread = threading.Thread(target=node.wait_until_queue_is_empty)
    thread.start()
    thread.join()

    # Calculate total execution time
    end_time = time.time()
    execution_time = end_time - start_time
    time.sleep(5)

    # Find how many transactions exist in the blockchain
    chain = node.get_blockchain()
    transactions_in_chain: int = 0
    blocks_in_chain: int = 0
    for block in chain:
        transactions_in_chain += len(block["transactions"])
        blocks_in_chain += 1

    # Remove the transactions/blocks that were created by default (genesis and initialization)
    initial_transactions = NUMBER_OF_NODES
    initial_blocks = 2 + ((NUMBER_OF_NODES - 1) // BLOCK_CAPACITY)

    transactions_in_chain -= initial_transactions
    blocks_in_chain -= initial_blocks

    # Report data
    throughput: float = float(transactions_in_chain) / execution_time
    block_time: float = execution_time / float(blocks_in_chain)

    report_file = os.path.join("reports", f"node{id}.txt")
    with open(report_file, "w") as file:
        file.write(
            f"{processed_transactions} transactions sent in {execution_time:.6f} seconds\n"
        )
        file.write(
            f"Total {transactions_in_chain} transactions ({blocks_in_chain} blocks) have been added in the blockchain\n"
        )

        file.write(f"Throughput: {throughput} transactions/second\n")
        file.write(f"Block Time: {block_time} seconds/block\n")


""" Start the Flask application """

app.run(host="0.0.0.0", port=port)
