import os
import signal
import argparse
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, jsonify

from bcc.Node import Node
from bcc.Bootstrap import Bootstrap
from bcc.Transaction import BCC_MESSAGE_FEE_PER_CHAR, BCC_TRANSFER_FEE, TransactionType

load_dotenv()
DEFAULT_PORT = int(os.getenv("DEFAULT_PORT"))

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
args = parser.parse_args()
is_bootstrap: bool = args.bootstrap
port: int = args.port
if port < DEFAULT_PORT or port > 65535:
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
        if data["recipient"] is None or len(data["recipient"]) == 0:
            return jsonify({"message": "Recipient address cannot be empty"}), 400
        elif data["type"] == "stake" and data["recipient"] != "0":
            return (
                jsonify(
                    {"message": "Recipient address must be 0 for stake transaction"}
                ),
                400,
            )
        elif data["type"] != "stake" and not any(
            n["public_key"] == data["recipient"] for n in info["nodes"]
        ):
            return jsonify({"message": "Invalid recipient address"}), 400

        recipient = data["recipient"]

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


""" Start the Flask application """

app.run(port=port)
