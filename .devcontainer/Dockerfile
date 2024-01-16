# [Choice] Python version (use -bookworm or -bullseye variants on local arm64/Apple Silicon): 3, 3.12, 3.11, 3.10, 3.9, 3.8, 3-bookworm, 3.12-bookworm, 3.11-bookworm, 3.10-bookworm, 3.9-bookworm, 3.8-bookworm, 3-bullseye, 3.12-bullseye, 3.11-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3-buster, 3.12-buster, 3.11-buster, 3.10-buster, 3.9-buster, 3.8-buster
ARG VARIANT=3-bookworm
ARG TARGET_JAVA_VERSION=21
FROM python:${VARIANT}

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get purge -y imagemagick imagemagick-6-common
RUN python3 -m pip install --upgrade setuptools build debugpy
RUN apt-get install -y cmake libavformat-dev gdb

EXPOSE 5678

USER root
ARG TARGET_JAVA_VERSION
ENV JAVA_HOME /usr/lib/jvm/msopenjdk-current
ENV PATH "${JAVA_HOME}/bin:${PATH}"
# Default to UTF-8 file.encoding
ENV LANG en_US.UTF-8

# Install Microsoft OpenJDK
RUN arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
    "amd64") \
    jdkUrl="https://aka.ms/download-jdk/microsoft-jdk-${TARGET_JAVA_VERSION}-linux-x64.tar.gz"; \
    ;; \
    "arm64") \
    jdkUrl="https://aka.ms/download-jdk/microsoft-jdk-${TARGET_JAVA_VERSION}-linux-aarch64.tar.gz"; \
    ;; \
    *) echo >&2 "error: unsupported architecture: '$arch'"; exit 1 ;; \
    esac \
    \
    && wget --progress=dot:giga -O msopenjdk.tar.gz "${jdkUrl}" \
    && wget --progress=dot:giga -O sha256sum.txt "${jdkUrl}.sha256sum.txt" \
    \
    && sha256sumText=$(cat sha256sum.txt) \
    && sha256=$(expr substr "${sha256sumText}" 1 64) \
    && echo "${sha256} msopenjdk.tar.gz" | sha256sum --strict --check - \
    && rm sha256sum.txt* \
    \
    && mkdir -p "$JAVA_HOME" \
    && tar --extract \
    --file msopenjdk.tar.gz \
    --directory "$JAVA_HOME" \
    --strip-components 1 \
    --no-same-owner \
    && rm msopenjdk.tar.gz* \
    \
    && ln -s ${JAVA_HOME} /docker-java-home \
    && ln -s ${JAVA_HOME} /usr/local/openjdk-${TARGET_JAVA_VERSION}

RUN wget https://repo1.maven.org/maven2/io/swagger/codegen/v3/swagger-codegen-cli/3.0.51/swagger-codegen-cli-3.0.51.jar -O ${JAVA_HOME}/bin/swagger-codegen.jar
RUN chmod +x ${JAVA_HOME}/bin/swagger-codegen.jar