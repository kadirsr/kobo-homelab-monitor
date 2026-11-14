FROM python:3.13-alpine

WORKDIR /app
COPY app.py /app/app.py
RUN addgroup -S app && adduser -S -G app app
USER app

EXPOSE 8090
CMD ["python", "/app/app.py"]

