import base64 
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def decrypt(ciphertext_base64: str, SEED: str) -> str:
    key = hashlib.sha256(SEED.encode("utf-8")).digest()
    iv = bytes([0] * 16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext_bytes = base64.b64decode(ciphertext_base64)
    plaintext_bytes = unpad(cipher.decrypt(ciphertext_bytes), AES.block_size)
    return plaintext_bytes.decode("utf-8")
