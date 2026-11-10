# AI-security-learning

网络空间安全课程项目与学习资料。

## 东门子工业设备维护 Web 教学靶场

靶场源码、Windows 虚拟机安装方法、可选 Docker Desktop 运行、四种运行模式、自动化测试和逐项实验步骤见 [dongmenzi-lab/README.md](dongmenzi-lab/README.md) 与 [实验指导手册](dongmenzi-lab/docs/实验指导手册.md)。这是使用虚构数据的本地教学模拟，不连接真实工控设备。Docker 配置尚未在本机实测。

在 Windows PowerShell 中获取并启动安全状态：

```powershell
git clone https://github.com/alen875/AI-security-learning.git
cd AI-security-learning\dongmenzi-lab
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe init_db.py
.venv\Scripts\python.exe run_range.py --mode safe
```

浏览器打开 `http://127.0.0.1:5000/`。实验步骤、数据重置和 Kali 私网连接的命令以靶场目录内的说明为准。首次初始化生成的凭据、数据库和课堂证据只保存在使用者本机，已由 `.gitignore` 排除。
