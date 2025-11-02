from pathlib import Path
import config
import fileUtils
import models
import tools

def CalculateParama(book:models.Book):
    book.safeName = tools.SanitizeName(book.name)
    book.decryptedTxt = Path(f"{book.safeName}.txt")
    count = 0
    for chapter in book.chapters:
        count += 1
        chapter.safeTitle = tools.SanitizeName(chapter.title)
        if (config.setting.cache.text == True):
            chapter.decrypted = Path(config.textFolder) / f"{count} {chapter.safeTitle}.txt"
        chapter.key = Path(f"key\\{chapter.id}")
        chapter.encryptedTxt = Path(f"{book.id}\\{chapter.id}.txt")

def init():
    global setting
    setting = fileUtils.loadSetting(Path(".\\setting.yaml"))
    if setting.batch.enable == True and setting .batch.queue.count == 0:
        models.Print.err("[ERR] 设置文件中的batch目录下的queue项设置错误，因此这个选项将不会起作用")
        setting.batch.enable = False
    global textFolder
    global imageFolder
    textFolder = ""
    imageFolder = ""
    