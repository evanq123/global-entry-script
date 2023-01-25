import argparse
from datetime import datetime, timedelta
import logging
import sys

import requests
import tweepy

import time
from collections import defaultdict

from secrets import twitter_credentials, twitter_oauth

LOGGING_FORMAT = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'

# LAX is good for testing
LOCATIONS = [
    ('IAD (Dulles)', 5142),
    ('DCA (Reagan)', 8120),
    # ('BTI (Linthicum/Baltimore)', 7940),
    # ('SFO', 5446),
    # ('LAX', 5180)
]

HANDLE = '@your_handle'

DELTA = 3  # Weeks

SCHEDULER_API_URL = 'https://ttp.cbp.dhs.gov/schedulerapi/slots?orderBy=soonest&limit=1&locationId={location}'
TTP_TIME_FORMAT = '%Y-%m-%dT%H:%M'

NOTIF_MESSAGE = '{handle} New appointment slot open at {location}: {date}'
MESSAGE_TIME_FORMAT = '%A, %B %d, %Y at %I:%M %p'

def tweet(message):
    # oauth2_user_handler = tweepy.OAuth2UserHandler(**twitter_oauth)
    # oauth2_url = oauth2_user_handler.get_authorization_url()
    # print(oauth2_url)
    # access_token = oauth2_user_handler.fetch_token(oauth2_url)
    api = tweepy.Client(**twitter_credentials)
    try:
        api.create_tweet(text=message)
    except tweepy.TweepyException as e:
        print(f"Duplicate Tweet: {e}")
    except Exception as e:
        raise

CACHED_MESSAGES = defaultdict(set)

def check_for_openings(location_name, location_code, test_mode=True):
    start = datetime.now()
    end = start + timedelta(weeks=DELTA)

    url = SCHEDULER_API_URL.format(location=location_code,
                                   start=start.strftime(TTP_TIME_FORMAT),
                                   end=end.strftime(TTP_TIME_FORMAT))
    try:
        results = requests.get(url).json()  # List of flat appointment objects
    except requests.ConnectionError:
        logging.exception('Could not connect to scheduler API')
        sys.exit(1)

    messages = []

    for result in results:
        if result['active'] > 0:
            logging.info('Opening found for {}'.format(location_name))

            timestamp = datetime.strptime(result['startTimestamp'], TTP_TIME_FORMAT)
            message = NOTIF_MESSAGE.format(handle=HANDLE, location=location_name,
                                           date=timestamp.strftime(MESSAGE_TIME_FORMAT))
            messages.append(message)
            if message in CACHED_MESSAGES[location_code]:
                print(f'{message}, but has been seen.')
            elif test_mode:
                print(message)
            else:
                CACHED_MESSAGES[location_code].add(message)
                logging.info('Tweeting: ' + message)
                tweet(message)
                
            return  # Halt on first match
    if messages:
        CACHED_MESSAGES[location_code].clear()
        CACHED_MESSAGES[location_code].update(messages)
    logging.info('No openings for {}'.format(location_name))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', '-t', action='store_true', default=False)
    parser.add_argument('--verbose', '-v', action='store_true', default=False)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format=LOGGING_FORMAT,
                            level=logging.INFO,
                            stream=sys.stdout)
    while True:
        logging.info('Starting checks (locations: {})'.format(len(LOCATIONS)))
        for location_name, location_code in LOCATIONS:
            check_for_openings(location_name, location_code, args.test)
        # time.sleep(10)

if __name__ == '__main__':
    main()
