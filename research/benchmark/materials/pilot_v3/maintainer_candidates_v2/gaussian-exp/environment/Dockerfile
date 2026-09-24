# Dependencies-only CPU image for the Gaussian one-step EXP candidate (no papers, tasks or answers).
# Own image per package (user decision 2026-09-24): not shared with any other package.
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=2 \
    OMP_NUM_THREADS=2

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

RUN useradd --create-home --uid 1000 solver \
    && mkdir -p /work \
    && chown solver:solver /work \
    && chmod 0755 /work
USER solver
WORKDIR /work
