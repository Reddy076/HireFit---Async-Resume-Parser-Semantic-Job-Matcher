FROM python:3.11-slim
WORKDIR /code
COPY services/resume/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/resume/app ./app
COPY services/common ./common
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
