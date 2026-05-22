FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# DATA_DIR can be overridden at runtime (e.g. /data on Fly.io volume)
ENV DATA_DIR=.
RUN mkdir -p logs
CMD ["python", "main.py"]
