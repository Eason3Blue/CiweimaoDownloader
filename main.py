import os
import base64
from wsgiref import headers
import requests
import mimetypes
import uuid
import re

from sqlalchemy import true

import decrypt

from pathlib import Path
from dataclasses import dataclass,field
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ebooklib import epub
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import List,Optional
from tqdm import tqdm

@dataclass
class Chapters:
    id: int = field(default_factory=int)
    title: str = field(default_factory=str)
    content:str = field(default_factory=str)

@dataclass
class BookInfo:
    name: str
    author: str
    cover: Optional[bytes]
    
defaultHeaders = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6788.76 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

def get_with_retry(url, max_retries=3, backoff_factor=0.5, timeout=10): #有自动重试的get方法
    session = requests.Session()
    session.headers = defaultHeaders.copy()

    retry_strategy = Retry(
        total=max_retries,               # 总重试次数
        status_forcelist=[403, 404, 429, 500, 502, 503, 504],  # 针对哪些状态码重试
        allowed_methods=["GET"],         # 哪些 HTTP 方法允许重试（注意大小写）
        backoff_factor=backoff_factor    # 重试间的间隔因子（指数退避）
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()  # 抛出 HTTP 错误（如 404, 500）
        return response
    except requests.RequestException as e:
        print(f"[ERROR] 请求失败: {e}")
        return None


def sanitize_filename(name: str) -> str: #函数，标准化章节名，避免章节名不符合Windows命名规范导致报错
    return re.sub(r'[\\/:*?"<>|]', '', name)

def remove_newlines_in_files(folder_path): #方法，将章节文档中的换行删去
    donePath = Path(f"{folder_path}/done")
    if donePath.exists() == True:
        print("[INFO] 已处理过，跳过")
        return
    
    folder = Path(folder_path)
    for file in tqdm(list(folder.iterdir()), desc="[PROCESSING] 规范化文件中"):
        if file.is_file():
            try:
                text = file.read_text(encoding='utf-8')
                text_no_newlines = text.replace('\r', '').replace('\n', '')
                file.write_text(text_no_newlines, encoding='utf-8')
            except Exception as e:
                print(f"[ERR] 处理失败 {folder_path}/{file.name}: {e}")
    
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return

def rename_files_in_folder(folder_path): #方法，将key文件名转化为chapterId
    donePath = Path("key/done")
    if donePath.exists() == True:
        print("[INFO] 已处理过，跳过")
        return
    
    for filename in tqdm(os.listdir(folder_path),desc="[PROCESSING] 重命名中"):
        full_path = os.path.join(folder_path, filename)
        if os.path.isfile(full_path):
            name, ext = os.path.splitext(filename)
            try:
                decoded = base64.b64decode(name).decode('utf-8', errors='ignore')
                new_name = decoded[:9]
                new_filename = f"{new_name}{ext}"
                new_full_path = os.path.join(folder_path, new_filename)
                os.rename(full_path, new_full_path)
            except Exception as e:
                print(f"[ERR] 跳过了 {filename}: {e}")
    
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return

def getContents(book_id: int) -> List[Chapters]: #方法，获得具体目录
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
        for li in soup.select("ul.book-chapter-list li"): #根据网页的每一项找到每一章节
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

def getName(book_id: int) -> Optional[BookInfo]: #方法，获取书籍信息
    url = f"https://www.ciweimao.com/book/{book_id}"
    headers = defaultHeaders.copy()

    try:
        resp = get_with_retry(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title_tag = soup.find("meta", property="og:novel:book_name") #根据Meta标签寻找
        author_tag = soup.find("meta", property="og:novel:author")
        cover_tag = soup.find("meta", property="og:image")

        if not (title_tag and author_tag and cover_tag):
            raise ValueError("[WARN] 缺失必要的 meta 标签")

        name = title_tag["content"]
        author = author_tag["content"]
        cover_url = cover_tag["content"]

        try:
            cover_resp = get_with_retry(cover_url)
            cover_resp.raise_for_status()
            cover = cover_resp.content
        except Exception as e:
            print(f"[WARN] 封面图片获取失败: {e}")
            cover = None

        return BookInfo(name=name, author=author, cover=cover)

    except Exception as e:
        print(f"[WARN] 自动获取书籍信息失败: {e}")
        return None

def clean_html_with_images(raw_html: str, split_by_indent=True): #函数，将txt中的图片链接下载并包含进入epub中
    recommandDeleted = re.sub(r'<Book\s+{[^{}]+}\s*>\s*([\s\S]{0,300})?', '', raw_html) #删去作者推书的超链接，epub不支持这个
    soup = BeautifulSoup(recommandDeleted, 'html.parser')

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
            epub_path = Path("images") / filename
            if parsed.scheme in ('http', 'https'):
                resp = get_with_retry(src)
                if resp.status_code != 200:
                    raise ValueError(f"[ERR] HTTP {resp.status_code}")
                image_data = resp.content
            else:
                with open(src, 'rb') as f:
                    image_data = f.read()
            image_items.append(epub.EpubItem(
                uid=f"img_{(filename.replace('.','_')).replace('-','_')}", #为符合xml命名规范
                file_name=epub_path.as_posix(),
                media_type="image/jpeg",
                content=image_data
            ))
            img_tag['src'] = epub_path.as_posix()
        except Exception as e:
            print(f"[WARN] 图像处理失败: {src} - {e}")
            img_tag.decompose()
    text = str(soup)
    if split_by_indent:
        paragraphs = re.split(r'(?=　　)', text)
    else:
        paragraphs = text.split('\n\n')
    text_block = ''.join(f"<p>{para.strip()}</p>" for para in paragraphs if para.strip())
    final_html = f"{text_block}"
    return final_html, image_items

def generate_epub(chapters: List, bookName: str, bookAuthor: str, bookCover, output_path: str): #方法，生成epub
    epub_book = epub.EpubBook()
    epub_book.set_title(bookName or "未命名")
    epub_book.add_author(bookAuthor or "佚名")
    if bookCover and isinstance(bookCover, bytes):
        epub_book.set_cover("cover.jpg", bookCover)
    else:
        print(f"[WARN] 封面图片为空或格式不正确")
        
    spine = ['nav']
    epub_chapters = []
    for idx, chapter in tqdm(list(enumerate(chapters)), desc="[PROCESSING]构建epub中"):

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
    
    print("[INFO] 本程序基于Zn90107UlKa/CiweimaoDownloader@github.com\n[INFO] 如果您是通过被售卖的渠道获得的本软件，请您立刻申请退款。\n[INFO] 仅供个人学习与技术研究\n[INFO]禁止任何形式的商业用途\n[INFO] 所有内容版权归原作者及刺猬猫平台所有\n[INFO] 请在 24 小时内学习后立即删除文件\n[INFO] 作者不承担因不当使用导致的损失及法律后果")
    bookUrl = input("[OPT] 输入你想下载的书籍Url：")
    
    bookId = int(bookUrl.split("/")[-1])
    bookPath = Path(f"{bookId}")
    
    remove_newlines_in_files(bookPath)
    
    chapters = getContents(bookId)
    if not chapters:
        input("[OPT][ERR] 无法获取目录，按回车退出程序，请稍后再试")
        exit
    book_info = getName(bookId)
    if not book_info:
        raise Exception("[ERR] 无法获取书籍信息")
    else:
        print(f"[INFO] 获取到：标题: {book_info.name}， 作者： {book_info.author}")
    
    count = 0
    FullChapters = []
    Path(f"decrypted/{bookId}").mkdir(parents=True,exist_ok=True)
    for chapter in tqdm(chapters,desc="[PROGRESSING] 解码中"):
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
                FullChapters.append(Chapters(chapterId,chapterTitle,txt))
            except:
                print(f"[ERROR] 解密 {str(txtPath)} 时发生错误")
                continue
        except:
            print(f"[WARN] {chapterTitle} 未购买")
            txt = "本章未购买"
            with open(decryptedTxtPath,"w",encoding='utf-8') as f:
                f.write(txt)
            FullChapters.append(Chapters(chapterId,chapterTitle,txt))
            
    print("[INFO] 正在打包Epub...")
    generate_epub(FullChapters, book_info.name, book_info.author, book_info.cover, f"output.epub")
    input("[OPT] 任意键退出程序...")
