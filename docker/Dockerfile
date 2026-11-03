FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]" && useradd -m ama
USER ama
ENV AMA_HOME=/home/ama/.ama AMA_HOST=0.0.0.0 AMA_PORT=8410
EXPOSE 8410
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8410/health')"
CMD ["ama", "serve", "--mcp"]
