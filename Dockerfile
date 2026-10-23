FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api.py motor.py ./
COPY static/ ./static/
RUN useradd --system --uid 10001 --create-home appuser
USER appuser
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers"]