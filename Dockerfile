FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN mkdir -p /app/data

ENV SERVER_PORT=5000

CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:${SERVER_PORT} --timeout 120 --access-logfile - --error-logfile - --log-level info --capture-output web_server:app"]