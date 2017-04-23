from datetime import timedelta, datetime
from chefboyrd.models.shifts import Shift

def checkAvailability(id, name):
    """
    This method checks the availability of the shifts and makes sure that there are no
    scheduling overlaps in terms of duration.

    Args:
        id: the id of the shift that will be in analysis

    Returns:
        True: if there are no scheduling conflicts
        False: if the worker in question already has a schedule arranged
    """
    tryShift = Shift.getShift(id)
    for workShift in Shift.select().where(Shift.name==name):
        if workShift.shift_time_start <= tryShift.shift_time_start and workShift.shift_time_end <= tryShift.shift_time_end:
            return False