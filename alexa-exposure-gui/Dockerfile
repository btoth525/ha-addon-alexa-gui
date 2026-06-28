ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
WORKDIR /app

COPY requirements.txt /app/
RUN apk add --no-cache gcc musl-dev libffi-dev python3-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del gcc musl-dev libffi-dev python3-dev

COPY app/ /app/app/
COPY www/ /app/www/
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
