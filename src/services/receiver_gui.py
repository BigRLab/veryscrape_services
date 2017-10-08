import tkinter as tk
from functools import partial
from multiprocessing import Queue
from threading import Thread

import requests

RED, GREEN = '#ff8080', '#9fff80'


class ItemGUI(Thread):
    def __init__(self, queue, *args, **kwargs):
        super(ItemGUI, self).__init__(*args, **kwargs)
        self.queue = queue

    def run_app(self):
        app = tk.Tk()
        frame = tk.Frame(app, width=600, height=600)
        frame.pack(fill='both', expand=True)
        gui_button = tk.Button(frame, text='GUI', command=self.run_status_gui)
        gui_button.pack(side='top', fill='both', expand=True)
        app.mainloop()

    def run_status_gui(self):
        Thread(target=StatusGUI, args=(self.queue,)).start()

    def run(self):
        self.run_app()


class StatusGUI(tk.Tk):
    api_server_url = 'http://127.0.0.1:1111'
    companies = list(sorted(eval(requests.get(api_server_url, params={'q': 'topics'}).text).keys()))

    def __init__(self, queue, *args, **kwargs):
        super(StatusGUI, self).__init__(*args, **kwargs)
        self.queue = queue
        self.status_frame = StreamStatusPage(self)
        self.puller = Thread(target=self.pull)
        self.running = True
        self.run()

    def end(self):
        self.running = False
        self.puller.join()
        self.destroy()
        self.quit()

    def flush_queue(self):
        if self.queue.qsize() >= 2:
            last = self.queue.get_nowait()
            while not self.queue.empty():
                last = self.queue.get_nowait()
            self.queue.put(last)

    def pull(self):
        self.flush_queue()
        while self.running:
            if not self.queue.empty():
                data = self.queue.get_nowait()
                for t, d in data.items():
                    default = {c: RED for c in self.companies}
                    for c, val in d.items():
                        if val > 0:
                            default[c] = GREEN
                    self.status_frame.update_colors(t, default)
                self.status_frame.render(self.status_frame.current_view)

    def run(self):
        grid_size = (12, 10, 1, 1)
        self.protocol("WM_DELETE_WINDOW", self.end)
        self.grid(*grid_size)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=11)
        for i in range(grid_size[1]):
            self.grid_columnconfigure(i, weight=1)

        self.puller.start()
        self.mainloop()


class StreamStatusPage(tk.Frame):
    def __init__(self, master):
        super(StreamStatusPage, self).__init__(master)
        self.master = master
        self.companies = master.companies
        self.types = ['article', 'blog', 'reddit', 'twitter', 'stock']
        self.current_view = 'article'

        self.labels = {c: None for c in self.companies}
        self.statuses = {c: {k: RED for k in self.types} for c in self.companies}

        self.grid(row=1, column=0, sticky=tk.NSEW, columnspan=10, rowspan=11)
        self.reset()
        self.render(self.current_view)
        self.lift()

    def change_view(self, t):
        self.current_view = t
        self.render(t)

    def reset(self):
        # Create buttons
        for i, t in enumerate(self.types):
            button = tk.Button(self.master, text=t, command=partial(self.change_view, t))
            button.grid(row=0, column=i * 2, sticky=tk.NSEW, columnspan=2, rowspan=1)
        # Create alphabetically sorted grid of labels
        topics = iter(self.companies)
        for i in range(11):
            self.rowconfigure(i, weight=1)
            for j in range(10):
                self.columnconfigure(j, weight=1)
                c = next(topics)
                label = tk.Label(self, bd=2, bg=RED, text=c, relief='solid', font='Helvetica 14')
                label.grid(row=i, column=j, sticky=tk.NSEW)
                self.labels[c] = label

    def update_colors(self, t, color_dict):
        for k, c in color_dict.items():
            self.statuses[k][t] = c

    def render(self, t):
        try:
            for c in self.companies:
                self.labels[c].config(bg=self.statuses[c][t])
                self.labels[c].update()
            self.update()
        except tk.TclError:
            pass


if __name__ == '__main__':
    q = Queue()
    ItemGUI(q).start()
