#!/bin/bash

# Install Wine if not present
if ! command -v wine &> /dev/null; then
    sudo dpkg --add-architecture i386
    sudo apt-get update
    sudo apt-get install -y wine wine32
fi

# Start gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app