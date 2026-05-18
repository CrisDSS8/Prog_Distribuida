FROM python:3.11-slim
WORKDIR /app
RUN pip install pika
COPY send.py .
CMD ["python", "send.py"]