FROM python:3.10

RUN apt-get install -yqq --no-install-recommends \
    && pip install 'feedparser==6.0.10' \
    && pip install 'Scrapy==2.6.2' \
    && pip install 'Telethon==1.25.0' \
    && pip install 'telethon-cryptg==0.0.4' \
    && pip install 'httpx==0.23.0'

WORKDIR /app

ADD . .
