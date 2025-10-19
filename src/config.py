from pathlib import Path
import fileUtils
from models import Print
def init():
    global setting
    setting = fileUtils.loadSetting(Path(".\\setting.yaml"))
    if setting.batch.enable == True and setting .batch.queue.count == 0:
        Print.err("[ERR] 设置文件中的batch目录下的queue项设置错误，因此这个选项将不会起作用")
        setting.batch.enable = False
    global textFolder
    global imageFolder
    textFolder = ""
    imageFolder = ""
    