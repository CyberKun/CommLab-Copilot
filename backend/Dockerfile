FROM python:3.12.14-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home commlab && mkdir -p /data/artifacts && chown -R commlab:commlab /data /app
USER commlab
CMD ["uvicorn", "commlab.main:app", "--host", "0.0.0.0", "--port", "8000"]
