#!/bin/bash

sleep 3 # Wait for the database to be ready

alembic upgrade head

cd src || exit

#gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000
uvicorn main:app --host=0.0.0.0 --port=8000