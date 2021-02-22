import datetime


def get_last_monday():
    time_now = datetime.datetime.now()
    last_monday = time_now - datetime.timedelta(days=time_now.weekday()) - datetime.timedelta(hours=time_now.hour,
                                                                                              minutes=time_now.minute,
                                                                                              seconds=time_now.second)
    return last_monday

