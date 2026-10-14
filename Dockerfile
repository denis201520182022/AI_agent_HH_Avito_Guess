FROM python:3.11-slim-bookworm

RUN echo "Types: deb\n\
URIs: http://mirror.yandex.ru/debian/\n\
Suites: bookworm bookworm-updates\n\
Components: main\n\
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\
\n\
Types: deb\n\
URIs: http://mirror.yandex.ru/debian-security\n\
Suites: bookworm-security\n\
Components: main\n\
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg" > /etc/apt/sources.list.d/debian.sources && \
    echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=1000 \
    -r requirements.txt
COPY . .

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /app/logs

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]