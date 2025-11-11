FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE ${API_PORT}
CMD ["python","controller_core.py"]
