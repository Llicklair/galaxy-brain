# Build context = this environment/ dir. prepare.sh stages the pinned repo snapshot at repo/.
# git-init + tag `base` so the verifier can diff exactly what the agent changed.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY repo/ /app/
RUN pip install --no-cache-dir -e . pytest ruff
RUN git init -q && git add -A \
    && git -c user.email=eval@local -c user.name=eval commit -qm base && git tag base
