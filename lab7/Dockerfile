FROM jenkins/jenkins:lts-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    qemu-system-arm ipmitool firefox-esr python3 python3-venv curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG GECKODRIVER_VERSION=0.37.1
RUN curl --fail --location --retry 3 \
    "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
    -o /tmp/geckodriver.tar.gz \
    && tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin \
    && rm /tmp/geckodriver.tar.gz
COPY requirements.txt /tmp/lab7-requirements.txt
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir -r /tmp/lab7-requirements.txt
ENV PATH="/opt/test-venv/bin:${PATH}"
USER jenkins
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY init.groovy.d/ /usr/share/jenkins/ref/init.groovy.d/
