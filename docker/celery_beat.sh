#!/bin/bash

sleep 3 # Wait for the database to be ready

cd src || exit

celery --app=tasks:app beat -l info