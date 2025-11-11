import sqlite3,time
class DBManager:
    def __init__(self, path):
        self.conn=sqlite3.connect(path,check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS events(ts REAL,rule TEXT,data TEXT)")
    def insert_event(self,rule,data):
        self.conn.execute("INSERT INTO events VALUES(?,?,?)",(time.time(),rule,str(data)));self.conn.commit()
