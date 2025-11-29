import re
import filetype
import mimetypes
import models
from typing import Optional

def SanitizeName(name: str) -> str: #函数，标准化章节名，避免章节名不符合Windows命名规范导致报错
    return re.sub(r'[\\/:*?"<>|]', '', name)

def CheckImageMIME(img: Optional[bytes]):
    kind = filetype.guess(img)
    
    if kind != None:
        mime = kind.mime #获取图片mime
        ext = kind.extension #根据mime获取后缀
    else:
        raise Exception("图片识别Mime失败")
    if not ext:
        fallback = {
            "image/webp": ".webp",
            "image/x-icon": ".ico",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }
        ext = fallback.get(mime, "")
    return mime, ext

def ProcessString(originStr:str, dataSource:models.Book, rule:dict = {}):
    rule = {
                "bookID": dataSource.id,
                "bookCover": f'<img src="{dataSource.coverUrl}" alt="书籍封面">',
                "bookName": dataSource.name,
                "bookAuthor": dataSource.author,
                "bookDescription": dataSource.description,
                "Enter": "　　"
            }
    return originStr.format_map(rule)