import rsa
from typing import TypedDict


class Wallet(TypedDict):
    public_key: str
    private_key: str


def generate_wallet() -> Wallet:
    """
    Creates a new wallet with a private and a public key for
    encryption with RSA algorithm, and returns a dictionary
    with {public_key, private_key}
    """
    public_key, private_key = rsa.newkeys(2048)
    public_key_PEM: str = str(public_key.save_pkcs1().decode("utf-8"))
    private_key_PEM: str = str(private_key.save_pkcs1().decode("utf-8"))
    return {
        "public_key": public_key_PEM,
        "private_key": private_key_PEM,
    }


def encrypt_message(message: str, public_key: str) -> str:
    """
    Encrypts a given string message with given public key using RSA algorithm,
    and returns the encrypted message in HEX format

    Keyword arguments:
    message -- The string message to be encrypted
    public_key -- The PEM-formatted public key
    """
    public_key_bytes: bytes = public_key.encode("utf-8")
    key: rsa.PublicKey = rsa.PublicKey.load_pkcs1(public_key_bytes)
    encoded_message: bytes = message.encode("utf-8")
    return rsa.encrypt(encoded_message, key).hex()


def decrypt_message(message: str, private_key: str) -> str:
    """
    Decrypts a given string message (in HEX format) with given
    private key using RSA algorithm, and returns the decrypted message

    Keyword arguments:
    message -- The encrypted string message (in HEX format)
    private_key -- The PEM-formatted private key
    """
    private_key_bytes: bytes = private_key.encode("utf-8")
    key: rsa.PrivateKey = rsa.PrivateKey.load_pkcs1(private_key_bytes)
    decoded_message: bytes = bytes.fromhex(message)
    return rsa.decrypt(decoded_message, key).decode("utf-8")


def calculate_hash(message: str) -> str:
    """
    Returns a message's hash, using SHA-256 algorithm.
    """
    encoded_message: bytes = message.encode("utf-8")
    hash: bytes = rsa.compute_hash(encoded_message, "SHA-256")
    return hash.hex()


def sign_message(message: str, private_key: str) -> str:
    """
    Signs a given string message with given private key using RSA algorithm,
    and returns the signature in HEX format

    Keyword arguments:
    message -- The hashed string message to be signed
    private_key -- The PEM-formatted private key
    """
    private_key_bytes: bytes = private_key.encode("utf-8")
    key: rsa.PrivateKey = rsa.PrivateKey.load_pkcs1(private_key_bytes)
    encoded_message: bytes = message.encode("utf-8")
    signature: str = rsa.sign(encoded_message, key, "SHA-256").hex()
    return signature


def verify_message(message: str, signature: str, public_key: str) -> bool:
    """
    Verifies that a given string message is signed by a certain public key,
    given the signature (in HEX format) and using RSA algorithm.
    Returns True if the verification is succesfull, otherwise False

    Keyword arguments:
    message -- The raw (not hased) string message to be verified
    signature -- The signature to be verified (in HEX format)
    public_key -- The PEM-formatted public key
    """
    public_key_bytes: bytes = public_key.encode("utf-8")
    key: rsa.PublicKey = rsa.PublicKey.load_pkcs1(public_key_bytes)
    decoded_signature: bytes = bytes.fromhex(signature)
    encoded_message: bytes = message.encode("utf-8")
    try:
        rsa.verify(encoded_message, decoded_signature, key)
        return True
    except rsa.VerificationError:
        return False
