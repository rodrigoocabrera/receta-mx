FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV RECETAMX_HOST=0.0.0.0 RECETAMX_PORT=8080
EXPOSE 8080
CMD ["python", "-m", "recetamx.server"]
