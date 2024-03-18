#!/usr/bin/env bash
cd "$(dirname "$0")/.."

java -jar ${JAVA_HOME}/bin/swagger-codegen.jar generate -i ./openapi.yaml -l python -c ./scripts/cli-gen-opts.json -o ./out/pylivoltek/