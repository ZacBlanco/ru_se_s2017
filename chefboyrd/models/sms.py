from peewee import TextField, DateTimeField, Model
from chefboyrd.models import BaseModel

class Sms(Model):
	'''
	Args:

	sid(str): is an unique id assigned by twilio. it will help us keep track of sms that is in, or not in db
    submission_time(datetime): is the date and time the feedback was submitted
    body(str): the message of the string
    phone_num(str): Phone number of person who sent in text
	'''
	sid = TextField(unique=True)
	submission_time = DateTimeField()
	body = TextField()
	phone_num = TextField()
	#additional categories to associate	
