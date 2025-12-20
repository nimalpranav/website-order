FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install flask google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
CMD ["python", "app.py"]
