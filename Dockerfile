# Build stage
FROM python:3.10 AS builder

# We will install using a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Copy list of required packages
COPY . /ferdelance

# Install packages using pip
RUN cd /ferdelance && \
    pip install --upgrade pip && \
    pip install --no-cache-dir federated-learning-shared/ && \
	pip install --no-cache-dir .

# Installation stage
FROM python:3.10-slim-buster AS base
ENV PATH="/opt/venv/bin:${PATH}"

# Copy built environment to base
COPY --from=builder /opt/venv /opt/venv

WORKDIR /spearhead

CMD ["uvicorn", "ferdelance.server.api:api", "--host", "0.0.0.0", "--port", "1456"]
