import base64
import requests
import uuid
import re
import magic
import mimetypes

import decrypt

from colorama import init, Fore, Style, Back
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
    decrypted: Path = field(default_factory=Path)
    key: Path = field(default_factory=Path)
    encryptedTxt: Path = field(default_factory=Path)
    title: str = field(default_factory=str)
    content:str = field(default_factory=str)

@dataclass
class Book:
    id: int = field(default_factory=int)
    url: str = field(default_factory=str)
    chapters: list = field(default_factory=list)
    safeName: str = field(default_factory=str)
    name: str = field(default_factory=str)
    author: str = field(default_factory=str)
    cover: Optional[bytes] = field(default_factory=bytes)
    
    decryptedFolder: Path = field(default_factory=Path)
    decryptedTxt: Path = field(default_factory=Path)

init(autoreset=True)
class Print:
    @staticmethod
    def err(msg): print(Back.RED + Fore.WHITE + Style.BRIGHT + f"{msg}")
    @staticmethod
    def warn(msg): print(Back.LIGHTYELLOW_EX + Fore.BLACK + Style.BRIGHT + f"{msg}")
    @staticmethod
    def info(msg): print(f"{msg}")
    @staticmethod
    def opt(msg): return input(Back.LIGHTWHITE_EX + Fore.BLACK + f"{msg}")
    @staticmethod
    def processingLabel(msg):
        return Back.LIGHTBLUE_EX + Style.BRIGHT + Fore.WHITE + f"{msg}" + Style.RESET_ALL

class Requests:
    def __init__(self, maxRetries=3, backoff=0.5, timeout=10):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6788.76 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

        retry_strategy = Retry(
            total=maxRetries,
            status_forcelist=[403, 404, 429, 500, 502, 503, 504],
            allowed_methods={"GET", "POST"},
            backoff_factor=backoff
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.timeout = timeout

    def get(self, url, params=None):
        if params is None:
            params = {}
        return self.session.get(url, timeout=self.timeout, params=params)

    def post(self, url, data=None):
        if data is None:
            data = {}
        return self.session.post(url, timeout=self.timeout, data=data)

def SanitizeName(name: str) -> str: #函数，标准化章节名，避免章节名不符合Windows命名规范导致报错
    return re.sub(r'[\\/:*?"<>|]', '', name)

def RemoveNewlinesInEachFile(folderPath): #方法，将章节文档中的换行删去
    folder = Path(folderPath)
    
    donePath = folder / "done"
    if donePath.exists() == True:
        Print.info(f"[INFO] 已处理过，跳过")
        return
    
    for file in tqdm(list(folder.iterdir()), desc=Print.processingLabel(f"[PROCESSING] 规范化文件中")):
        if file.is_file():
            try:
                text = file.read_text(encoding='utf-8')
                result = text.replace('\r', '').replace('\n', '')
                file.write_text(result, encoding='utf-8')
            except Exception as e:
                Print.err(f"[ERR] 处理失败 {folderPath}/{file.name}，原因是： {e}")
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return

def TransformFilename(keyPath): #方法，将key文件名转化为chapterI
    folder = Path(keyPath)
    
    donePath = donePath = folder / "done"
    if donePath.exists() == True:
        Print.info(f"[INFO] 已处理过，跳过")
        return

    for file in tqdm(list(folder.iterdir()), desc=Print.processingLabel(f"[PROCESSING] 重命名中")):
        if file.is_file():
            try:
                originName = file.name
                decodedName = base64.b64decode(originName).decode('utf-8', errors='ignore')
                newName = decodedName[:9]
                file.rename(folder / newName)
            except Exception as e:
                Print.err(f"[ERR] 处理失败 {keyPath}/{file.name}，原因是： {e}")
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return

def getContents(book:Book): #方法，获得具体目录
    url = "https://www.ciweimao.com/chapter/get_chapter_list_in_chapter_detail"
    data = {
        "book_id": book.id,
        "chapter_id": "0",
        "orderby": "0"
    }
    
    try:
        response = Requests().post(url, data)
    except requests.RequestException:
        return []
    
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        count = 0
        for li in soup.select("ul.book-chapter-list li"): #根据网页的每一项找到每一章节
            count += 1
            a = li.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            try:
                id = int(href.strip().split("/")[-1])
            except ValueError:
                continue
            title = a.get_text(strip=True)

            chapter = Chapters(id = id, title = title)
            chapter.decrypted = book.decryptedFolder / f"{count} {SanitizeName(chapter.title)}.txt"
            chapter.key = Path(f"key/{chapter.id}")
            chapter.encryptedTxt = Path(f"{book.id}/{chapter.id}.txt")
            book.chapters.append(chapter)
        return 0
    except Exception as e:
        Print.err(f"[ERR] 解析章节列表失败: {e}")
        return -1

def getName(book: Book) -> Optional[Book]: #方法，获取书籍信息
    url = f"https://www.ciweimao.com/book/{book.id}"

    try:
        try:
            response = Requests().post(url)
        except requests.RequestException:
            return []
    
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:novel:book_name") #根据Meta标签寻找
        author_tag = soup.find("meta", property="og:novel:author")
        cover_tag = soup.find("meta", property="og:image")

        if not (title_tag and author_tag and cover_tag):
            raise ValueError(f"[WARN] 缺失必要的 meta 标签")

        name = title_tag["content"]
        author = author_tag["content"]
        coverUrl = cover_tag["content"]

        try:
            try:
                CoverResponse = Requests().get(coverUrl)
            except requests.RequestException:
                return []
    
            cover = CoverResponse.content
        except Exception as e:
            Print.warn(f"[WARN] 封面图片获取失败: {e}")
            cover = None

        book.name = name
        book.author = author
        book.cover = cover
        return 0

    except Exception as e:
        Print.warn(f"[WARN] 自动获取书籍信息失败: {e}")
        return -1

def GetImagesInTxt(raw: str): #函数，将txt中的图片链接下载并包含进入epub中
    recommandDeleted = re.sub(r'<Book\s+{[^{}]+}\s*>\s*([\s\S]{0,300})?', '', raw) #删去作者推书的超链接，epub不支持这个
    soup = BeautifulSoup(recommandDeleted, 'html.parser')

    for span in soup.find_all('span'):
        span.decompose()
    
    imageItems = []
    for imgTag in soup.find_all('img'):
        imgUrl = imgTag.get('src')
        if not imgUrl:
            imgTag.decompose()
            continue
        try:
            parsed = urlparse(imgUrl)
            if parsed.scheme in ('http', 'https'):
                try:
                    response = Requests().get(imgUrl)
                except requests.RequestException:
                    continue
    
                image_data = response.content
                mime = magic.from_buffer(image_data, mime=True) #获取图片mime，符合epub检查
                ext = mimetypes.guess_extension(mime) #根据mime获取后缀
                if not ext:
                    fallback = {
                        "image/webp": ".webp",
                        "image/x-icon": ".ico",
                        "image/heic": ".heic",
                        "image/heif": ".heif",
                    }
                    ext = fallback.get(mime, "")
                filename = f"{uuid.uuid4()}{ext}"
                epub_path = Path("images") / filename
            else:
                continue
            
            imageItems.append(epub.EpubItem(
                uid=f"img_{(filename.replace('.','_')).replace('-','_')}", #为符合epub的xml命名规范
                file_name=epub_path.as_posix(),
                media_type=mime,
                content=image_data
            ))
            imgTag['src'] = epub_path.as_posix() #保留图片的原有位置
        except Exception as e:
            Print.warn(f"[WARN] 图像处理失败: {imgUrl} - {e}")
            imgTag.decompose()
    text = str(soup) #获取imgUrl替换后的txt
    paragraphs = re.split(r'(?=　　)', text)

    textInBlock = ''.join(f"<p>{para.strip()}</p>" for para in paragraphs if para.strip())
    return textInBlock, imageItems

def generateEpub(book:Book, output_path: str): #方法，生成epub
    epub_book = epub.EpubBook()
    epub_book.set_title(book.name or "未命名")
    epub_book.add_author(book.author or "佚名")
    if book.cover and isinstance(book.cover, bytes):
        epub_book.set_cover("cover.jpg", book.cover)
    else:
        Print.warn(f"[WARN] 封面图片为空或格式不正确")
    epub_book.set_language("zh")
        
    spine = ['nav']
    epub_chapters = []
    for idx, chapter in tqdm(list(enumerate(book.chapters)), desc=Print.processingLabel(f"[PROCESSING] 构建epub中")):

        try:
            chapter_html, img_items = GetImagesInTxt(chapter.content)
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
            Print.err(f"[ERR] 处理第 {idx + 1} 章时出错: {e}")
    
    epub_book.spine = spine
    epub_book.toc = tuple(epub_chapters)  # type: ignore
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())
    
    try:
        epub.write_epub(output_path, epub_book, {})
        Print.info(f"[INFO] EPUB 成功生成：{output_path}")
    except Exception as e:
        Print.err(f"[ERR] 写入 EPUB 失败: {e}")

if __name__ == "__main__":
    TransformFilename("key")
    book = Book()
    
    Print.info(f"[INFO] 本程序基于Zn90107UlKa/CiweimaoDownloader@github.com\n[INFO] 如果您是通过被售卖的渠道获得的本软件，请您立刻申请退款。\n[INFO] 仅供个人学习与技术研究\n[INFO] 禁止任何形式的商业用途\n[INFO] 所有内容版权归原作者及刺猬猫平台所有\n[INFO] 请在 24 小时内学习后立即删除文件\n[INFO] 作者不承担因不当使用导致的损失及法律后果")
    book.url = Print.opt(f"[OPT] 输入你想下载的书籍Url：")
    
    book.id = int(book.url.split("/")[-1])
    if not isinstance(book.id, int):
        Print.opt("[OPT][ERR] 错误的输入，按回车退出程序")
        exit()

    RemoveNewlinesInEachFile(Path(f"{book.id}"))
    
    if getName(book) != 0: #这个方法作用到了book上
        raise Exception(f"[ERR] 无法获取书籍信息")
    else:
        Print.info(f"[INFO] 获取到：标题: {book.name}， 作者： {book.author}")
    
    book.safeName = SanitizeName(book.name)
    book.decryptedFolder = Path(f"decrypted/{book.id}")
    book.decryptedFolder.mkdir(parents=True,exist_ok=True)
    book.decryptedTxt = Path(f"{book.safeName}.txt")
    
    if getContents(book) != 0: #这个方法作用到了book上
        Print.opt(f"[OPT][ERR] 无法获取目录，请稍后再试，按回车退出程序")
        exit()
    
    

    for chapter in tqdm(book.chapters,desc=Print.processingLabel(f"[PROCESSING] 解码中")):
        if chapter.decrypted.exists() == True:
            with open(chapter.decrypted, "r", encoding="utf-8") as f: #读取缓存
                txt = f.read()
                chapter.content = txt
            with open(book.decryptedTxt, "a", encoding="utf-8") as f:
                f.write(chapter.title + "\n" + txt + "\n\n")
            continue
        else:
            try:
                with open(chapter.key, 'r' , encoding="utf-8") as f:
                    seed = f.read()
                with open(chapter.encryptedTxt, 'r', encoding="utf-8") as f:
                    encryptedTxt = f.read()
                    
                try:
                    txt = decrypt.decrypt(encryptedTxt, seed)
                    chapter.content = txt
                    with open(chapter.decrypted,"w", encoding="utf-8") as f:
                        f.write(txt)
                    with open(book.decryptedTxt, "a", encoding="utf-8") as f:
                        f.write(f"{chapter.title}\n{txt}\n")
                except Exception as e:
                    Print.err(f"[ERR] 解密 {str(chapter.encryptedTxt)} 时发生错误：{e}")
                    continue
            except FileNotFoundError:
                Print.warn(f"[WARN] {chapter.title} 未购买")
                txt = "本章未购买"
                chapter.content = txt
            except Exception as e:
                Print.warn(f"[WARN] {e}")
    
    Print.info(f"[INFO] txt文件已生成在：{book.safeName}")
    Print.info(f"[INFO] 正在打包Epub...")
    generateEpub(book, f"{book.safeName}.epub")
    Print.opt(f"[OPT] 任意键退出程序...")
