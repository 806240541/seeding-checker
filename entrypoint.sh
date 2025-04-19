#!/bin/bash
set -e

# 确保输出目录存在
mkdir -p /app/output
chmod -R 777 /app/output

# 确保配置目录存在
mkdir -p /app/config
chmod -R 777 /app/config

# 默认配置文件路径
CONFIG_PATH="${CONFIG_FILE:-/app/config/config.ini}"
CONFIG_DIR=$(dirname "$CONFIG_PATH")

# 确保配置目录存在
mkdir -p "$CONFIG_DIR"

# 如果配置文件不存在，创建默认配置
if [ ! -f "$CONFIG_PATH" ]; then
    echo "配置文件不存在，创建默认配置: $CONFIG_PATH"
    # 尝试复制内置的模板配置文件
    if [ -f "/app/config.ini" ]; then
        cp /app/config.ini "$CONFIG_PATH"
        echo "已从内置模板创建配置文件"
    else
        # 如果没有内置模板，创建一个基本配置
        cat > "$CONFIG_PATH" << 'EOF'
[general]
# NAS目录路径，可以配置多个目录，用逗号分隔
nas_directories = /vol3/1000
# 要排除的目录路径，可以配置多个目录，用逗号分隔
exclude_directories = 
# 最小文件大小阈值(MB)，只检查大于此大小的文件
size_threshold = 100
# 输出文件名前缀
output_file = /app/output/redundant_files
# 每日检查时间(24小时制)
schedule_time = 03:00
# 是否忽略软链接和硬链接文件
ignore_links = true

[downloader]
# 启用的下载器列表，用逗号分隔
enabled_clients = qb1

# qBittorrent下载器配置示例
[qb1]
type = qbittorrent
host = 192.168.1.100
port = 8080
username = admin
password = adminpassword
# 路径映射 (如果下载器容器中的路径与NAS不同)
path_mappings = 
EOF
        echo "已创建基本配置文件"
    fi
    
    # 设置合适的权限，确保配置文件可读写
    chmod 666 "$CONFIG_PATH"
else
    echo "配置文件已存在: $CONFIG_PATH"
fi

# 检查app.py是否存在
if [ ! -f "/app/app.py" ]; then
    echo "错误: 找不到应用程序文件 /app/app.py"
    exit 1
fi

echo "启动Seeding Checker..."
echo "当前目录: $(pwd)"
echo "目录内容:"
ls -la

# 执行传入的命令或默认命令
if [ $# -eq 0 ]; then
    # 默认命令
    exec python /app/app.py --config "$CONFIG_PATH"
else
    # 用户指定的命令
    exec "$@"
fi 