import yaml
import models
import base64
from pydantic import ValidationError
from pathlib import Path
from tqdm import tqdm


def loadSetting(p : Path) -> models.Config:
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    try:
        return models.Config(**data)
    except ValidationError as e:
        models.Print.err("[ERR] 配置文件类型错误:")
        models.Print.err(f"[ERR] {e.json(indent=2)}")
        raise    


def RemoveNewlinesInEachFile(folderPath): #方法，将章节文档中的换行删去
    folder = Path(folderPath)
    if not folder.exists():
        models.Print.err("[ERR] 找不到对应的目录")
        models.Print.opt("[OPT] 按回车退出程序...")
        exit()
    
    donePath = folder / "done"
    if donePath.exists() == True:
        models.Print.info(f"[INFO] 已处理过，跳过")
        return
    
    for file in tqdm(list(folder.iterdir()), desc=models.Print.processingLabel(f"[PROCESSING] 规范化文件中")):
        if file.is_file():
            try:
                text = file.read_text(encoding='utf-8')
                result = text.replace('\r', '').replace('\n', '')
                file.write_text(result, encoding='utf-8')
            except Exception as e:
                models.Print.err(f"[ERR] 处理失败 {folderPath}/{file.name}，原因是： {e}")
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return

def TransformFilename(keyPath): #方法，将key文件名转化为chapterID
    folder = Path(keyPath)
    if not folder.exists():
        models.Print.err("[ERR] 找不到key目录")
        models.Print.opt("[OPT] 按回车退出程序...")
        exit()
    
    donePath = donePath = folder / "done"
    if donePath.exists() == True:
        models.Print.info(f"[INFO] 已处理过，跳过")
        return

    for file in tqdm(list(folder.iterdir()), desc=models.Print.processingLabel(f"[PROCESSING] 重命名中")):
        if file.is_file():
            try:
                originName = file.name
                decodedName = base64.b64decode(originName).decode('utf-8', errors='ignore')
                newName = decodedName[:9]
                file.rename(folder / newName)
            except Exception as e:
                models.Print.err(f"[ERR] 处理失败 {keyPath}/{file.name}，原因是： {e}")
    with open(donePath,"w",encoding='utf-8') as f:
        f.write("OK")
    return
