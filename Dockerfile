FROM python:3.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8765

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY pixelsundo ./pixelsundo
COPY web ./web
COPY data/samples ./data/samples
COPY server.py ./

EXPOSE 8765
CMD ["sh", "-c", "python server.py --host 0.0.0.0 --port ${PORT:-8765} --no-browser"]
