# -*- coding: utf-8 -*-
"""FIELD01F1: guarded modeless lifetime; no Rhino/Eto/native geometry imports."""
from __future__ import print_function
import functools
import os
import time
import traceback
from field_core import text


def guarded(stage):
    """The startup try/except does not enclose later .NET event callbacks."""
    def decorate(method):
        @functools.wraps(method)
        def invoke(self, *args):
            try:
                return method(self, *args)
            except BaseException as exc:
                # A diagnostic failure must not become a second event exception.
                try:
                    self.life.error(stage, exc)
                except BaseException:
                    pass
                return None
        return invoke
    return decorate


class Lifetime(object):
    """One session, one deferred finalization; never owns a native object.

    schedule must queue work for a later UI turn, not run it synchronously.
    cleanup detaches event handlers and releases this session's strong reference.
    No claim about the cause of the earlier native Rhino crash is made here.
    """
    def __init__(self, report, schedule, cleanup, request_window_close):
        self.report = report
        self.schedule = schedule
        self.cleanup = cleanup
        self.request_window_close = request_window_close
        self.busy = False
        self.abort = False
        self.close_pending = False
        self.closed = False
        self.finalized = False
        self.queued = False
        self.failed = False
        self.document_available = True
        self.emergency_path = report.path + '.emergency.txt'

    def error(self, stage, exc):
        """Best effort separate log: no host console and no recursive reporting."""
        self.failed = True
        try:
            line = (u'SMARTSKIN_FIELD_CALLBACK_ERROR | utc=' + text(time.time()) +
                    u' | stage=' + text(stage) + u' | error=' + text(exc) + u'\n' +
                    text(traceback.format_exc()) + u'\n')
            with open(self.emergency_path, 'ab') as output:
                output.write(line.encode('utf-8'))
                output.flush()
        except BaseException:
            pass

    def emit(self, stage, **fields):
        if self.finalized:
            return False
        try:
            self.report.emit(stage, **fields)
            return True
        except BaseException as exc:
            self.error(stage, exc)
            return False

    def begin_work(self):
        if self.busy or self.close_pending or self.closed or self.finalized or not self.document_available:
            return False
        self.busy = True
        self.abort = False
        return True

    def end_work(self):
        self.busy = False
        if self.closed:
            self._queue_finalize()
        elif self.close_pending:
            try:
                # Do not call Close in a nested RhinoApp.Wait callback.
                self.schedule(self._close_after_work)
            except BaseException as exc:
                self.error('QUEUE_CLOSE_AFTER_WORK', exc)

    def _close_after_work(self):
        try:
            if not self.busy and not self.closed and not self.finalized:
                self.request_window_close()
        except BaseException as exc:
            self.error('CLOSE_AFTER_WORK', exc)

    def request_close(self):
        self.close_pending = True
        self.abort = True
        self.emit('CLOSING',busy=self.busy,native_geometry_disposal=False)
        return not self.busy

    def mark_document_closed(self):
        self.document_available = False
        self.close_pending = True
        self.abort = True
        self.emit('DOCUMENT_CLOSED',geometry_access_disabled=True)
        if not self.busy and not self.closed:
            try:
                self.schedule(self._close_after_work)
            except BaseException as exc:
                self.error('QUEUE_DOCUMENT_CLOSE',exc)

    def mark_closed(self):
        if self.closed:
            return
        self.closed = True
        self.abort = True
        self.close_pending = True
        self.emit('CLOSED_OBSERVED',native_geometry_disposal=False)
        if not self.busy:
            self._queue_finalize()

    def _queue_finalize(self):
        if self.queued or self.finalized:
            return
        self.queued = True
        try:
            self.schedule(self.finalize)
        except BaseException as exc:
            # Keep a bounded strong reference; do not perform native cleanup here.
            self.queued = False
            self.error('QUEUE_FINALIZE',exc)

    def finalize(self):
        if self.finalized or not self.closed or self.busy:
            return
        try:
            self.emit('CLOSE_FINALIZE_BEGIN',phase='LATER_UI_TURN',native_geometry_disposal=False)
            self.emit('SESSION_END',geometry_commit=False,callback_error=self.failed,
                      window_closed=True,rhino_process_exit_requested=False)
            self.report.finish()
        except BaseException as exc:
            self.error('FINALIZE_REPORT',exc)
            try:
                self.report.handle.close()
            except BaseException:
                pass
        finally:
            self.finalized = True
            try:
                self.cleanup()
            except BaseException as exc:
                self.error('DETACH_HANDLERS',exc)

    def cancelled(self):
        return self.abort or self.closed or not self.document_available
