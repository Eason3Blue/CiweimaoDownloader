import re
import magic
import mimetypes
import base64 
import hashlib
from Crypto.Cipher import AES
from typing import Optional
from Crypto.Util.Padding import unpad

def SanitizeName(name: str) -> str: #函数，标准化章节名，避免章节名不符合Windows命名规范导致报错
    return re.sub(r'[\\/:*?"<>|]', '', name)

def CheckImageMIME(img: Optional[bytes]):
    mime = magic.from_buffer(img, mime=True) #获取图片mime
    ext = mimetypes.guess_extension(mime) #根据mime获取后缀
    if not ext:
        fallback = {
            "image/webp": ".webp",
            "image/x-icon": ".ico",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }
        ext = fallback.get(mime, "")
    return mime, ext
