FROM python:3.10

RUN apt-get install -yqq --no-install-recommends \
    && pip install 'feedparser==6.0.11' \
    && pip install 'Scrapy==2.11.2' \
    && pip install 'Telethon==1.35.0' \
    && pip install 'telethon-cryptg==0.0.4' \
    && pip install 'httpx==0.27.0'

WORKDIR /app

COPY . .
