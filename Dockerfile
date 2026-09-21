FROM python:3.13-slim
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "server.py"]
