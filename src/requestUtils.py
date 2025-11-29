import models
import requests
from bs4 import BeautifulSoup

def GetContents(book:models.Book): #方法，获得具体目录
    url = "https://www.ciweimao.com/chapter/get_chapter_list_in_chapter_detail"
    data = {
        "book_id": book.id,
        "chapter_id": "0",
        "orderby": "0"
    }
    
    try:
        response = models.Requests().post(url, data)
    except requests.RequestException:
        return []
    
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        
        for box in soup.select("div.book-chapter-box"):
        # 卷名
            vol_title = box.select_one("h4.sub-tit").get_text(strip=True)  # type: ignore
            chapter = models.Chapters()
            chapter.title = vol_title
            chapter.isVolIntro = True
            book.chapters.append(chapter)

            # 卷下的章节
            for a in box.select("ul.book-chapter-list li a"):
                url = a.get("href")
                # 去掉章节标题里的多余空格和换行
                title = a.get_text(strip=True)
                chapter = models.Chapters()
                chapter.title = title
                chapter.id = int(url.strip().split("/")[-1]) # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
                book.chapters.append(chapter)
        return 0
    except Exception as e:
        models.Print.err(f"[ERR] 解析章节列表失败: {e}")
        return -1

def GetName(book: models.Book): #方法，获取书籍信息
    url = f"https://www.ciweimao.com/book/{book.id}"

    try:
        try:
            response = models.Requests().post(url)
        except requests.RequestException:
            return -1
    
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:novel:book_name") #根据Meta标签寻找
        author_tag = soup.find("meta", property="og:novel:author")
        cover_tag = soup.find("meta", property="og:image")
        description_tag = soup.find("meta", property="og:description")

        if not (title_tag and author_tag and cover_tag and description_tag):
            raise ValueError(f"[WARN] 缺失必要的 meta 标签")

        name = title_tag["content"]
        author = author_tag["content"]
        coverUrl = cover_tag["content"]
        description = description_tag["content"]

        try:
            try:
                CoverResponse = models.Requests().get(coverUrl)
            except requests.RequestException:
                return []
    
            cover = CoverResponse.content
        except Exception as e:
            models.Print.warn(f"[WARN] 封面图片获取失败: {e}")
            cover = None

        book.name = str(name)
        book.author = str(author)
        book.cover = cover
        book.coverUrl = str(coverUrl)
        book.description = str(description)
        return 0

    except Exception as e:
        models.Print.warn(f"[WARN] 自动获取书籍信息失败: {e}")
        return -1
