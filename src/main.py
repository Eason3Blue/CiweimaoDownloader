from urllib.parse import urlparse
import models
import requestUtils
import fileUtils
import epubUtils
import config
import tools
import decrypt
from pathlib import Path
from tqdm import tqdm

if __name__ == "__main__":
    config.init()
    
    fileUtils.TransformFilename("key")
    book = models.Book()
    
    models.Print.info(f"[INFO] 本程序基于Zn90107UlKa/CiweimaoDownloader@github.com\n[INFO] 如果您是通过被售卖的渠道获得的本软件，请您立刻申请退款。\n[INFO] 仅供个人学习与技术研究\n[INFO] 禁止任何形式的商业用途\n[INFO] 所有内容版权归原作者及刺猬猫平台所有\n[INFO] 请在 24 小时内学习后立即删除文件\n[INFO] 作者不承担因不当使用导致的损失及法律后果")
    
    rootFolder = Path('.')
    queue = []
    
    if config.setting.batch.enable == False:
        try:
            for folder in rootFolder.iterdir():
                if folder.is_dir() and folder.name.isdigit():
                    models.Print.warn(f"[INFO] 自动模式找到了以下目录：{folder.name}")    
        except Exception as e:
            models.Print.err(f"[ERR] 自动寻找目录失败，原因是： {e}")
        
        url = models.Print.opt(f"[OPT] 输入你想下载的书籍Url或目录名字：")
        queue.append(url)
    elif config.setting.batch.auto == False: 
        queue = config.setting.batch.queue
    else:
        try:
            for folder in rootFolder.iterdir():
                if folder.is_dir() and folder.name.isdigit():
                    models.Print.warn(f"[INFO] 自动模式找到了以下目录：{folder.name}")
                    queue.append(folder.name)
        except Exception as e:
            models.Print.err(f"[ERR] 自动寻找目录失败，原因是： {e}")
    
    for url in queue:
        book = models.Book() #清空状态
        
        book.url = url
        book.id = int(urlparse(str(book.url)).path.split('/')[-1])
        if not isinstance(book.id, int):
            models.Print.err(f"[ERR] 错误的输入：{url}，这一项会被忽略")
            continue
        
        if config.setting.cache.text == True:
            try:
                config.textFolder = config.setting.cache.textFolder.format_map({
                    "bookID" : book.id
                })
                Path(config.textFolder).mkdir(parents=True,exist_ok=True)
            except Exception as e:
                models.Print.err(f"[ERR] 设置文件中，textFolder为无效地址，错误为{e}")

        if config.setting.cache.image == True:
            try:
                config.imageFolder = config.setting.cache.imageFolder.format_map({
                    "bookID" : book.id
                })
                Path(config.imageFolder).mkdir(parents=True,exist_ok=True)
            except Exception as e:
                models.Print.err(f"[ERR] 设置文件中，imageFolder为无效地址，错误为{e}")

        fileUtils.RemoveNewlinesInEachFile(Path(f"{book.id}"))
        
        if requestUtils.GetName(book) != 0: #这个方法作用到了book上
            raise Exception(f"[ERR] 无法获取书籍信息")
        else:
            models.Print.info(f"[INFO] 获取到：标题: {book.name}， 作者： {book.author}")
        
        book.safeName = tools.SanitizeName(book.name)
        book.decryptedTxt = Path(f"{book.safeName}.txt")
        if book.decryptedTxt.exists(): book.decryptedTxt.unlink(True) #避免重复写入，先删除
        
        if requestUtils.GetContents(book) != 0: #这个方法作用到了book上
            models.Print.opt(f"[OPT][ERR] 无法获取目录，请稍后再试，按回车退出程序")
            exit()
        
        for chapter in tqdm(book.chapters,desc=models.Print.processingLabel(f"[PROCESSING] 解码中")):
            if chapter.isVolIntro == False:
                if(chapter.decrypted.exists() == True): #读取缓存
                    with open(chapter.decrypted, "r", encoding="utf-8") as f:
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
                            if config.setting.cache.text == True: # 写入缓存
                                with open(chapter.decrypted,"w", encoding="utf-8") as f:
                                    f.write(txt)
                            with open(book.decryptedTxt, "a", encoding="utf-8") as f:
                                    f.write(f"{chapter.title}\n{txt}\n")
                        except Exception as e:
                            models.Print.err(f"[ERR] 保存 {str(chapter.encryptedTxt)} 时发生错误：{e}")
                            continue
                    except FileNotFoundError:
                        if (config.setting.log.notFoundWarn == True):
                            models.Print.warn(f"[WARN] {chapter.title} 未购买")
                        txt = "本章未购买"
                        chapter.content = txt
                    except Exception as e:
                        models.Print.warn(f"[WARN] {e}")
            else:
                try:
                    txt = ""
                    with open(book.decryptedTxt, "a", encoding="utf-8") as f:
                        f.write(f"{chapter.title}\n{txt}\n")
                except Exception as e:
                    models.Print.err(f"[ERR] 保存 {str(chapter.encryptedTxt)} 时发生错误：{e}")
                    continue
        
        models.Print.info(f"[INFO] txt文件已生成在：{book.safeName}")
        models.Print.info(f"[INFO] 正在打包Epub...")

        if (config.setting.homePage.enable == True): 
            models.Print.warn("[INFO] 检测到书籍主页选项打开")
            chapter = models.Chapters(isVolIntro=False, id=0, title=book.name)
            chapter.content = config.setting.homePage.style.format_map({
                "bookCover": f'<img src="{book.coverUrl}" alt="书籍封面">',
                "bookName": book.name,
                "bookAuthor": book.author,
                "bookDescription": book.description
            })
            chapter.isVolIntro = False
            book.chapters.insert(0,chapter)
        
        epubUtils.GenerateEpub(book, f"{book.safeName}.epub")
    models.Print.opt(f"[OPT] 任意键退出程序...")
