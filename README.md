# CiweimaoDownloader

一款用于下载刺猬猫（Ciweimao）平台小说的工具。操作简便，功能强大。
为了避免发生一些大家都不愿意看到的事情，我把解密的源代码删去了（不到10行代码），有兴趣的各位可以自行反编译原app查看。

温馨提示：本软件仅为了个人存档、学习使用，想要传播盗版、损坏原作者利益的请自觉离开

## 使用教程

### 1. 准备环境
* 下载并安装支持 Root 权限的安卓模拟器（如 MuMu Player）
* 下载刺猬猫 App **（推荐版本 v2.9.303）**
* 下载支持 Root 访问的文件管理器（如 MT 文件管理器）
* 下载本程序（CiweimaoDownloader）[下载页](https://github.com/Eason3Blue/CiweimaoDownloader/releases/latest)

### 2. 安装应用
1. 启动模拟器
2. 安装刺猬猫 App 和文件管理器

### 3. 下载小说章节
1. 打开刺猬猫 App 并登录
2. 长按目标小说，选择 **"下载所有章节"**
3. 等待下载完成后**静置至少 1 分钟**
4. **彻底关闭** 刺猬猫 App

### 4. 提取关键数据
1. 开启模拟器的 Root 权限
2. 授予文件管理器 Root 权限
3. 导航至以下两个关键目录：
   - `/data/data/com.kuangxiangciweimao.novel/files/Y2hlcy8`
   - `/data/data/com.kuangxiangciweimao.novel/files/novelCiwei/reader/booksnew/<小说数字ID>`
4. 将这两个文件夹完整转移到电脑：
   - **在模拟器内**：将文件夹移动到共享目录（如 MuMu Player 的 `/sdcard/$MuMu12Shared`）
   - **在电脑上**：打开模拟器共享文件夹（如 `文档/MuMuSharedFolder`）
   - 复制 `Y2hlcy8` 和 `<小说数字ID>` 文件夹
   - 粘贴到 CiweimaoDownloader 程序根目录

### 5. 重命名文件夹
1. 将 `Y2hlcy8` 重命名为 `key`
2. 保持 `<小说数字ID>` 文件夹原名不变

### 6. 获取小说链接
1. 访问 [刺猬猫官网](https://www.ciweimao.com)
2. 进入目标小说详情页
3. **完整复制浏览器地址栏 URL**（示例：`https://www.ciweimao.com/book/xxxxxxxxx`）

### 7. 运行程序
* **预编译版本**：直接双击运行程序
* **源代码版本**：
  1. 安装 Python 3.11
  2. 安装 `requirements.txt` 中的依赖
  3. 运行主程序

### 8. 获取结果
* **完整小说**：程序根目录生成 `<小说书名>.epub` 文件以及 `<小说书名>.txt`文件
* **分章文本**：`decrypted/` 目录包含每章 TXT 文件

## 版权声明

* 📖 **仅供个人学习与技术研究**  
* ⛔ **禁止任何形式的商业用途**  
* ©️ 所有内容版权归**原作者及刺猬猫平台**所有  
* ⏰ 请在 **24 小时内**学习后立即删除文件  
* ⚠️ 作者**不承担**因不当使用导致的损失及法律后果  

> 使用本软件即表示您同意上述条款
