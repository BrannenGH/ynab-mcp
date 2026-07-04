FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_TRANSPORT=streamable-http

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server.py .
COPY scripts ./scripts

RUN chmod +x /app/scripts/*.py

EXPOSE 8000

CMD ["python", "/app/mcp_server.py"]
