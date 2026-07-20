FROM python:3.12.8-bookworm
LABEL authors="Eko Indarto"

ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE


# Combine apt-get commands to reduce layers
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash akmi

ENV PYTHONPATH=/home/akmi/aca/src
ENV BASE_DIR=/home/akmi/aca

WORKDIR ${BASE_DIR}


# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.


# Create and activate virtual environment
RUN python -m venv .venv
ENV APP_NAME="Repository Asistant Service"
ENV PATH="/home/akmi/aca/.venv/bin:$PATH"
# Copy the application into the container.
COPY src ./src
COPY pyproject.toml .
COPY README.md .
COPY uv.lock .

RUN uv venv --clear .venv
# Install dependencies

RUN uv sync --frozen --no-cache && chown -R akmi:akmi ${BASE_DIR}
USER akmi
# Run the application.
CMD ["python", "-m", "src.main"]

#CMD ["tail", "-f", "/dev/null"]