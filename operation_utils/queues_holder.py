from queue import Queue
import typing
import threading
class QueuesHolder:
    def __init__(self):
        self.queues: typing.List[Queue] = []
        self.queues_access_lock = threading.Lock()

    def add_new_queue(self) -> Queue:
        new_queue = Queue()
        self.queues.append(new_queue)
        return new_queue

    def delete_queue(self, queue: Queue):
        self.queues.remove(queue)

    def put(self, something: object):
        with self.queues_access_lock:
            for queue in self.queues:
                queue.put(something)
