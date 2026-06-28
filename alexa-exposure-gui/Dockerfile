FROM python:3.13-alpine

ARG BUILD_ARCH

ENV LANG=C.UTF-8
WORKDIR /app

COPY requirements.txt /app/
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY app/ /app/app/
COPY www/ /app/www/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
