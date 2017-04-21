'''
Shift management dashboard for the manager interface
'''
import json
from flask import Flask, Blueprint, render_template, request, url_for, jsonify
from flask_table import Table, Col, ButtonCol
from flask_wtf import FlaskForm, CsrfProtect
from wtforms import StringField, IntegerField, validators
from wtforms.ext.dateutil.fields import DateTimeField
from datetime import datetime
from jinja2 import TemplateNotFound
import os 
from chefboyrd.auth import require_role
from chefboyrd.models.shifts import ClaimedShift, FreeShift
from chefboyrd import APP

page = Blueprint('shift_manager', __name__, template_folder='./templates')

class ShiftForm(FlaskForm):
    '''
    This is the form that displays fields to make a shift
    '''
    start = DateTimeField('Shift Starting Time')
    end = DateTimeField('Shift Ending Time')
    role = StringField('Role', [validators.Length(min=2, max=25)])

class ItemTable(Table):
    '''
    This ItemTable class generates a table of the avaliable shifts.
    It also has buttons to post a shift
    '''
    name = Col('Name')
    shift_time_start = Col('Starting Time')
    duration = Col('Duration')
    role = Col('Role')
    post = ButtonCol('Post Shift', 'shift_manager.post',url_kwargs=dict(id='id'), button_attrs={'class': 'btn btn-danger'})

@page.route("/", methods=['GET', 'POST'])
@require_role('admin')
def calendar():
    '''
    Renders the index page of the shift management page
    '''
    shifts = []
    form = ShiftForm()
    for person in ClaimedShift.select():
        shifts.append(dict(name=person.name, shift_time_start=person.shift_time_start.strftime("%Y-%m-%d %H:%M"), shift_time_end=person.shift_time_end.strftime("%Y-%m-%d %H:%M")))
    table = ItemTable(shifts)
    return render_template('/shift_manager/index.html', shifts=shifts, logged_in=True, table=table, form=form)

@page.route('/data')
def return_data():
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    # You'd normally use the variables above to limit the data returned
    # you don't want to return ALL events   like in this code
    # but since no db or any real storage is implemented I'm just
    # returning data from a text file that contains json elements
    with open("chefboyrd/views/templates/shift_manager/events.json", "r") as input_data:
        # you should use something else here than just plaintext
        # check out jsonfiy method or the built in json module
        # http://flask.pocoo.org/docs/0.10/api/#module-flask.json
        return input_data.read()