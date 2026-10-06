FROM python:3.12-slim

WORKDIR /app

# tesseract-ocr lets the upload screening read phone photos / scanned PDFs of
# IDs and logbooks (see app/services/document_validation.py). It is optional:
# without it those files are still accepted, just not content-checked.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
