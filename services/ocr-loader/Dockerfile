FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' 'requests>=2.32,<3' 'pymupdf>=1.24,<2'
COPY app.py .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
