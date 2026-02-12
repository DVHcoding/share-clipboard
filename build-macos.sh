#!/bin/zsh

pyinstaller \
    --name="ClipboardClient" \
    --windowed \
    --onefile \
    client.py
