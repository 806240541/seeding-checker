#!/bin/bash

echo "=== 做种检查器故障排除工具 ==="
echo "该脚本将帮助您诊断和解决常见的配置问题"
echo ""

# 检查配置文件
echo "1. 检查配置文件"
if [ -f config.ini ]; then
    echo "✓ 找到配置文件 config.ini"
    
    # 检查编码格式
    echo "   检查文件编码格式:"
    ENCODING=$(file -i config.ini | grep -o "charset=.*")
    echo "   $ENCODING"
    
    if [[ "$ENCODING" != *"utf-8"* && "$ENCODING" != *"ascii"* ]]; then
        echo "⚠️ 警告: 配置文件编码不是UTF-8格式，可能导致读取错误"
        echo "   建议使用UTF-8编码保存配置文件"
        echo "   尝试转换文件编码..."
        
        cp config.ini config.ini.bak
        iconv -f $(echo $ENCODING | cut -d= -f2) -t UTF-8 config.ini.bak > config.ini.utf8
        
        if [ $? -eq 0 ]; then
            mv config.ini.utf8 config.ini
            echo "✓ 已将配置文件转换为UTF-8编码"
        else
            echo "✗ 转换失败，请手动使用文本编辑器打开并以UTF-8格式保存"
        fi
    fi
    
    # 检查配置部分是否存在
    echo "   检查配置内容:"
    
    if grep -q "^\[general\]" config.ini; then
        echo "   ✓ [general] 部分存在"
    else
        echo "   ✗ 缺少 [general] 部分，这是必须的！"
        echo "   修复: 在配置文件开头添加 [general] 部分"
    fi
    
    if grep -q "^\[downloader\]" config.ini; then
        echo "   ✓ [downloader] 部分存在"
    else
        echo "   ✗ 缺少 [downloader] 部分"
    fi
    
    if grep -q "^\[qbittorrent\]" config.ini || grep -q "^\[transmission\]" config.ini; then
        echo "   ✓ 下载器配置部分存在"
    else
        echo "   ✗ 缺少下载器配置部分 [qbittorrent] 或 [transmission]"
    fi
    
    # 检查必要的配置项
    MISSING_ITEMS=0
    
    if ! grep -q "nas_directory" config.ini; then
        echo "   ✗ 缺少 nas_directory 配置"
        MISSING_ITEMS=$((MISSING_ITEMS+1))
    fi
    
    if ! grep -q "size_threshold" config.ini; then
        echo "   ✗ 缺少 size_threshold 配置"
        MISSING_ITEMS=$((MISSING_ITEMS+1))
    fi
    
    if ! grep -q "schedule_time" config.ini; then
        echo "   ✗ 缺少 schedule_time 配置"
        MISSING_ITEMS=$((MISSING_ITEMS+1))
    fi
    
    if ! grep -q "client_type" config.ini; then
        echo "   ✗ 缺少 client_type 配置"
        MISSING_ITEMS=$((MISSING_ITEMS+1))
    fi
    
    if [ $MISSING_ITEMS -gt 0 ]; then
        echo "   ⚠️ 缺少 $MISSING_ITEMS 个必要配置项"
        echo "   建议: 参考 README.md 中的配置示例"
    else
        echo "   ✓ 所有必要配置项已存在"
    fi
else
    echo "✗ 配置文件 config.ini 不存在"
    
    # 创建默认配置文件
    echo "   创建默认配置文件..."
    cat > config.ini << EOL
[general]
# NAS目录路径，将扫描该目录下的所有文件
nas_directory = /vol3/1000/Movie/
# 最小文件大小阈值(MB)，只检查大于此大小的文件
size_threshold = 100
# 输出文件名前缀
output_file = redundant_files
# 每日检查时间(24小时制)
schedule_time = 03:00

[downloader]
# 下载器类型: qbittorrent 或 transmission
client_type = qbittorrent

[qbittorrent]
host = 192.168.50.111
port = 8085
username = admin
password = yourpassword

[transmission]
host = 192.168.50.111
port = 9091
username = admin
password = yourpassword
EOL

    echo "   ✓ 已创建默认配置文件 config.ini"
    echo "   请编辑此文件设置正确的配置信息，特别是下载器的密码"
fi

echo ""

# 检查Docker环境
echo "2. 检查Docker环境"
if command -v docker >/dev/null 2>&1; then
    echo "✓ Docker已安装"
    
    if command -v docker-compose >/dev/null 2>&1; then
        echo "✓ Docker Compose已安装"
    else
        echo "✗ Docker Compose未安装"
        echo "  请安装Docker Compose后再继续"
    fi
    
    # 检查容器状态
    if docker ps | grep -q seeding-checker; then
        echo "✓ 容器正在运行"
        
        # 检查容器日志
        echo "   容器日志预览:"
        docker logs --tail 10 seeding-checker
    else
        echo "✗ 容器未运行"
        
        if docker ps -a | grep -q seeding-checker; then
            echo "   容器存在但未运行，尝试查看最后的错误日志:"
            docker logs --tail 20 seeding-checker
            
            echo "   重新启动容器..."
            docker-compose up -d
        else
            echo "   容器不存在，尝试启动..."
            docker-compose up -d
        fi
    fi
else
    echo "✗ Docker未安装"
    echo "  请先安装Docker和Docker Compose"
fi

echo ""

# 检查NAS目录
echo "3. 检查NAS目录"
NAS_DIR=$(grep nas_directory config.ini | cut -d= -f2 | tr -d ' ')

if [ -n "$NAS_DIR" ]; then
    echo "   配置的NAS目录: $NAS_DIR"
    
    if [ -d "$NAS_DIR" ]; then
        echo "✓ NAS目录存在"
        
        # 检查目录权限
        if [ -r "$NAS_DIR" ]; then
            echo "✓ 有读取权限"
            
            # 统计目录中的文件数量
            FILE_COUNT=$(find "$NAS_DIR" -type f | wc -l)
            echo "   目录中包含 $FILE_COUNT 个文件"
        else
            echo "✗ 无法读取目录，请检查权限"
        fi
    else
        echo "✗ NAS目录不存在，请检查路径是否正确"
    fi
else
    echo "✗ 配置文件中未找到NAS目录配置"
fi

echo ""
echo "故障排除完成，如果问题依然存在，请查看上述输出中的错误提示" 