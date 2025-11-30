# =============================== #
#   EPUB Pipeline Generator       #
#   Threaded Producer + Async Consumer
#   Designed for high performance &
#   low memory usage EPUB building
# =============================== #

import models
import uuid
import tools
import asyncio
import re
import aiofiles
import config
from ebooklib import epub
from asyncHttp import AsyncHTTP
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from tqdm import tqdm

# ---------------------------------------
# STEP 1: ========== 章解析（同步多线程）
# ---------------------------------------

def parse_chapter(idx: int, chapter: models.Chapters):
    """解析章节，不下载图片，只抽取 URL + 生成 HTML."""
    try:
        raw = chapter.content or ""
        cleaned = re.sub(r'<Book\s+{[^{}]+}>\s*([\s\S]{0,300})?', '', raw)
        soup = BeautifulSoup(cleaned, "html.parser")

        # 删除 span
        for span in soup.find_all('span'):
            span.decompose()

        img_urls = []
        for img in soup.find_all('img'):
            src = img.get("src")
            if not src:
                img.decompose()
                continue

            parsed = urlparse(str(src))
            if parsed.scheme in ("http", "https"):
                img_urls.append(str(src))
            else:
                img.decompose()

        text = str(soup)
        paragraphs = re.split(r'(?=　　)', text)
        html = ''.join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

        return idx, chapter.title ,html, chapter.isVolIntro, img_urls, None
    except Exception as e:
        return idx, None, None, None, [], e


# ---------------------------------------
# STEP 2: ========== Pipeline: 图片下载器
# ---------------------------------------

async def fetch_with_cache(url: str) -> tuple[str, bytes | None]:
    """下载单图，支持缓存，失败返回 None."""

    parsed = urlparse(url)
    fname = parsed.path.split("/")[-1] or uuid.uuid4().hex
    cache_path = Path(config.imageFolder) / fname

    # 如果开启缓存 & 存在
    if (
        getattr(config, "setting", None)
        and getattr(config.setting, "cache", None)
        and getattr(config.setting.cache, "image", False)
        and cache_path.exists()
    ):
        try:
            async with aiofiles.open(cache_path, "rb") as f:
                return url, await f.read()
        except:
            pass  # 缓存读取失败则继续下载

    # 网络下载
    try:
        data = await AsyncHTTP.get(url)
    except Exception as e:
        models.Print.err(f"[ERR] 下载失败: {url} {e}")
        return url, None

    # 写缓存
    if (
        getattr(config, "setting", None)
        and getattr(config.setting, "cache", None)
        and getattr(config.setting.cache, "image", False)
    ):
        try:
            Path(config.imageFolder).mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(data)
        except:
            pass

    return url, data


async def image_worker(queue: asyncio.Queue,
                       results: dict[str, bytes | None],
                       sem: asyncio.Semaphore):
    """消费者 worker：持续从队列取 URL，下载，保存结果."""
    while True:
        url = await queue.get()
        if url is None:       # poison pill
            queue.task_done()
            return

        async with sem:
            u, data = await fetch_with_cache(url)
            results[u] = data

        queue.task_done()


# ---------------------------------------
# STEP 3: ========== 主流程
# ---------------------------------------

def GenerateEpub(book: models.Book,
                 output_path: str,
                 max_workers: int = 8,
                 max_img_tasks: int = 16):

    # 初始化 EPUB
    epub_book = epub.EpubBook()
    epub_book.set_title(book.name or "未命名")
    epub_book.add_author(book.author or "佚名")
    epub_book.set_language("zh")

    # 封面
    try:
        mime, ext = tools.CheckImageMIME(book.cover)
        if ext.startswith("."):
            ext = ext[1:]
        epub_book.set_cover(f"cover.{ext}", book.cover)
    except Exception as e:
        models.Print.warn(f"[WARN] 封面读取失败: {e}")

    # ===============================
    # A. 多线程解析章节（生产者）
    # ===============================
    chapter_infos = []
    all_urls = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(parse_chapter, idx, chap): idx
            for idx, chap in enumerate(book.chapters)
        }

        for fut in tqdm(as_completed(futures),
                        total=len(futures),
                        desc="[PROCESS] 解析章节..."):
            idx, title, html, isVol, urls, err = fut.result()
            if err:
                models.Print.err(f"[ERR] 解析章节 {idx+1} 失败: {err}")
                continue

            chapter_infos.append((idx, title, html, isVol))
            all_urls.extend(urls)

    chapter_infos.sort(key=lambda x: x[0])

    # ===============================
    # B. 异步图片下载 Pipeline
    # ===============================

    async def pipeline_main(unique_urls: list[str]):
        """一个事件循环，生产者（线程池部份）已把 URL 提供给我们。"""
        await AsyncHTTP.init()              # 启动 HTTP session

        queue = asyncio.Queue()
        results = {}                        # url → bytes

        # 去重后的 URL 塞入队列（producer）
        for u in unique_urls:
            queue.put_nowait(u)

        # 控制并发
        sem = asyncio.Semaphore(max_img_tasks)

        # 启动 workers
        workers = [
            asyncio.create_task(image_worker(queue, results, sem))
            for _ in range(max_img_tasks)
        ]

        # 塞入 poison pill
        for _ in workers:
            queue.put_nowait(None)

        await queue.join()

        # 停掉 workers
        for w in workers:
            w.cancel()

        try:
            await AsyncHTTP.close()
        except:
            pass

        return results

    unique_urls = list(dict.fromkeys(all_urls))
    if unique_urls:
        models.Print.info(f"[INFO] Pipeline 下载图片: {len(unique_urls)}")
        url_to_bytes = asyncio.run(pipeline_main(unique_urls))
    else:
        url_to_bytes = {}

    # ===============================
    # C. 添加图片到 EPUB + 替换 HTML src
    # ===============================
    url_to_epubpath = {}

    for url, data in url_to_bytes.items():
        if not data:
            continue

        mime, ext = tools.CheckImageMIME(data)
        if ext.startswith("."):
            ext = ext[1:]
        filename = f"{uuid.uuid4().hex}.{ext}"
        epub_path = f"images/{filename}"

        item = epub.EpubItem(
            uid=f"img_{uuid.uuid4().hex}",
            file_name=epub_path,
            media_type=mime,
            content=data
        )
        epub_book.add_item(item)
        url_to_epubpath[url] = epub_path

    # ===============================
    # D. 构建章节
    # ===============================
    spine = ["nav"]
    epub_chapters = []

    for idx, title ,html, isVol in chapter_infos:
        for url, rep in url_to_epubpath.items():
            if url in html:
                html = html.replace(url, rep)

        chap = epub.EpubHtml(
            title=title,
            file_name=f"chap_{idx+1}.xhtml",
            lang="zh"
        )
        chap.content = f"<h1>{html_title(book, idx)}</h1>{html}"

        epub_book.add_item(chap)
        epub_chapters.append((idx, chap, isVol))
        spine.append(chap) # pyright: ignore[reportArgumentType]

    # ===============================
    # E. 目录 (TOC)
    # ===============================
    toc = []
    curVol = None
    curList = []

    for idx, chap, isVol in epub_chapters:
        if isVol:
            if curVol and curList:
                toc.append([epub.Section(curVol.title), curList.copy()])
            curVol = chap
            curList.clear()
        else:
            if curVol:
                curList.append(chap)
            else:
                toc.append(chap)

    if curVol:
        toc.append([epub.Section(curVol.title), curList.copy()])

    epub_book.spine = spine
    epub_book.toc = list(tuple(toc))
    epub_book.add_item(epub.EpubNav())
    epub_book.add_item(epub.EpubNcx())

    # ===============================
    # F. 写入 EPUB
    # ===============================
    try:
        epub.write_epub(output_path, epub_book, {})
        models.Print.info(f"[INFO] EPUB 生成成功：{output_path}")
    except Exception as e:
        models.Print.err(f"[ERR] EPUB 写入失败: {e}")


def html_title(book, idx):
    try:
        return book.chapters[idx].title or f"章节 {idx+1}"
    except:
        return f"章节 {idx+1}"
