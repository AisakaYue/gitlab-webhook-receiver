#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import json
import logging
from logging import handlers
import threading
from Queue import Queue
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

logger = None
queue = Queue()
options = None


def init_logger(log_file):
    global logger
    log_level = logging.DEBUG      # DEBUG is quite verbose
    logger = logging.getLogger('gitlab-webhook')
    logger.setLevel(log_level)
    log_handler = logging.handlers.RotatingFileHandler(log_file, backupCount=4)
    f = logging.Formatter("%(asctime)s %(filename)s %(levelname)s %(message)s",
                          "%B %d %H:%M:%S")
    log_handler.setFormatter(f)
    logger.addHandler(log_handler)


def send_email(subject, content):
    import smtplib
    from email.header import Header
    from email.mime.text import MIMEText

    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = options.email_sender
    message['To'] = options.email_receivers
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtpObj = smtplib.SMTP(host=options.email_server)
        smtpObj.login(options.email_user, options.email_passwd)
        smtpObj.sendmail(
            options.email_sender,
            options.email_receivers.split(','),
            message.as_string()
        )
    except smtplib.SMTPException as e:
        logger.exception('email send failed.\n%r', e)


def clone_project(git_ssh_url, branch):
    from sh import git, ErrorReturnCode
    os.chdir('/tmp')
    try:
        p = git('clone', '-b', branch, git_ssh_url)
        p.wait()
        logger.info(p.cmd)
    except ErrorReturnCode as e:
        logger.info(e)


def do_something(project_name, object_kind='tag_push'):
    from sh import bash
    try:
        p = bash(
            '/tmp/{project}/packaging.sh'.format(project=project_name),
            _env={'TRIGGER': object_kind}
        )
        logger.info('do something: {cmd}'.format(cmd=p.cmd))
        p.wait()
        subject = '{proj} CI Success.'.format(proj=project_name)
        content = p.stdout
    except Exception as e:  # unknown exceptions
        subject = '{proj} CI Failed.'.format(proj=project_name)
        content = repr(e)

    logger.info('{subject}\n{content}'.format(subject=subject, content=content))
    if options.email_notify:
        send_email(subject, content)


def clean_project(project_name):
    from sh import sudo, rm, ErrorReturnCode
    logger.info('clean project')
    try:
        with sudo:
            rm('-rf', '/tmp/{}'.format(project_name)).wait()
    except ErrorReturnCode as e:
        logger.info(e)


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

    project_name = post_msg['repository']['name']
    logger.info(project_name)
    clean_project(project_name)

    # get the real branch. refs/tags/1.0.0 => 1.0.0
    # refs/heads/enhancement/auto-packaging-test-debs => enhancement/auto-packaging-test-debs
    if '/' in post_msg['ref']:
        branch = '/'.join(post_msg['ref'].split('/')[2:])
    else:
        branch = post_msg['ref']
    logger.debug(branch)
    clone_project(git_ssh_url, branch)

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


def parse_cmdline():
    import argparse
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '-p', '--port', default=8000, help='port of the service listening', required=True
    )
    argparser.add_argument('--log-file', type=str, dest='log_file', required=True)
    argparser.add_argument(
        '--email-notify', dest='email_notify', action='store_true',
        help='notify the result of packaging.sh through email when it run failed'
    )
    argparser.add_argument('--email-server', dest='email_server')
    argparser.add_argument('--email-user', dest='email_user')
    argparser.add_argument('--email-passwd', dest='email_passwd')
    argparser.add_argument('--email-sender', dest='email_sender')
    argparser.add_argument('--email-receivers', dest='email_receivers', help='split with comma')
    return argparser.parse_args()


def main():
    """
        the main event.
    """
    global options
    options = parse_cmdline()

    init_logger(options.log_file)
    t = threading.Thread(target=parse_forever)
    t.setDaemon(True)
    t.start()

    server = HTTPServer(('', int(options.port)), webhookReceiver)
    try:
        logger.info('started web server...')
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('ctrl-c pressed, shutting down.')
        server.socket.close()

if __name__ == '__main__':
    main()
