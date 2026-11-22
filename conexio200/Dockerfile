FROM python:3.13-alpine

RUN pip install --no-cache-dir "paho-mqtt>=2.1,<3"

WORKDIR /app
COPY conexio /app/conexio

CMD ["python", "-u", "-m", "conexio"]
