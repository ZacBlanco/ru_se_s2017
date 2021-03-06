"""Houses all the functions to add or delete sms objects into the database
Includes the feedback analysis functions

written by: Seo Bo Shim, Jarod Morin
tested by: Seo Bo Shim, Jarod Morin
debugged by: Seo Bo Shim, Jarod Morin
"""

from chefboyrd.models.sms import Sms
from chefboyrd.models.statistics import Tabs
from twilio.rest import Client
import twilio.twiml
from peewee import IntegrityError
from string import punctuation
from datetime import datetime, date, timedelta
import configparser
import os
from chefboyrd.tests.test_fb_data import test_sms_data, TestMessages, auto_generate_sms_data
import requests as request

#if in travis, use environment variables. If not in travis, use configuration file. If configuration file missing. email seobo.shim@rutgers.edu
if '/home/travis/build' in os.path.dirname(__file__):
    account_sid = os.environ['account_sid']
    auth_token = os.environ['auth_token']
    restaurant_phone_number = "+19083325081" # remoev
else:
    config = configparser.RawConfigParser()
    try:
        config.read(os.path.join(os.path.dirname(__file__),'sms.cfg')) #assuming config file same path as this controller
    except:
        print("no sms.cfg file, sms data will not be from Twilio")
    account_sid = config['keys']['account_sid']
    auth_token = config['keys']['auth_token']
    cust_phone_number = config['test']['cust_phone_number']
    restaurant_phone_number = config['test']['restaurant_phone_number']

Config = configparser.ConfigParser()
Config.read(os.path.join(os.path.dirname(__file__),"criteriaLists.ini"))
configDict = {}
options = Config.options("SectionOne")
for option in options:
    try:
        configDict[option] = Config.get("SectionOne", option)
    except:
        configDict[option] = None

posWordList = configDict['poslist'].split(' ')
negWordList = configDict['neglist'].split(' ')
exceptionWordList = configDict['exceptionlist'].split(' ')
negationWordList = configDict['negationlist'].split(' ')
emphasisWordList = configDict['emphasislist'].split(' ')
foodWordList = configDict['foodlist'].split(' ')
serviceWordList = configDict['servicelist'].split(' ')
stopWordList = configDict['stoplist'].split(' ')

def update_db(*date_from, **kwargs):
    """Updates the sms in the database starting from the date_from specified (at time midnight)
    no param = updates the sms feedback in database with all message entries
    analyze feedback when sms is sent

    Args:
        date_from (Date): a specified date, where we update db with sms sent after this date
        update_from (str): an optional argument. This should be "test" if messages are not coming from
        twilio, but from the test_fb_data file

    Returns:
        res(int): 1 on success. 0 on error

    Throws:
        SystemError: When the Twilio Client cannot be started. Possibly invalid account_sid or
        auth_token
    """

    if (kwargs):
        if(kwargs["update_from"]):
            if(kwargs['update_from'] == "test"):
                if date_from == ():
                    messages = test_sms_data(5, datetime(2016, 3, 25))
                else:
                    date_from = date_from[0]
                    if (date_from > datetime.now()):
                        return 0
                    else:
                        messages = test_sms_data(5, date_from)
                messages = test_sms_data(5, datetime(2016, 3, 25))
            elif(kwargs['update_from'] == "autogen"):
                if date_from == ():
                    messages = auto_generate_sms_data()
                else:
                    date_from = date_from[0]
                    if (date_from > datetime.now()):
                        return 0
                    else:
                        messages = auto_generate_sms_data(date_from=date_from)
            else:
                return 0
        else:
            return 0
    else:
        try:
            client = Client(account_sid,auth_token)
            messages = client.messages.list(to=restaurant_phone_number)
            process_incoming_sms()
            if date_from == ():
                messages = client.messages.list(to=restaurant_phone_number) # this may have a long random string first
            else:
                date_from = date_from[0]
                if (date_from > datetime.now()):
                    #raise ValueError
                    return 0
                messages = client.messages.list(date_sent=date_from,to=restaurant_phone_number)
        except:
            if date_from==():
                messages = auto_generate_sms_data()
            else:
                date_from = date_from[0]
                if (date_from > datetime.now()):
                    return 0
                else:
                    messages = auto_generate_sms_data(date_from=date_from)
            #raise SystemError
    for message in messages:
        try:
            sms = Sms.get(message.sid == Sms.sid)
            if (sms.invalid_field == True):
                #pass
                print('deleting ' + sms.body)
                delete_twilio_feedback(sms.sid)
            else:
                pass
        except:
            try:
                if message.date_sent != None:
                    date_tmp = message.date_sent - timedelta(hours=4)
                    sms_str = date_tmp.strftime("%Y-%m-%d %H:%M:%S")
                    date_tmp= datetime.strptime(sms_str, "%Y-%m-%d %H:%M:%S")
                else:
                    date_tmp = None
                sms_tmp = Sms(sid=message.sid,
                    submission_time=date_tmp,
                    body=message.body,
                    phone_num=message.from_,
                    )
                res2 = feedback_analysis(sms_tmp.body)
                sms_tmp.pos_flag = res2[0]
                sms_tmp.neg_flag = res2[1]
                sms_tmp.exception_flag = res2[2]
                sms_tmp.food_flag = res2[3]
                sms_tmp.service_flag = res2[4]
                sms_tmp.invalid_field = False
                try:
                    err = sms_tmp.save()
                except IntegrityError:
                    pass
            except IntegrityError:
                err = 0
                #print("Duplicate Sms Entry " + sms_tmp.body)
    return 1

def process_incoming_sms(*one):
    """Updates SMS table in database with the incoming SMS. Checks for the unique key to invalidate
    SMS or keep it. 
    
    Only for processing SMS in real time.

    - Precondition: A Twilio POST request is received.

    TODO: Fix error with twilio, where the most recent message does not have a submission timep

    Args:
        *one(int): optional argument

    Returns:
        res(int): 1 on success. 0 on error

    Throws:
        SystemError: When the Twilio Client cannot be started. Possibly invalid account_sid or
        auth_token
    """
    tabss = Tabs.select()
    valid_keys = []
    for tab in tabss:
        key = tab.fb_key
        if key == "~~~~~~~~~~":
            continue
        else:
            valid_keys.append(key)
    try:
        client = Client(account_sid,auth_token)
        messages = client.messages.list(to=restaurant_phone_number)
    except:
        raise SystemError

    if (one):
        messages = client.messages.list(to=restaurant_phone_number)
        message = messages[0] # get the first message
        message_key = []
        for key in valid_keys:
            if key in message.body[:len(key)]:
                new_body = message.body.replace(key,'')
                #remoev key
                tab = Tabs.update(fb_key="~~~~~~~~~~").where(Tabs.fb_key == key)
                message_key.append(key)

        if (message_key):
            #i can use the date time as now because feedback comes in immediately here
            sms_tmp = Sms(
                sid=message.sid,
                submission_time=datetime.now(),
                body=new_body,
                phone_num=message.from_)
            res2 = feedback_analysis(sms_tmp.body)
            sms_tmp.pos_flag = res2[0]
            sms_tmp.neg_flag = res2[1]
            sms_tmp.exception_flag = res2[2]
            sms_tmp.food_flag = res2[3]
            sms_tmp.service_flag = res2[4]
            sms_tmp.invalid_field = False
            try:
                err = sms_tmp.save()
            except IntegrityError:
                pass
        else:                
            try:
                i = message.body.index(' ')
            except ValueError:
                i = 7
                pass
            if (one):
                non_accept = "Your unique key {" + message.body[:i] + "} is not valid"
                client.messages.create(
                    to=message.from_,
                    from_=restaurant_phone_number,
                    body=non_accept,)
            
            sms_tmp = Sms(
                sid=message.sid,
                submission_time=datetime.now(),
                body=message.body,
                phone_num=message.from_)
            sms_tmp.invalid_field = True
            try:
                err = sms_tmp.save()
            except IntegrityError:
                pass
            #delete_twilio_feedback(message.sid)
    else:
        messages = client.messages.list(to=restaurant_phone_number, date_sent=datetime.today())
        for message in messages:
            message_key = []
            for key in valid_keys:
                if key in message.body[:len(key)]:
                    new_body = message.body.replace(key,'')
                    tab = Tabs.select().where(Tabs.fb_key == key)
                    tab.fb_key = "~~~~~~~~~~"
                    message_key.append(key)

            if (message_key):
                #i can use the date time as now because feedback comes in immediately here
                sms_tmp = Sms(
                    sid=message.sid,
                    submission_time=datetime.now(),
                    body=new_body,
                    phone_num=message.from_
                    )
                res2 = feedback_analysis(sms_tmp.body)
                sms_tmp.pos_flag = res2[0]
                sms_tmp.neg_flag = res2[1]
                sms_tmp.exception_flag = res2[2]
                sms_tmp.food_flag = res2[3]
                sms_tmp.service_flag = res2[4]
                sms_tmp.invalid_field = False
                try:
                    err = sms_tmp.save()
                except IntegrityError:
                    pass
            else:                
                try:
                    i = message.body.index(' ')
                except ValueError:
                    i = 7
                    pass
                if (one):
                    non_accept = "Your unique key {" + message.body[:i] + "} is not valid"
                    client.messages.create(
                        to=message.from_,
                        from_=restaurant_phone_number,
                        body=non_accept,)
                
                sms_tmp = Sms(
                    sid=message.sid,
                    submission_time=datetime.now(),
                    body=message.body,
                    phone_num=message.from_,
                    invalid_field=True
                    )
                try:
                    err = sms_tmp.save()
                except IntegrityError:
                    pass
                #delete_twilio_feedback(message.sid)
    return 1

def update_db_rating(rating):
    """updates the dateabase with the rating specified.
    TODO: update the rating avarage on feedbackM view

    Args:
        rating(Rating): rating object that contains all the parameters

    Returns:
        res(int): 1 on success. 0 on error

    Throws:
        N/A
    """
    try:
        Rating(
            submission_time=datetime.now(),
            food=rating['food'],
            service=rating['service'],
            clean=rating['clean'],
            ambience=rating['ambience'],
            overall=rating['overall'],
            comment=rating['comment']
            ).save()
        return 1
    except:
        return 0

def delete_twilio_feedback(sidd):
    """Wipes the message with the specified sid(s) on Twilio
    Will display response codes.

    Args:
        sidd(str): optional argument. Include a sid or a list of SMS sids to delete from the twilio DB
    
    Returns:
        res(int): 1 on success. 0 if the feedback could not be deleted
    
    Raises:
        ValueError: sms could not be found in database
    """
    if (sidd):     #Assumption is that all feedback in db will match twilio
        if type(sidd) is list:
            try:
                smss = Sms.delete().where(Sms.sid in sidd).execute()
            except:
                raise ValueError
            for sid in sidd:
                url = "https://{}:{}@api.twilio.com/2010-04-01/Accounts/".format(account_sid,auth_token) + account_sid + '/Messages/' + sid
                try:
                    response = request.delete(url)
                except:
                    print("max retries Error")
                finally:
                    if response.status_code == 204:
                        return 1
                    if response.status_code == 404:
                        print(sid + " " + response.reason)
                        return 0
                    else:
                        print(response.reason)
                        return 0
        elif type(sidd) is str:
            sid = sidd
            try:
                sms = Sms.delete().where(Sms.sid==sid).execute()
            except:
                raise ValueError
            url = "https://{}:{}@api.twilio.com/2010-04-01/Accounts/".format(account_sid,auth_token) + account_sid + '/Messages/' + sid
            try:
                response = request.delete(url)
            except:
                print("max retries Error")
            finally:
                if response.status_code == 204:
                    return 1
                if response.status_code == 404:
                    print(sid + " " + response.reason)
                    return 0
                else:
                    print(response.reason)
                    return 0
        else:
            return 0
    else:
        return 0
    return 0

def feedback_analysis(inStr):
    """
    Determines aspects of input string based on word content.

    Extended description:

    Args:
        inStr (str): String containing words separated by spaces or
                        non-apostrophe punctuation.

    Returns:
        list (posFlag,negFlag,exceptionFlag,foodFlag,serviceFlag):
            A list of integers representing whether the input string
            meets the necessary criteria to be flagged as positive,
            negative, food-related, service-related or contains an exception.

    Throws:
        TypeError: When argument is not a string.

    """

    if not isinstance(inStr, str):
        raise TypeError("Input must be a string")

    posFlag = 0
    negFlag = 0
    exceptionFlag = 0
    foodFlag = 0
    serviceFlag = 0

    #config files moved up
    inStrProcessed = inStr
    for p in list(punctuation):
        if p != '\'':
            inStrProcessed = inStrProcessed.replace(p, ' ')

    inStrProcessed = inStrProcessed.lower()
    wordsProcessed = inStrProcessed.split(' ')
    wordsProcessed = list(filter(bool, wordsProcessed))
    for i, word in enumerate(wordsProcessed):
        if word in posWordList:
            if i > 0:
                if wordsProcessed[i-1] in negationWordList:
                    negFlag = 1
                else:
                    if wordsProcessed[i-1] in emphasisWordList and i > 1:
                        if wordsProcessed[i-2] in negationWordList:
                            negFlag = 1
                        else:
                            posFlag = 1

                    else:
                        posFlag = 1
            else:
                posFlag = 1

    for i, word in enumerate(wordsProcessed):
        if word in negWordList:
            if i > 0:
                if wordsProcessed[i-1] in negationWordList:
                    posFlag = 1
                else:
                    if wordsProcessed[i-1] in emphasisWordList and i > 1:
                        if wordsProcessed[i-2] in negationWordList:
                            posFlag = 1
                        else:
                            negFlag = 1

                    else:
                        negFlag = 1
            else:
                negFlag = 1

    for word in wordsProcessed:
        if word in exceptionWordList:
            exceptionFlag = 1
            break

    for word in wordsProcessed:
        if word in foodWordList:
            foodFlag = 1
            break

    for word in wordsProcessed:
        if word in serviceWordList:
            serviceFlag = 1
            break

    #print("posFlag = {}:\nnegFlag = {}:\nexceptionFlag = {}:".format(posFlag,negFlag,exceptionFlag),
    #     "\nfoodFlag = {}:\nserviceFlag = {}:".format(foodFlag,serviceFlag))

    return [posFlag,negFlag,exceptionFlag,foodFlag,serviceFlag]


def word_freq_counter(inStr):
    """
    Determines frequency of each word in input string.

    Extended description:

    Args:
        inStr (str): String containing words separated by spaces or
                        non-apostrophe punctuation.

    Returns:
        resultDict (dict(str)): A list of dictionary elements mapping the each distinct word within inStr
                    to its number of occurrences in the input.

    Throws:
        TypeError: When argument is not a string.

    """

    if not isinstance(inStr, str):
        raise TypeError("Input must be a string")

    inStrProcessed = inStr
    for p in list(punctuation):
        if p != '\'':
            inStrProcessed = inStrProcessed.replace(p, ' ')

    inStrProcessed = inStrProcessed.lower()

    wordsProcessed = inStrProcessed.split(' ')
    wordsProcessed = list(filter(bool, wordsProcessed))

    #print("Stop word list: ")
    #print(stopWordList,"\n")

    result = list()

    for word in wordsProcessed:
        if word not in stopWordList:
            result.append(word)
            
    #print(wordsProcessed,"\n")
    #print(result)
    wordsProcessed = result
    
    #print("Processed word list: ")
    #print(wordsProcessed)
    #print("\n",set(wordsProcessed))
    wordSet = []
    freqs = [0 for x in range(len(set(wordsProcessed)))]
    #print(freqs,"\n")
    for word in set(wordsProcessed):
        if word not in wordSet:
            wordSet.append(word)
    #print(wordSet)

    for i, word in enumerate(wordSet):
        for  word2 in wordsProcessed:
            if word == word2:
                freqs[i] = freqs[i] + 1
    try:
        maxfreq = max(freqs)
    except ValueError:
        maxfreq = 0
    
    return wordSet, freqs, maxfreq

#muhStr = input("Enter the string: ")
#dictOut = wordFreqCounter(muhStr)
#print(dictOut)
