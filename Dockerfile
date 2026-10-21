FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY public ./public
RUN useradd --create-home prometeus && mkdir downloads && chown prometeus:prometeus downloads
USER prometeus
ENV HOST=0.0.0.0
EXPOSE 7189
CMD ["python", "server.py"]
