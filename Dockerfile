FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建配置和输出目录并设置权限
RUN mkdir -p /app/output /app/config && \
    chmod -R 777 /app/output /app/config

# 复制默认配置文件
COPY config.ini /app/

# 复制启动脚本
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# 明确复制主应用程序文件
COPY app.py /app/
COPY *.sh /app/ 2>/dev/null || echo "No shell scripts found"
COPY *.py /app/ 2>/dev/null || echo "Copying additional Python files"

# 复制其余文件
COPY . .

# 列出/app目录内容以便调试
RUN echo "Listing /app directory:" && \
    ls -la /app && \
    if [ -f /app/app.py ]; then \
      echo "app.py found" && \
      chmod +x /app/app.py; \
    else \
      echo "ERROR: app.py NOT found in /app"; \
    fi

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 定义挂载卷
VOLUME ["/app/config", "/app/output", "/data"]

# 设置环境变量
ENV CONFIG_FILE=/app/config/config.ini
ENV PYTHONUNBUFFERED=1

# 设置启动脚本为入口点
ENTRYPOINT ["/app/entrypoint.sh"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD ps aux | grep python | grep app.py || exit 1 