FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE ${API_PORT}
CMD ["python","edge_core.py"]
