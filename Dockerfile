FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建配置和输出目录并设置权限
RUN mkdir -p /app/output /app/config && \
    chmod -R 777 /app/output /app/config

# 首先复制所有文件到容器
COPY . .

# 确保启动脚本有执行权限
RUN if [ -f /app/entrypoint.sh ]; then chmod +x /app/entrypoint.sh; fi

# 列出/app目录内容以便调试
RUN echo "Listing /app directory:" && \
    ls -la /app && \
    if [ -f /app/app.py ]; then \
      echo "app.py found" && \
      chmod +x /app/app.py; \
    else \
      echo "WARNING: app.py NOT found in /app"; \
    fi

# 如果缺少关键文件，创建一个最小的配置文件模板
RUN if [ ! -f /app/config.ini ]; then \
      echo "[general]\nnas_directories = /vol3/1000\nsize_threshold = 100\noutput_file = /app/output/redundant_files\nschedule_time = 03:00\nignore_links = true\n\n[downloader]\nenabled_clients = qb1\n\n[qb1]\ntype = qbittorrent\nhost = 192.168.1.100\nport = 8080\nusername = admin\npassword = adminpassword\npath_mappings = " > /app/config.ini; \
      echo "Created basic config.ini template"; \
    fi

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 定义挂载卷
VOLUME ["/app/config", "/app/output", "/data"]

# 设置环境变量
ENV CONFIG_FILE=/app/config/config.ini
ENV PYTHONUNBUFFERED=1

# 创建启动脚本（如果不存在）
RUN if [ ! -f /app/entrypoint.sh ]; then \
      echo '#!/bin/bash\n\n# 确保输出目录存在\nmkdir -p /app/output\nchmod -R 777 /app/output\n\n# 确保配置目录存在\nmkdir -p /app/config\nchmod -R 777 /app/config\n\n# 默认配置文件路径\nCONFIG_PATH="${CONFIG_FILE:-/app/config/config.ini}"\nCONFIG_DIR=$(dirname "$CONFIG_PATH")\n\n# 确保配置目录存在\nmkdir -p "$CONFIG_DIR"\n\n# 如果配置文件不存在，创建默认配置\nif [ ! -f "$CONFIG_PATH" ]; then\n    echo "配置文件不存在，创建默认配置: $CONFIG_PATH"\n    if [ -f "/app/config.ini" ]; then\n        cp /app/config.ini "$CONFIG_PATH"\n        echo "已从内置模板创建配置文件"\n    else\n        echo "错误: 未找到配置模板"\n        exit 1\n    fi\n    \n    # 设置合适的权限，确保配置文件可读写\n    chmod 666 "$CONFIG_PATH"\nelse\n    echo "配置文件已存在: $CONFIG_PATH"\nfi\n\n# 检查app.py是否存在\nif [ ! -f "/app/app.py" ]; then\n    echo "错误: 找不到应用程序文件 /app/app.py"\n    exit 1\nfi\n\necho "启动Seeding Checker..."\necho "配置文件: $CONFIG_PATH"\n\n# 执行app.py\nexec python /app/app.py --config "$CONFIG_PATH"' > /app/entrypoint.sh && \
      chmod +x /app/entrypoint.sh && \
      echo "Created entrypoint.sh script"; \
    fi

# 设置启动脚本为入口点
ENTRYPOINT ["/app/entrypoint.sh"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD ps aux | grep python | grep app.py || exit 1 