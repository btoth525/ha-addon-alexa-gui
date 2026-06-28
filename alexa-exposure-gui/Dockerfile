ARG BUILD_FROM=python:3.13-alpine
FROM ${BUILD_FROM}

# BUILD_ARCH is passed by the HA supervisor; declare it to suppress warnings
ARG BUILD_ARCH

ENV LANG=C.UTF-8
WORKDIR /app

# Install build tools for any C-extension packages (ruamel.yaml.clib), then
# remove them to keep the image small
COPY requirements.txt /app/
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY app/ /app/app/
COPY www/ /app/www/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
