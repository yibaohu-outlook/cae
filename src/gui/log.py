#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" © Ihor Mirzov, May 2020
Distributed under GNU General Public License v3.0

Custon logging handlers for catching CCX and CGX output.
The Text handler is created once per session
and prints into CAE's textEdit.
The File handler is created any time you open a model.
Log file has the same name as model. """

# Standard modules
import os
import re
import time
import logging
import threading

# External modules
from PyQt5 import QtGui, QtWidgets


class MyLoggingHandler(logging.Handler):

    # Target could be textEdit or file
    def __init__(self, target):
        super().__init__() # create handler
        self.target = target
        fmt = logging.Formatter('%(levelname)s, %(module)s: %(message)s')
        self.setFormatter(fmt)


# Handler to show logs in the CAE's textEdit
class MyTextLoggingHandler(MyLoggingHandler):

    # Sends log messages to Window's textEdit widget
    def emit(self, LogRecord):

        # Message color depending on logging level
        color = {
            'NOTSET':   'Black',
            'DEBUG':    'Gray',
            'INFO':     'Green',
            'WARNING':  'Blue',
            'ERROR':    'Red',
            'CRITICAL': 'Pink', }
        if LogRecord.levelname in color:
            color = color[LogRecord.levelname]
        else:
            color = '#2F4F4F' # DARKSLATEGRAY

        # Move newlines before the levelname
        msg = LogRecord.getMessage()
        while msg.startswith('\n'):
            self.target.append('<p></p>')
            msg = msg[1:]

        # Keep all newlines in message
        msg = msg.replace('\n', '<br/>')

        if LogRecord.levelname == 'Level 25':
            msg = '<p style=\"margin:0px; color:{};\">{}</p>'\
                .format(color, msg)
        else:
            msg = '<span style=\"color:{};\">{}</span>: {}'\
                .format(color, LogRecord.levelname, msg)
            msg = '<p style=\"margin:0px;\">{}</p>'.format(msg)

        # Print message and scroll it to the end
        self.target.append(msg)
        self.target.moveCursor(QtGui.QTextCursor.End)


# Handler to write the job's log file
class MyFileLoggingHandler(MyLoggingHandler):

    def emit(self, LogRecord):

        # Move newlines before the levelname
        msg = LogRecord.getMessage()
        while msg.startswith('\n'):
            with open(self.target, 'a') as f:
                f.write('\n')
            msg = msg[1:]

        msg = '{}: {}'.format(LogRecord.levelname, msg)
        if msg.startswith('Level 25: '):
            msg = msg[10:]

        # Write message to the log file
        with open(self.target, 'a') as f:
            f.write(msg + '\n')
        # self.flush()


# Called only once on startup
def add_text_handler(textEdit):
    logging.getLogger().handlers = []
    h = MyTextLoggingHandler(textEdit)
    logging.getLogger().addHandler(h)


# Called at each file import
def add_file_handler(log_file):
    if len(logging.getLogger().handlers) > 1:
        logging.getLogger().handlers.pop()
    h = MyFileLoggingHandler(log_file)
    logging.getLogger().addHandler(h)
    if os.path.exists(log_file):
        os.remove(log_file)


# Process one non-empty stdout message
def log_line(line):
    if not len(line.strip()):
        return
    if line == 'key: from string   not known':
        return
    if line == 'key: from string   ? not known':
        return
    logging_levels = {
        'NOTSET': 0,
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50}
    if line.startswith(tuple(logging_levels.keys())):
        match = re.search('(^\w+): (.+)', line) # levelname and message
        if match: # skip logging of empty strings
            level = match.group(1)
            line = match.group(2)
            logging.log(logging_levels[level], line)
    else:
        logging.log(25, line)


# Read and log processes stdout
# Attention: it's infinite pipe reader!
# An old reader quits if a new one is started
def read_output(pipe, cgx_process):

    # Posting to CGX window outputs to std line with backspaces:
    # pplploplotplot plot eplot e plot e Oplot e OUplot e OUTplot e OUT-plot e OUT-Splot e OUT-S3
    def filter_backspaces(line):
        if 8 in line:
            l = bytearray()
            i = 1
            b = line[-i]
            while b != 8:
                l.insert(0, b)
                i += 1
                b = line[-i]
            return l
        else:
            return line

    # Infininte cycle to read process'es stdout
    def read_pipe_and_log(pipe, cgx_process):
        time.sleep(3) # save from 100% CPU bug
        while True:

            # Stop logging if CGX is closed
            if cgx_process is None:
                return

            # Stop logging is a new thread created
            t_names = sorted([t.name for t in threading.enumerate() \
                if t.name.startswith('read_output')])
            if len(t_names) >= 2:

                # Quit the cycle and finish the thread if it's outdated
                if threading.current_thread().name == t_names[0]:
                    logging.debug('Thread {} stopped.'.format(t_names[0]))
                    return

                # A new thread shouldn't log until an old one finishes
                else:
                    time.sleep(0.3)
                    continue

            # Pack/group log messages
            line = pipe.readline()
            if line != b'':
                line = filter_backspaces(line)
                line = line.decode().strip()
                log_line(line)
                time.sleep(0.03) # CAE dies during fast logging
            else:
                time.sleep(0.3) # reduce CPU usage

    t_name = 'read_output_{}'.format(time.time()).split('.')[0]
    t = threading.Thread(target=read_pipe_and_log,
        args=(pipe, cgx_process), name=t_name, daemon=True)
    t.start()

    # List currently running threads
    t_names = sorted([t.name for t in threading.enumerate() \
        if t.name.startswith('read_output')])
    msg = 'Output reading threads:\n' + ', '.join(t_names)
    logging.debug(msg)
