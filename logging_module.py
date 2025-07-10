import datetime

def log_temperature(current_temp_c, goal_temp_c):
    dtime = datetime.datetime.now()
    mydate = str(dtime.date())
    mytime = str(dtime.time())
    with open('log2.csv', 'a') as mylog:
        mystr = f"{mydate},{mytime},{current_temp_c:.2f},{goal_temp_c:.2f}\n"
        mylog.write(mystr)
