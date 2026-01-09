FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN mkdir -p /app/data

ENV SERVER_PORT=5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "web_server:app"]
