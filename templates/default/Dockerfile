FROM dxlib:latest
RUN useradd -m sandbox
USER sandbox

WORKDIR /app

# Copy the strategy.py and main.py into the container
COPY --chown=sandbox:sandbox strategy.py main.py /app/

CMD ["python", "main.py"]
