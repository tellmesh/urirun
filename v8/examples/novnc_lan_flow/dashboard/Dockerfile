FROM python:3.12-slim

RUN pip install --no-cache-dir litellm

WORKDIR /site
COPY . /site
EXPOSE 8080

CMD ["python", "server.py"]
