FROM python:2

RUN pip install --upgrade pip
RUN pip install tweepy
RUN pip install --upgrade google-api-python-client
RUN pip install python-dateutil
RUN pip install --upgrade oauth2client 
RUN pip install uszipcode

ADD twitter-to-pubsub.py /twitter-to-pubsub.py
ADD pubsub-to-bigquery.py /pubsub-to-bigquery.py
ADD controller.py /controller.py
ADD utils.py /utils.py

CMD python controller.py