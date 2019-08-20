FROM python:3.7

WORKDIR /app
ENV FLASK_APP app.py
ENV FLASK_RUN_HOST 0.0.0.0
EXPOSE 5000

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./app /app

RUN python3 -m venv env

CMD [ "flask", "run" ]