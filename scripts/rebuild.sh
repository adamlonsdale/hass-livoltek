#!/usr/bin/env bash
python3 -m build ./out/pylivoltek/

find . -name "pylivoltek*.whl" -exec cp -f '{}' . \;
python3 -m pip install -r requirements.txt --force-reinstall