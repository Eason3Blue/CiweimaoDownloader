import models
import uuid
import tools
import requests
import re
import config
from ebooklib import epub
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from tqdm import tqdm

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
            parsed = urlparse(str(imgUrl))
            if parsed.scheme in ('http', 'https'):
                
                if(config.setting.cache.image == False or 
                   Path(f"{config.imageFolder}\\{parsed.path.split('/')[-1]}").exists() == False): #缓存选项未开或未找到缓存
                    try:
                        response = models.Requests().get(imgUrl)
                    except requests.RequestException:
                        continue
                    if config.setting.cache.image == True:
                        with open(Path(f"{config.imageFolder}\\{parsed.path.split('/')[-1]}"), "wb") as f:
                            f.write(response.content)
                    image_data = response.content
                    mime, ext = tools.CheckImageMIME(image_data)
                    filename = f"{uuid.uuid4()}.{ext}"
                    epub_path = Path("images") / filename
                else:
                    with open(Path(f"{config.imageFolder}\\{parsed.path.split('/')[-1]}"), "rb") as f:
                        image_data = f.read()
                        
                    mime, ext = tools.CheckImageMIME(image_data)
                    filename = f"{uuid.uuid4()}.{ext}"
                    epub_path = Path("images") / filename
            else:
                continue
            
            imageItems.append(epub.EpubItem(
                # uid=f"img_{(filename.replace('.','_')).replace('-','_')}", #为符合epub的xml命名规范
                uid=f'img_{re.sub(r"[.-]", "_", filename)}',
                file_name=epub_path.as_posix(),
                media_type=mime,
                content=image_data
            ))
            imgTag['src'] = epub_path.as_posix() # type: ignore #保留图片的原有位置
        except Exception as e:
            models.Print.warn(f"[WARN] 图像处理失败: {imgUrl} - {e}")
            imgTag.decompose()
    text = str(soup) #获取imgUrl替换后的txt
    paragraphs = re.split(r'(?=　　)', text)

    textInBlock = ''.join(f"<p>{para.strip()}</p>" for para in paragraphs if para.strip())
    return textInBlock, imageItems

def ProcessChapter(idx: int, chapter: models.Chapters): # 单章节处理逻辑，方便多线程调度
    try:
        chapter_html, img_items = GetImagesInTxt(chapter.content)
        epubChapter = epub.EpubHtml(
            title=chapter.title,
            file_name=f'chap_{idx + 1}.xhtml',
            lang='zh'
        )
        epubChapter.content = f"<h1>{chapter.title}</h1>{chapter_html}"
        return idx, epubChapter, img_items, chapter.isVolIntro, None
    except Exception as e:
        return idx, None, [None], None, e

def GenerateEpub(book: models.Book, output_path: str, max_workers: int = 8):  # 增加线程池大小控制
    epub_book = epub.EpubBook()
    epub_book.set_title(book.name or "未命名")
    epub_book.add_author(book.author or "佚名")
    epub_book.set_language("zh")
    try:
        mime, ext = tools.CheckImageMIME(book.cover)
        epub_book.set_cover(f"cover.{ext}", book.cover)
    except Exception as e:
        models.Print.warn(f"[WARN] {e}")
    

    spine = ['nav']
    epub_chapters = []

    # ===== 使用线程池并行处理章节 =====
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ProcessChapter, idx, chapter): idx
                   for idx, chapter in enumerate(book.chapters)}

        for future in tqdm(as_completed(futures), total=len(futures), desc=models.Print.processingLabel(f"[PROCESSING] 构建epub中")):
            idx, epubChapter, img_items, isVol, err = future.result()
            if err:
                models.Print.err(f"[ERR] 处理第 {idx + 1} 章时出错: {err}")
                continue
            # 保持章节顺序
            for img in img_items: 
                epub_book.add_item(img)
            epub_chapters.append((idx, epubChapter, isVol))

    # ===== 按顺序添加章节和图片 =====
    epub_chapters.sort(key=lambda x: x[0])  # 按 idx 排序
    for idx, c, _ in epub_chapters:
        epub_book.add_item(c)
        spine.append(c)

    isCurInSec = False
    curVolTitle = ""
    curSecChapters = [] #每分卷的章节
    toc = [] #最终的目录
    for idx, epubChapter, isVol in epub_chapters:
        if isVol == True:
            if isCurInSec == True:
                toc.append([epub.Section(curVolTitle), curSecChapters.copy()]) #保存上一卷
            curSecChapters.clear()
            curVolTitle = epubChapter.title
            isCurInSec = True
        else:
            if isCurInSec == True:
                curSecChapters.append(epubChapter)
            else:
                toc.append(epubChapter)
    if isCurInSec:
        toc.append((epub.Section(curVolTitle),curSecChapters.copy()))


    epub_book.spine = spine
    epub_book.toc = tuple(toc)  # type: ignore
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())

    try:
        epub.write_epub(output_path, epub_book, {})
        models.Print.info(f"[INFO] EPUB 成功生成：{output_path}")
    except Exception as e:
        models.Print.err(f"[ERR] 写入 EPUB 失败: {e}")
