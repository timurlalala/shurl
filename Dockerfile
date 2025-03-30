FROM python:bookworm
LABEL authors="t.samigullin"

RUN mkdir /fastapi_app

WORKDIR /fastapi_app

COPY . .