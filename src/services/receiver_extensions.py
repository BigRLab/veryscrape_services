from collections import deque
from datetime import datetime
from multiprocessing.connection import Listener
from threading import Thread

from sqlalchemy import create_engine, Table, MetaData, Column, Float, DateTime


class QueueDBWriter(Thread):
    def __init__(self, queue, companies):
        super(QueueDBWriter, self).__init__()
        self.queue = queue
        self.companies = companies

        self.db = create_engine('sqlite:///data/companyData.db')
        self.db.echo = False

        self.table_names = ['article', 'blog', 'twitter', 'reddit', 'stock']

        self.tables = {}
        for t in self.table_names:
            self.tables[t] = Table(t, MetaData(self.db), Column('time', DateTime, primary_key=True),
                                   *[Column(i, Float) for i in self.companies])
            if t not in self.db.table_names():
                self.tables[t].create()

    def update_database(self, data):
        current_time = datetime.now()
        for k in self.tables:
            i = self.tables[k].insert()
            data[k].update(time=current_time)
            i.execute(data[k])

    def run(self):
        while True:
            if not self.queue.empty():
                data = self.queue.get_nowait()
                self.update_database(data)


class StockGymEndPoint(Thread):
    def __init__(self, queue):
        super(StockGymEndPoint, self).__init__()
        self.queue = queue
        self.max_items_in_queue = 10

        self.server = Listener(('localhost', 6100), authkey=b'veryscrape')
        self.conn = None

    def accept_next(self):
        while True:
            try:
                self.conn = self.server.accept()
                break
            except Exception as e:
                _ = e

    def decrease_queue_size(self):
        allowed_items = deque(maxlen=self.max_items_in_queue)
        while not self.queue.empty():
            allowed_items.append(self.queue.get_nowait())
        for item in allowed_items:
            self.queue.put(item)

    def run(self):
        self.accept_next()
        while True:
            if self.queue.qsize() > self.max_items_in_queue:
                self.decrease_queue_size()
            else:
                if not self.queue.empty():
                    data = self.queue.get_nowait()
                    try:
                        self.conn.send(data)
                    except Exception as e:
                        _ = e
                        self.accept_next()
                        self.conn.send(data)
