# Local S3 for dev: Moto server (S3 only, in-memory). Built to avoid
# depending on gated third-party images.
FROM python:3.11-slim
RUN pip install --no-cache-dir "moto[s3,server]==5.0.*"
EXPOSE 4566
CMD ["moto_server", "-H", "0.0.0.0", "-p", "4566"]
