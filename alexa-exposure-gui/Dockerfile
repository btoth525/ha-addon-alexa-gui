ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY www/ /app/www/
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
