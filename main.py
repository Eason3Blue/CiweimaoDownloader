import os
import base64
import requests
import uuid
import re

from sqlalchemy import true
import decrypt
from pathlib import Path
from dataclasses import dataclass,field
from ebooklib import epub
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import mimetypes
from typing import List
from typing import Optional
@dataclass
class Chapters:
    id: int = field(default_factory=int)
    title: str = field(default_factory=str)
    content:str = field(default_factory=str)
@dataclass
class Chapter:
    chapter_id: int
    title: str
@dataclass
class BookInfo:
    name: str
    author: str
    cover: Optional[bytes]
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '', name)
def rename_files_in_folder(folder_path):
    donePath = Path("key/done")
    if donePath.exists() == True:
        return
    for filename in os.listdir(folder_path):
        full_path = os.path.join(folder_path, filename)
        if os.path.isfile(full_path):
            name, ext = os.path.splitext(filename)
            try:
                decoded = base64.b64decode(name).decode('utf-8', errors='ignore')
                new_name = decoded[:9]
                new_filename = f"{new_name}{ext}"
                new_full_path = os.path.join(folder_path, new_filename)
                os.rename(full_path, new_full_path)
                print(f"Renamed: {filename} -> {new_filename}")
            except Exception as e:
                print(f"Skipped {filename}: {e}")
    with open(donePath,"w") as f:
        f.write("OK")
    return
defaultHeaders = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6788.76 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9"
}
def getContent(book_id: int) -> List[Chapters]:
    url = "https://www.ciweimao.com/chapter/get_chapter_list_in_chapter_detail"
    headers = defaultHeaders.copy()
    data = {
        "book_id": book_id,
        "chapter_id": "0",
        "orderby": "0"
    }
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] 请求失败: {e}")
        return []
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        chapter_list = []
        for li in soup.select("ul.book-chapter-list li"):
            a_tag = li.find("a", href=True)
            if not a_tag:
                continue
            href = a_tag["href"]
            try:
                chapter_id = int(href.strip().split("/")[-1])
            except ValueError:
                continue
            raw_title = a_tag.get_text(strip=True)
            cleaned_title = ''.join(c for c in raw_title if c not in r'\/:*?"<>|')
            chapter_list.append(Chapters(chapter_id, cleaned_title))
        return chapter_list
    except Exception as e:
        print(f"[ERROR] 解析章节列表失败: {e}")
        return []
def remove_newlines_in_files(folder_path):
    donePath = Path(f"{folder_path}/done")
    if donePath.exists() == True:
        return
    folder = Path(folder_path)
    for file in folder.iterdir():
        if file.is_file():
            try:
                text = file.read_text(encoding='utf-8')
                text_no_newlines = text.replace('\r', '').replace('\n', '')
                file.write_text(text_no_newlines, encoding='utf-8')
                print(f"Processed: {file.name}")
            except Exception as e:
                print(f"Failed to process {file.name}: {e}")
    with open(donePath,"w") as f:
        f.write("OK")
    return
def getName(book_id: int) -> Optional[BookInfo]:
    url = f"https://www.ciweimao.com/book/{book_id}"
    headers = defaultHeaders.copy()

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title_tag = soup.find("meta", property="og:novel:book_name")
        author_tag = soup.find("meta", property="og:novel:author")
        cover_tag = soup.find("meta", property="og:image")

        if not (title_tag and author_tag and cover_tag):
            raise ValueError("[WARN]必要的 meta 标签缺失")

        name = title_tag["content"]
        author = author_tag["content"]
        cover_url = cover_tag["content"]

        try:
            cover_resp = requests.get(cover_url, timeout=10)
            cover_resp.raise_for_status()
            cover = cover_resp.content
        except Exception as e:
            print(f"[WARN] 封面图片获取失败: {e}")
            cover = None

        return BookInfo(name=name, author=author, cover=cover)

    except Exception as e:
        print(f"[WARN] 自动获取书籍信息失败: {e}")
        return None

def clean_html_with_images(raw_html: str, split_by_indent=True):
    img_dir = Path("images")
    soup = BeautifulSoup(raw_html, 'html.parser')

    for span in soup.find_all('span'):
        span.decompose()
    image_items = []
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src')
        if not src:
            img_tag.decompose()
            continue
        try:
            parsed = urlparse(src)
            ext = os.path.splitext(parsed.path)[-1] or '.jpg'
            filename = f"{uuid.uuid4()}{ext}"
            epub_path = img_dir / filename
            if parsed.scheme in ('http', 'https'):
                resp = requests.get(src, timeout=10)
                if resp.status_code != 200:
                    raise ValueError(f"[ERR]HTTP {resp.status_code}")
                image_data = resp.content
            else:
                with open(src, 'rb') as f:
                    image_data = f.read()
            mime_type, _ = mimetypes.guess_type(str(epub_path))
            mime_type = mime_type or 'image/jpeg'
            image_items.append(epub.EpubItem(
                uid=filename,
                file_name=epub_path.as_posix(),
                media_type=mime_type,
                content=image_data
            ))
            img_tag['src'] = epub_path.as_posix()
        except Exception as e:
            print(f"[WARN] 图像处理失败: {src} - {e}")
            img_tag.decompose()
    text = soup.get_text()
    if split_by_indent:
        paragraphs = re.split(r'(?=　　)', text)
    else:
        paragraphs = text.split('\n\n')
    text_block = ''.join(f"<p>{para.strip()}</p>" for para in paragraphs if para.strip())
    final_html = f"<div>{text_block}</div>{str(soup)}"
    return final_html, image_items
def generate_epub(chapters: List, bookName: str, bookAuthor: str, bookCover, output_path: str):
    epub_book = epub.EpubBook()
    epub_book.set_title(bookName or "Untitled Book")
    epub_book.add_author(bookAuthor or "Unknown Author")
    if bookCover and isinstance(bookCover, bytes):
        epub_book.set_cover("cover.jpg", bookCover)
    else:
        print(f"[WARN] 封面图片为空或格式不正确")
    spine = ['nav']
    epub_chapters = []
    for idx, chapter in enumerate(chapters):
        try:
            chapter_html, img_items = clean_html_with_images(chapter.content)
            c = epub.EpubHtml(
                title=chapter.title,
                file_name=f'chap_{idx + 1}.xhtml',
                lang='zh'
            )
            c.content = f"<h1>{chapter.title}</h1>{chapter_html}"
            epub_book.add_item(c)
            for img in img_items:
                epub_book.add_item(img)
            epub_chapters.append(c)
            spine.append(c)  # type: ignore
        except Exception as e:
            print(f"[ERROR] 处理第 {idx + 1} 章时出错: {e}")
    epub_book.spine = spine
    epub_book.toc = tuple(epub_chapters)  # type: ignore
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())
    try:
        epub.write_epub(output_path, epub_book, {})
        print(f"[INFO] EPUB 成功生成：{output_path}")
    except Exception as e:
        print(f"[ERROR] 写入 EPUB 失败: {e}")

if __name__ == "__main__":
    rename_files_in_folder("key")
    print("[INFO]本程序基于Zn90107UlKa/CiweimaoDownloader@github.com\n[INFO]如果您是通过被售卖的渠道获得的本软件，请您立刻申请退款。\n[INFO]仅供个人学习与技术研究\n[INFO]禁止任何形式的商业用途\n[INFO]所有内容版权归原作者及刺猬猫平台所有\n[INFO]请在 24 小时内学习后立即删除文件\n[INFO]作者不承担因不当使用导致的损失及法律后果")
    bookUrl = input("[OPT]输入你想下载的书籍Url：")
    bookId = int(bookUrl.split("/")[-1])
    bookPath = Path(f"{bookId}")
    remove_newlines_in_files(bookPath)
    chapters = getContent(bookId)
    book_info = getName(bookId)
    if not book_info:
        raise Exception("[ERR]无法获取书籍信息")
    count = 0
    FullChapters = []
    Path(f"decrypted/{bookId}").mkdir(parents=True,exist_ok=True)
    for chapter in chapters:
        chapterId = chapter.id
        chapterTitle = chapter.title
        seedPath = Path(f"key/{chapterId}")
        txtPath = Path(f"{bookId}/{chapterId}.txt")
        count += 1
        decryptedTxtPath = Path(f"decrypted/{bookId}/{count} {sanitize_filename(chapterTitle)}.txt")
        if decryptedTxtPath.exists() == True:
            with open(decryptedTxtPath) as f:
                txt = f.read()
            FullChapters.append(Chapters(chapterId,chapterTitle,txt))
            print(f"[INFO]{decryptedTxtPath} 已解码")
            continue
        try:
            with open(seedPath) as f:
                seed = f.read()
            with open(txtPath) as f:
                encryptedTxt = f.read()
            try:
                txt = decrypt.decrypt_aes_base64(encryptedTxt, seed)
                with open(decryptedTxtPath,"w") as f:
                    f.write(txt)
                print(f"[INFO]{decryptedTxtPath} 已解码")
                FullChapters.append(Chapters(chapterId,chapterTitle,txt))
            except:
                print("[ERROR]解密时发生错误")
                continue
        except:
            print(f"[WARN]{chapterTitle}未购买")
            txt = "本章未购买"
            with open(decryptedTxtPath,"w") as f:
                f.write(txt)
            FullChapters.append(Chapters(chapterId,chapterTitle,txt))
    print("[INFO]正在打包Epub...")
    generate_epub(FullChapters, book_info.name, book_info.author, book_info.cover, f"output.epub")
    input("[OPT]任意键退出程序...")
