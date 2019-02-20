#!/usr/bin/env python
#
# Website 

import errno
import yaml
import logging
import logging.handlers
import multiprocessing as mp
import threading

from darc.definitions import *
from darc.control import send_command


class StatusWebsiteException(Exception):
    pass


class StatusWebsite(threading.Thread):
    def __init__(self, stop_event):
        threading.Thread.__init__(self)
        self.stop_event = stop_event
        self.daemon = True

        with open(CONFIG_FILE, 'r') as f:
            config = yaml.load(f)['status_website']

        # set config, expanding strings
        kwargs = {'home': os.path.expanduser('~')}
        for key, value in config.items():
            if isinstance(value, str):
                value = value.format(**kwargs)
            setattr(self, key, value)

        # setup logger
        handler = logging.handlers.WatchedFileHandler(self.log_file)
        formatter = logging.Formatter(logging.BASIC_FORMAT)
        handler.setFormatter(formatter)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        self.logger.info('Initialized')

        # create website directory
        try:
            os.makedirs(self.web_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                self.logger.error("Failed to create website directory: {}".format(e))
                raise StatusWebsiteException("Failed to create website directory: {}".format(e))

    def run(self):
        """
        """
        while not self.stop_event.is_set():
            self.logger.info("Getting status of all services")
            # get status for master node
            statuses = {'master': {}}
            for service in self.check_services_master:
                try:
                    service_status = send_command(10, service, 'status', host=MASTER)
                except Exception as e:
                    service_status = "UNKNOWN"
                    self.logger.error("Failed to get master status of {}: {}".format(service, e))
                statuses['master'][service] = service_status
            # get status for worker nodes
            for node in WORKERS:
                statuses[node] = {}
                for service in self.check_services_worker:
                    try:
                        service_status = send_command(10, service, 'status', host=node)
                    except Exception as e:
                        service_status = "UNKNOWN"
                        self.logger.error("Failed to get {} status of {}: {}".format(node, service, e))
                    statuses[node][service] = service_status
            self.logger.info("Publishing status")
            self.publish_status(statuses)
            self.stop_event.wait(self.interval)

    def publish_status(self, statuses):
        """
        Publish status as simple html webpage
        """ 

        webpage = template.format(statuses['master'])
        web_file = os.path.join(self.web_dir, index.html)
        with open(web_file, 'w') as f:
            f.write(webpage)

    def get_template(self):
        """
        Return the HTML template
        """

        template=dedent("""<html>
        <head><title>DARC status</title></head>
        <body>
        TEST
        </body>
        </html>
        """)
        return template
