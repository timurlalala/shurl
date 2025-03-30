FROM python:3.12-bookworm AS builder

RUN mkdir /fastapi_app
WORKDIR /fastapi_app
RUN python -m venv /fastapi_app/venv
ENV PATH="/fastapi_app/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-bookworm
WORKDIR /fastapi_app
COPY --from=builder /fastapi_app/venv /fastapi_app/venv
ENV PATH="/fastapi_app/venv/bin:$PATH"
COPY . .
RUN chmod a+x ./docker/*.sh