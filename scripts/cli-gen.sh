#!/usr/bin/env bash
cd "$(dirname "$0")/.."

java -jar ${JAVA_HOME}/bin/swagger-codegen.jar generate -i ./openapi.yaml -l python -c ./cli-gen-opts.json -o ./out/pylivoltek/
python3 -m build ./out/pylivoltek/

find . -name "pylivoltek*.whl" -exec cp -f '{}' . \;
python3 -m pip install -r requirements.txt --force-reinstall