# Seeding Checker (做种检查器)

一个功能强大的工具，用于检查NAS文件系统与BT客户端做种文件的同步状态，帮助您高效管理种子文件和优化存储空间 。


[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/yourusername/seeding-checker)
[![Docker Hub](https://img.shields.io/badge/Docker-Hub-blue)](https://hub.docker.com/r/yourusername/seeding-checker)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 项目背景

对于长期使用PT站点的用户来说，往往会面临两个常见问题：

1. **冗余文件占用空间**：下载完成后停止做种的文件仍然占用NAS存储空间
2. **丢失做种文件**：有些文件被意外删除，但下载器中仍在做种，造成下载比率统计错误

Seeding Checker就是为解决这些问题而设计的，帮助用户轻松找出NAS中不在做种的冗余文件，以及下载器中正在做种但实际已被删除的文件。

## 功能特性

- **冗余文件检测**：找出NAS中不再做种的文件，帮助释放宝贵存储空间
- **丢失文件检测**：发现下载器中正在做种但已从NAS删除的文件
- **多下载器支持**：同时支持多个qBittorrent和Transmission下载器实例
- **Docker容器化**：轻松部署在任何支持Docker的环境中
- **定时自动检查**：设置每日检查时间，自动生成详细报告
- **智能路径映射**：解决下载器容器内路径与NAS路径不一致的问题
- **多目录配置**：支持监控多个NAS目录，同时可配置排除特定目录
- **灵活阈值设置**：自定义文件大小阈值，只检查大于该大小的文件
- **详细报告输出**：生成包含文件信息、统计数据的完整报告

## 快速开始

### 使用Docker (推荐)

```bash
# 创建配置和输出目录
mkdir -p seeding-checker/config seeding-checker/output

# 启动容器
docker run -d \
  --name=seeding-checker \
  -v $(pwd)/seeding-checker/config:/app/config \
  -v $(pwd)/seeding-checker/output:/app/output \
  -v /your/nas/path1:/your/nas/path1:ro \
  -v /your/nas/path2:/your/nas/path2:ro \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  yourusername/seeding-checker:latest
```

容器首次启动时会自动在`config`目录中创建默认配置文件`config.ini`。您可以编辑此文件以配置您的NAS目录、下载器信息等。

### 使用Docker Compose

1. 创建必要的目录结构:
   ```bash
   mkdir -p config output
   ```

2. 创建 `docker-compose.yml`:
   ```yaml
   version: '3'
   
   services:
     seeding-checker:
       image: yourusername/seeding-checker:latest
       container_name: seeding-checker
       restart: unless-stopped
       volumes:
         - ./config:/app/config
         - ./output:/app/output
         # 您的NAS挂载点 - 请根据您的实际路径调整
         - /path/to/nas/data1:/path/to/nas/data1:ro
         - /path/to/nas/data2:/path/to/nas/data2:ro
       environment:
         - TZ=Asia/Shanghai
         - CONFIG_FILE=/app/config/config.ini
       user: "${UID:-1000}:${GID:-1000}"
   ```

3. 启动服务:
   ```bash
   docker-compose up -d
   ```

服务首次启动时会自动在`config`目录中创建默认配置文件`config.ini`。启动后，您可以根据需要编辑这个文件：

```bash
nano config/config.ini
```

修改配置后，重启容器使更改生效：

```bash
docker-compose restart
```

### 从源码构建

```bash
# 克隆仓库
git clone https://github.com/yourusername/seeding-checker.git
cd seeding-checker

# 创建并编辑配置
cp config.ini config/config.ini
nano config/config.ini

# 使用Docker Compose构建和启动
docker-compose up -d --build
```

## 配置指南

配置文件 `config.ini` 包含以下几个主要部分：

### 基本配置

```ini
[general]
# NAS目录路径，可以配置多个目录，用逗号分隔
nas_directories = /path/to/dir1, /path/to/dir2
# 要排除的目录路径，可以配置多个目录，用逗号分隔
exclude_directories = /path/to/dir1/temp, /path/to/dir2/system
# 最小文件大小阈值(MB)，只检查大于此大小的文件
size_threshold = 100
# 输出文件名前缀
output_file = /app/output/redundant_files
# 每日检查时间(24小时制)
schedule_time = 03:00
# 是否忽略软链接和硬链接文件
ignore_links = true
```

### 下载器配置

```ini
[downloader]
# 启用的下载器列表，用逗号分隔
enabled_clients = qb1, qb2, tr1

# qBittorrent下载器配置示例
[qb1]
type = qbittorrent
host = 192.168.1.100
port = 8080
username = admin
password = yourpassword
# 路径映射 (如果下载器容器中的路径与NAS不同)
path_mappings = /downloads=/path/to/nas/dir1

# Transmission下载器配置示例
[tr1]
type = transmission
host = 192.168.1.100
port = 9091
username = admin
password = yourpassword
# 路径映射 (如果下载器容器中的路径与NAS不同)
path_mappings = /downloads=/path/to/nas/dir2
```

## 关键配置项解释

### NAS目录设置

`nas_directories` 配置项定义了哪些目录需要检查。程序只会检查这些目录中的文件是否为冗余文件或缺失文件。对于不在此列表中的目录（例如，下载器做种的其他目录），程序会自动忽略。

```ini
# 同时检查多个目录，使用逗号分隔
nas_directories = /vol1/data, /vol2/media, /vol3/documents
```

### 路径映射

当下载器运行在容器内，而文件路径与宿主机不同时，需要设置路径映射。例如，如果下载器容器内的文件路径是 `/downloads`，而在NAS上对应 `/vol1/data`，则设置：

```ini
path_mappings = /downloads=/vol1/data
```

可以设置多个映射，用逗号分隔：

```ini
path_mappings = /downloads=/vol1/data, /movies=/vol2/media/movies
```

### 多下载器支持

可以同时配置多个下载器：

```ini
[downloader]
enabled_clients = qb1, qb2, tr1

[qb1]
type = qbittorrent
host = 192.168.1.100
port = 8080
...

[qb2]
type = qbittorrent
host = 192.168.1.101
port = 8080
...
```

## 输出结果

程序会生成两个主要报告文件：

1. **冗余文件报告**：列出NAS中不在做种列表中的文件
2. **缺失文件报告**：列出下载器中正在做种但实际已从NAS中删除的文件

两个文件都保存在配置的输出目录中，附带时间戳以区分不同时间的检查结果。

## 手动运行检查

如果想立即执行检查，可以运行：

```bash
docker exec -it seeding-checker python app.py --now
```

## 故障排除

### 路径问题

如果遇到文件无法匹配的问题：

1. 检查下载器中的文件路径与NAS实际路径是否不同
2. 确认已正确配置路径映射
3. 查看日志中的路径转换信息

### 权限错误

如果遇到权限问题：

1. 确保Docker容器用户ID和组ID设置正确
2. 检查输出目录权限
3. 验证NAS目录挂载点权限

### 连接问题

如果无法连接到下载器：

1. 确认下载器地址和端口
2. 验证用户名和密码
3. 检查下载器API是否开启
4. 确认网络连接正常

## 将项目分享到GitHub和Docker Hub

如果您是第一次分享项目，以下是详细步骤：

### 分享到GitHub

1. **创建GitHub账户**
   如果没有GitHub账户，先在 [GitHub](https://github.com/) 注册一个。

2. **创建新仓库**
   - 登录GitHub，点击右上角"+"图标，选择"New repository"
   - 输入仓库名称，如"seeding-checker"
   - 添加项目描述
   - 设置为公开(Public)
   - 勾选"Add a README file", "Add .gitignore" (选择Python模板)
   - 添加许可证(如MIT)
   - 点击"Create repository"

3. **准备本地代码**
   - 确保代码中没有敏感信息(密码、IP地址等)
   - 创建适当的.gitignore文件排除不需要上传的文件

4. **初始化本地Git仓库并上传**
   ```bash
   # 进入项目目录
   cd seeding-checker
   
   # 初始化Git仓库
   git init
   
   # 添加远程仓库
   git remote add origin https://github.com/yourusername/seeding-checker.git
   
   # 添加所有文件到暂存区
   git add .
   
   # 创建首次提交
   git commit -m "Initial commit"
   
   # 推送到GitHub
   git push -u origin main
   ```

5. **添加项目文档**
   - 完善README.md (即本文档)
   - 添加简单的贡献指南(CONTRIBUTING.md)
   - 添加许可证文件(LICENSE)

### 分享到Docker Hub

1. **创建Docker Hub账户**
   如果没有Docker Hub账户，在 [Docker Hub](https://hub.docker.com/) 注册一个。

2. **创建Dockerfile**
   确保项目中有正确配置的Dockerfile。

3. **本地构建Docker镜像**
   ```bash
   docker build -t yourusername/seeding-checker:latest .
   ```

4. **登录Docker Hub**
   ```bash
   docker login
   ```

5. **推送镜像到Docker Hub**
   ```bash
   docker push yourusername/seeding-checker:latest
   ```

6. **创建Docker Hub仓库描述**
   - 登录Docker Hub
   - 进入您的仓库页面
   - 点击"Manage Repository"添加描述、使用说明等信息
   - 可以关联GitHub仓库实现自动构建

7. **设置自动构建(可选)**
   您可以配置GitHub与Docker Hub的集成，当推送代码到GitHub时自动构建Docker镜像。

## 持续维护与更新

1. **定期更新依赖**
   检查并更新项目依赖，确保安全性和兼容性。

2. **监听用户反馈**
   鼓励用户通过GitHub Issues提交问题和建议。

3. **添加新功能**
   根据用户需求和技术发展，持续改进项目。

## 贡献指南

欢迎贡献代码、报告问题或提出改进建议：

1. Fork项目
2. 创建您的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- 感谢所有为此项目做出贡献的开发者
- 特别感谢PT社区提供的灵感和支持
- 使用的开源库：requests, humanize, schedule

---

*Seeding Checker - 您的NAS存储空间优化专家* 
