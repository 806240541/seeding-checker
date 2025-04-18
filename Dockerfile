FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建配置和输出目录并设置权限
RUN mkdir -p /app/output /app/config && \
    chmod -R 777 /app/output

# 复制应用程序文件
COPY . .
RUN chmod +x app.py start.sh troubleshoot.sh

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 定义挂载卷
VOLUME ["/app/config", "/app/output", "/data"]

# 如果配置文件不存在，则复制默认配置
RUN if [ ! -f /app/config/config.ini ]; then \
      cp config.ini /app/config/config.ini 2>/dev/null || echo "No default config.ini found"; \
    fi

# 设置环境变量
ENV CONFIG_FILE=/app/config/config.ini
ENV PYTHONUNBUFFERED=1

# 默认命令
CMD ["python", "app.py", "--config", "/app/config/config.ini"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD ps aux | grep python | grep app.py || exit 1 