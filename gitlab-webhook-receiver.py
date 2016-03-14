#!/usr/bin/python

import os
import json
import logging
import subprocess
import logging.handlers
import threading
from Queue import Queue
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


log_file = 'webhook.log'
log_level = logging.DEBUG      # DEBUG is quite verbose
queue = Queue()


logger = logging.getLogger('log')
logger.setLevel(log_level)
log_handler = logging.handlers.RotatingFileHandler(log_file, backupCount=4)
f = logging.Formatter("%(asctime)s %(filename)s %(levelname)s %(message)s",
                      "%B %d %H:%M:%S")
log_handler.setFormatter(f)
logger.addHandler(log_handler)


def clone_project(git_ssh_url, branch):
    cmd = 'cd /tmp && git clone -b {} {}'.format(branch, git_ssh_url)
    logger.debug(cmd)
    proc = subprocess.Popen(cmd, shell=True)
    proc.wait()


def do_something(project_name, object_kind='tag_push'):
    cmd = 'TRIGGER={} /bin/bash /tmp/{}/packaging.sh'.format(object_kind, project_name)
    logger.debug('do something: %s', cmd)
    proc = subprocess.Popen(cmd, shell=True)
    proc.wait()


def clean_project(project_name):
    logger.debug('clean project')
    proc = subprocess.Popen('sudo rm -rf /tmp/{}'.format(project_name), shell=True)
    proc.wait()


def parse_single_post(data_string):
    logger.info('start parsing data_string')
    # parse data
    post_msg = json.loads(data_string)
    logger.debug(post_msg)
    # get object_kind. push/tag_push/issue/note/merge_request
    object_kind = post_msg['object_kind']
    logger.debug(object_kind)
    # get ssh url
    git_ssh_url = post_msg['repository']['git_ssh_url']
    logger.debug(git_ssh_url)
    # get the real branch. refs/tags/1.0.0 => 1.0.0
    branch = os.path.basename(post_msg['ref'])
    logger.debug(branch)

    clone_project(git_ssh_url, branch)

    project_name = post_msg['repository']['name']
    logger.debug(project_name)
    do_something(project_name, object_kind)

    clean_project(project_name)

    logger.info('parsing finished')


def parse_forever():
    while True:
        data_string = queue.get(block=True)
        parse_single_post(data_string)


class webhookReceiver(BaseHTTPRequestHandler):

    def do_POST(self):
        """
            receives post, handles it
        """
        logger.debug('got post')
        message = 'OK'
        self.rfile._sock.settimeout(15)
        data_string = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header("Content-type", "text")
        self.send_header("Content-length", str(len(message)))
        self.end_headers()
        self.wfile.write(message)
        logger.debug('gitlab connection should be cloxsed now.')
        queue.put(data_string)


def main():
    """
        the main event.
    """
    t = threading.Thread(target=parse_forever)
    t.setDaemon(True)
    t.start()

    server = HTTPServer(('', 8000), webhookReceiver)
    try:
        logger.info('started web server...')
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('ctrl-c pressed, shutting down.')
        server.socket.close()

if __name__ == '__main__':
    main()
