#!/usr/bin/env python
# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This file contains some utilities used for processing tweet data and writing
data to BigQuery
"""

import collections
import datetime
import time

from apiclient import discovery
import dateutil.parser
import httplib2
from oauth2client.client import GoogleCredentials
from uszipcode import Zipcode
from uszipcode import SearchEngine

search = SearchEngine(simple_zipcode=True)

SCOPES = ['https://www.googleapis.com/auth/bigquery',
          'https://www.googleapis.com/auth/pubsub']
NUM_RETRIES = 3


def get_credentials():
    """Get the Google credentials needed to access our services."""
    credentials = GoogleCredentials.get_application_default()
    if credentials.create_scoped_required():
        credentials = credentials.create_scoped(SCOPES)
    return credentials


def create_bigquery_client(credentials):
    """Build the bigquery client."""
    http = httplib2.Http()
    credentials.authorize(http)
    return discovery.build('bigquery', 'v2', http=http)


def create_pubsub_client(credentials):
    """Build the pubsub client."""
    http = httplib2.Http()
    credentials.authorize(http)
    return discovery.build('pubsub', 'v1beta2', http=http)


def ziplookup(lat, long):
    print lat, long
    zipsearch = search.by_coordinates(lat, long, radius=10, returns=1)
    print zipsearch
    if zipsearch:
        zip = zipsearch[0].zipcode
        return zip
    else:
        return 'N/A'


def ziplookupcity(location):
    print location
    zipsearch = []
    loc = [x.strip() for x in location.split(',')]
    print loc
    count = len(loc)
    if count >= 2:
        zipsearch = search.by_city_and_state(loc[0], loc[1], returns=1)
    else:
        '''zipsearch = search.by_city(location, returns=1) commented out as location only search seems unstable'''
        print "no city, state combo found"
    print zipsearch
    if zipsearch:
        zip = zipsearch[0].zipcode
        return zip
    else:
        return 'N/A'


def flatten(lst):
    """Helper function used to massage the raw tweet data."""
    for el in lst:
        if (isinstance(el, collections.Iterable) and
                not isinstance(el, basestring)):
            for sub in flatten(el):
                yield sub
        else:
            yield el


def cleanup(data):
    """Do some data massaging."""
    if isinstance(data, dict):
        newdict = {}
        for k, v in data.items():
            if (k == 'coordinates') and isinstance(v, list):
                # flatten list
                print data.items()
                print k, v
                try:
                    long = v[0][0][0]
                except:
                    long = v[0]
                    print "Full series of coordinates not found"
                try:
                    lat = v[0][0][1]
                except:
                    lat = v[1]
                newdict[k] = list(flatten(v))
                zip = ziplookup(lat, long)  # zip is N/A if no zip found, otherwise will store the zipcode into the array
                if zip == 'N/A':
                    print "No zipcode found for lat long"
                else:
                    newdict['zipcode'] = zip
            elif k == 'created_at' and v:
                newdict[k] = str(dateutil.parser.parse(v))
            # temporarily, ignore some fields not supported by the
            # current BQ schema.
            # TODO: update BigQuery schema
            elif (k == 'video_info' or k == 'scopes' or k == 'withheld_in_countries'
                  or k == 'is_quote_status' or 'source_user_id' in k
                  or k == ''
                  or 'quoted_status' in k or 'display_text_range' in k or 'extended_tweet' in k
                  or 'media' in k):
                pass
            elif v is False:
                newdict[k] = v
            else:
                if k and v:
                    newdict[k] = cleanup(v)
        return newdict
    elif isinstance(data, list):
        newlist = []
        for item in data:
            newdata = cleanup(item)
            if newdata:
                newlist.append(newdata)
        return newlist
    else:
        return data


def parse_zipcodes(data):
    """Parse zipcode to its own field.  Do a lookup against location if no coordinates were pprovided"""
    if isinstance(data, dict):
        if 'zipcode' in data.get('place', {}).get('bounding_box', {}):
            data['zipcode'] = data['place']['bounding_box']['zipcode']
            print "zipcode found in place/bounding_box/zipcode"
            return data
        elif 'location' in data.get('user', {}):
            print "looking for zip in location"
            loc = data['user']['location']
            zip = ziplookupcity(loc)
            if zip == 'N/A':
                print "No zipcode found for city data"
            else:
                data['zipcode'] = zip
            return data
        else:
            print "Zip could not be extracted from coordinates or location"
            return data
    else:
        return data


def bq_data_insert(bigquery, project_id, dataset, table, tweets):
    """Insert a list of tweets into the given BigQuery table."""
    try:
        rowlist = []
        # Generate the data that will be sent to BigQuery
        for item in tweets:
            item_row = {"json": item}
            rowlist.append(item_row)
        body = {"rows": rowlist}
        # Try the insertion.
        response = bigquery.tabledata().insertAll(
            projectId=project_id, datasetId=dataset,
            tableId=table, body=body).execute(num_retries=NUM_RETRIES)
        # print "streaming response: %s %s" % (datetime.datetime.now(), response)
        return response
        # TODO: 'invalid field' errors can be detected here.
    except Exception, e1:
        print "Giving up: %s" % e1
