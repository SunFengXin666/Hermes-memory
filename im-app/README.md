# IM+云盘

聊天 + 远程云盘管理 多功能桌面工具

## 功能
- 💬 **点对点聊天** — WebSocket 实时通信，私聊模式
- ☁️ **云盘** — 通过 SFTP 连接远程服务器，浏览/上传/下载/删除文件
- ⚙️ **设置** — 修改昵称

## 启动

### 方法1: 双击脚本
- **Windows**: 双击 `start.bat`
- **Linux/Mac**: `bash start.sh`

### 方法2: 手动
```bash
pip install -r requirements.txt
python app.py --port 5000
```

打开浏览器访问 `http://localhost:5000`

## 使用

1. 打开后输入昵称，点击「进入」
2. **聊天**: 左侧选用户，输入消息发送
3. **云盘**: 添加服务器（IP+端口+账号密码），连接后浏览文件
