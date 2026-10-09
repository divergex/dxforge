FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# mc for the minio-bootstrap service; the Chainguard minio-client image has no
# shell, so the binary is copied here and the bootstrap script runs in this image
COPY --from=cgr.dev/chainguard/minio-client@sha256:8c7dbd0036969963b760703d50da018fd2b9c1e9bac9f17abecc32a8dbbc9578 /usr/bin/mc /usr/bin/mc

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && mc --version

ENTRYPOINT ["forge"]
CMD ["--help"]
