`fix` any failing command with ChatGPT:

![fix Demo](demo.gif)

# Installation

## Prerequisites

You need Python 3 and an
[OpenAPI API key](https://platform.openai.com/account/api-keys).

## Linux and macOS

1. Download the [source code](https://github.com/mherrmann/fix/archive/refs/heads/main.zip).
2. Unpack it. We'll assume you unpacked to `~/Downloads/fix-main`.
3. Open a command prompt and change to that directory: `cd ~/Downloads/fix-main`.
3. Create a Python 3 virtual environment in that directory: `python3 -m venv venv`.
4. Activate the virtual environment: `source venv/bin/activate`.
5. Install dependencies: `pip install -Ur requirements.txt`
6. Create an alias for the command: `alias fix='~/Downloads/fix-main/venv/bin/python ~/Downloads/fix-main/main.py'`.

## Windows (untested)

1. Download the [source code](https://github.com/mherrmann/fix/archive/refs/heads/main.zip).
2. Unpack it. We'll assume you unpacked to `C:\Users\<user>\Downloads\fix-main`.
3. Open a command prompt and change to that directory: `cd C:\Users\<user>\Downloads\fix-main`.
3. Create a Python 3 virtual environment in that directory: `python3 -m venv venv`.
4. Activate the virtual environment: `call venv/Scripts/activate`.
5. Install dependencies: `pip install -Ur requirements.txt`
6. Create an alias for the command: `doskey fix=~/Downloads/fix-main/venv/bin/python ~/Downloads/fix-main/main.py`.

# Caveats

The [main.py](implementation) may send arbitrary files from your system to
OpenAI's servers. What could possibly go wrong?
