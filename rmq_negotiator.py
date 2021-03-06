import pika
import CONFIG
import json
from babynames_worker import BabyNamesWorker
from demoqueue_worker import DemoQueueWorker
import requests


class RMQNegotiator:
    CHANNEL = None
    CONNECTION = None

    def __init__(self,
                 host=CONFIG.RMQ_HOST,
                 port=CONFIG.RMQ_PORT,
                 message_queue=CONFIG.MESSAGE_QUEUE,
                 user=CONFIG.RMQ_USER,
                 password=CONFIG.RMQ_PASS):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.message_queue = message_queue

        # def list_queues(self):
        """
        proc = subprocess.Popen("/usr/sbin/rabbitmqctl list_queues",
                                shell=True,
                                stdout=subprocess.PIPE)
        stdout_value = proc.communicate()[0]
        return stdout_value
        """

    def list_queues(self, port=15672, virtual_host=None):
        url = 'http://%s:%s/api/queues/%s' % (self.host,
                                              port, virtual_host or '')
        response = requests.get(url, auth=(self.user, self.password))
        queues = [q['name'] for q in response.json()]
        return queues

    def open_connection(self):
        self.CONNECTION = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=pika.credentials.PlainCredentials(
                    self.user,
                    self.password),))
        self.CHANNEL = self.CONNECTION.channel()

    def publish_message(self, message):
        self.publish_messages([message], self.message_queue)

    def publish_messages(self, messages=[]):
        self.open_connection()
        for message in messages:
            self.CHANNEL.queue_declare(queue=self.message_queue)
            self.CHANNEL.basic_publish(exchange='',
                                       routing_key=self.message_queue,
                                       body=json.dumps(message))
            print(" [x] Sent %s" % message)
        self.close_connection()

    def close_connection(self):
        self.CONNECTION.close()

    def queue_count(self):
        self.open_connection()
        c = self.CHANNEL.queue_declare(
            queue=self.message_queue).method.message_count
        self.close_connection()
        return c

    def callback(self, ch, method, properties, body):
        jobdata = body.decode("utf-8")
        job = json.loads(jobdata)

        '''
        This is where we are going to execute jobs based on which message queue is being monitored.
        '''
        print("Executing: " + str(jobdata))
        if self.message_queue == "DemoQueue":
            DemoQueueWorker(job["ident"]).start()
            self.ack_job(ch, method)

        if self.message_queue == "BabyNamesPrecache":
            BabyNamesWorker(
                job["year"],
                job["gender"],
                job["locale"]
            ).start()
            self.ack_job(ch, method)

    def ack_job(self, ch, method):
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def begin_listening(self, func=None):
        self.open_connection()
        self.CHANNEL.queue_declare(queue=self.message_queue)
        self.CHANNEL.basic_qos(prefetch_count=1)
        self.CHANNEL.basic_consume(self.callback,
                                   queue=self.message_queue,
                                   no_ack=False)
        print(' [*] Waiting for messages. To exit press CTRL+C')
        self.CHANNEL.start_consuming()

"""
if __name__ == '__main__':
    listen = RMQNegotiator()
    threads = [threading.Thread(target=listen.begin_listening)
               for _ in range(8)]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()
"""
