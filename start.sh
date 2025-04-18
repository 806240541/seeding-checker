#!/bin/bash

# 创建必要的目录
mkdir -p output config

# 如果配置文件不在config目录中，则创建
if [ ! -f config/config.ini ] && [ -f config.ini ]; then
    echo "将配置文件复制到config目录..."
    cp config.ini config/
fi

# 检查配置文件是否存在
if [ ! -f config/config.ini ]; then
    echo "错误: 配置文件 config/config.ini 不存在，请创建配置文件后再运行"
    exit 1
fi

# 设置环境变量
export UID=$(id -u)
export GID=$(id -g)
echo "使用用户ID: $UID, 组ID: $GID"

echo "检查配置文件编码格式..."
file -i config/config.ini
echo "配置文件内容预览:"
head -n 10 config/config.ini

# 显示配置信息 - 支持新版配置格式
echo "当前配置信息:"

# 获取NAS目录
if grep -q "nas_directories" config/config.ini; then
    echo "NAS目录: $(grep nas_directories config/config.ini | cut -d= -f2 | tr -d ' ')"
elif grep -q "nas_directory" config/config.ini; then
    echo "NAS目录: $(grep nas_directory config/config.ini | cut -d= -f2 | tr -d ' ')"
else
    echo "警告: 配置文件中未找到NAS目录配置"
fi

# 检查下载器配置
if grep -q "enabled_clients" config/config.ini; then
    # 新版多下载器配置
    CLIENTS=$(grep enabled_clients config/config.ini | cut -d= -f2 | tr -d ' ')
    echo "启用的下载器: $CLIENTS"
    
    # 显示每个下载器的信息
    IFS=',' read -ra CLIENT_ARRAY <<< "$CLIENTS"
    for CLIENT in "${CLIENT_ARRAY[@]}"; do
        CLIENT_TRIM=$(echo $CLIENT | xargs)
        if grep -q "\[$CLIENT_TRIM\]" config/config.ini; then
            CLIENT_TYPE=$(grep -A 5 "\[$CLIENT_TRIM\]" config/config.ini | grep "type" | cut -d= -f2 | tr -d ' ')
            CLIENT_HOST=$(grep -A 5 "\[$CLIENT_TRIM\]" config/config.ini | grep "host" | cut -d= -f2 | tr -d ' ')
            CLIENT_PORT=$(grep -A 5 "\[$CLIENT_TRIM\]" config/config.ini | grep "port" | cut -d= -f2 | tr -d ' ')
            echo "  - $CLIENT_TRIM: 类型=$CLIENT_TYPE, 地址=$CLIENT_HOST:$CLIENT_PORT"
        else
            echo "  - $CLIENT_TRIM: 警告-未找到配置部分"
        fi
    done
elif grep -q "client_type" config/config.ini; then
    # 旧版下载器配置
    echo "下载器类型: $(grep client_type config/config.ini | cut -d= -f2 | tr -d ' ')"
else
    echo "警告: 配置文件中未找到下载器类型配置"
fi

# 确保输出目录有写入权限
chmod 777 output

# 检查是否有旧的容器
if docker ps -a | grep -q seeding-checker; then
    echo "发现旧的容器，正在停止并移除..."
    docker stop seeding-checker
    docker rm seeding-checker
fi

# 构建并启动Docker容器
echo "构建并启动Docker容器..."
docker-compose up -d

echo "容器已启动，可以通过以下命令查看日志："
echo "docker logs -f seeding-checker"

# 等待几秒后查看日志
sleep 5
echo "容器日志预览:"
docker logs seeding-checker 