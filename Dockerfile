FROM python:3.11-buster

RUN apt-get update \
    && apt-get install -y vim \
    && pip install poetry \
    && useradd -d /home/app -U -m -u 1111 app

USER app

ADD --chown=app:app . /app

WORKDIR /app

RUN poetry install && mkdir -p /app/tgdata

ENTRYPOINT ["poetry", "run"]
CMD ["python", "main.py"]
