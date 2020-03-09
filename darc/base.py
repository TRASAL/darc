#!/usr/bin/env python
#
# DARC base class

import os
import socket
import threading
import multiprocessing as mp
from multiprocessing import queues
import yaml
from queue import Empty

from darc.logger import get_logger
from darc.definitions import ROOT_DIR, CONFIG_FILE, MASTER, WORKERS


class DARCBase(threading.Thread):
    """
    DARC Base class

    Provides common methods to services
    """

    def __init__(self):
        """
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self.stop_event = threading.Event()

        self.needs_source_queue = True
        self.needs_target_queue = False
        self.source_queue = None
        self.target_queue = None

        # set names for config and logger
        name = type(self).__module__.split('.')[-1]
        self.log_name = type(self).__name__

        # load config
        with open(os.path.join(ROOT_DIR, CONFIG_FILE), 'r') as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)[name]

        # set config, expanding strings
        kwargs = {'home': os.path.expanduser('~'), 'hostname': socket.gethostname()}
        for key, value in config.items():
            if isinstance(value, str):
                value = value.format(**kwargs)
            setattr(self, key, value)

        # setup logger
        self.logger = get_logger(name, self.log_file)
        self.logger.info("{} initialized".format(self.log_name))

        # set host type
        hostname = socket.gethostname()
        if hostname == MASTER:
            self.host_type = 'master'
        elif hostname in WORKERS:
            self.host_type = 'worker'
        else:
            self.logger.warning("Running on unknown host")
            self.host_type = None

    def stop(self):
        """
        Stop this service
        """
        self.logger.info("Stopping {}".format(self.log_name))
        self.cleanup()
        self.stop_event.set()

    def set_source_queue(self, queue):
        """
        Set input queue

        :param queues.Queue queue: Input queue
        """
        if not isinstance(queue, queues.Queue):
            self.logger.error("Given source queue is not an instance of Queue")
            self.stop()
        else:
            self.source_queue = queue

    def set_target_queue(self, queue):
        """
        Set output queue

        :param queues.Queue queue: Output queue
        """
        if not isinstance(queue, queues.Queue):
            self.logger.error("Given target queue is not an instance of Queue")
            self.stop()
        else:
            self.target_queue = queue

    def run(self):
        """
        Main loop

        Receive commands on input queue, calls self.start_observation, self.stop_observation,
        else self.process_command
        """
        # check queues
        try:
            if self.needs_source_queue and not self.source_queue:
                self.logger.error("Source queue not set")
                self.stop()

            if self.needs_target_queue and not self.target_queue:
                self.logger.error("Target queue not set")
                self.stop()

            self.logger.info("Starting {}".format(self.log_name))
            while not self.stop_event.is_set():
                # read from queue
                try:
                    command = self.source_queue.get(timeout=.1)
                except Empty:
                    continue
                # command received, process it
                if command['command'] == "start_observation":
                    self.logger.info("Starting observation")
                    try:
                        self.start_observation(command['obs_config'])
                    except Exception as e:
                        self.logger.error("Failed to start observation: {}".format(e))
                elif command['command'] == "stop_observation":
                    self.logger.info("Stopping observation")
                    self.stop_observation()
                else:
                    self.process_command(command)
        # EOFError can occur due to usage of queues
        # Can be ignored
        except EOFError:
            pass
        except Exception as e:
            self.logger.error("Caught exception in main loop: {}".format(e))
            self.stop()

    def start_observation(self, *args, **kwargs):
        """
        Start observation stub, should be overridden by subclass if commands need to be executed at
        observation start

        :param list args: start_observation arguments
        :param dict kwargs: start_observation keyword arguments
        """
        pass

    def stop_observation(self, *args, **kwargs):
        """
        Stop observation stub, should be overridden by subclass if commands need to be executed at
        observation stop

        :param list args: stop_observation arguments
        :param dict kwargs: stop_observation keyword arguments
        """
        pass

    def cleanup(self):
        """
        Stub for commands to run upon service stop, defaults to self.stop_observation
        """
        self.stop_observation()

    def process_command(self, *args, **kwargs):
        """
        Process command from queue, other than start_observation and stop_observation

        :param list args: process command arguments
        :param dict kwargs: process command keyword arguments
        """
        raise NotImplementedError("process_command should be defined by subclass")