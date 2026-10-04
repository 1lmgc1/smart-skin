# Developer-only tests. Pure callback/ordering tests, NOT a native Rhino crash reproduction.
import ast, pathlib, tempfile, unittest
from field_core import Report
from field_lifecycle import Lifetime, guarded
ROOT=pathlib.Path(__file__).parent

class DummyReport:
    def __init__(self,root):
        self.path=str(pathlib.Path(root)/'session.txt');self.events=[];self.finished=0;self.fail_emit=False;self.fail_finish=False
    def emit(self,name,**data):
        if self.fail_emit: raise OSError('injected write failure')
        self.events.append((name,data))
    def finish(self):
        self.finished+=1
        if self.fail_finish: raise OSError('injected readback failure')
        return self.path

class LifetimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.report=DummyReport(self.tmp.name);self.queue=[];self.clean=[];self.close=[]
        self.life=Lifetime(self.report,self.queue.append,lambda:self.clean.append('clean'),lambda:self.close.append('close'))
    def idle(self):
        jobs=self.queue[:];self.queue.clear()
        for job in jobs:job()
    def test_close_is_deferred(self):
        self.assertTrue(self.life.request_close());self.life.mark_closed()
        self.assertEqual(self.clean,[]);self.assertEqual(self.report.finished,0)
        self.idle();self.assertEqual(self.clean,['clean']);self.assertEqual(self.report.finished,1)
    def test_repeated_closed_is_idempotent(self):
        self.life.mark_closed();self.life.mark_closed();self.idle();self.life.finalize()
        self.assertEqual(self.report.finished,1);self.assertEqual(len(self.clean),1)
    def test_busy_close_requests_cancel(self):
        self.assertTrue(self.life.begin_work());self.assertFalse(self.life.request_close())
        self.assertTrue(self.life.cancelled());self.assertEqual(self.queue,[])
        self.life.end_work();self.assertEqual(self.close,[]);self.idle();self.assertEqual(self.close,['close'])
    def test_forced_closed_does_not_clean_busy_work(self):
        self.life.begin_work();self.life.mark_closed();self.idle();self.assertEqual(self.clean,[])
        self.life.end_work();self.idle();self.assertEqual(self.clean,['clean'])
    def test_new_work_refused_after_closing(self):
        self.life.request_close();self.assertFalse(self.life.begin_work())
    def test_reentrant_check_refused(self):
        self.assertTrue(self.life.begin_work());self.assertFalse(self.life.begin_work())
    def test_document_close_invalidates_work(self):
        self.life.begin_work();self.life.mark_document_closed()
        self.assertFalse(self.life.document_available);self.assertTrue(self.life.cancelled())
        self.assertEqual(self.queue,[]);self.life.end_work();self.idle();self.assertEqual(self.close,['close'])
    def test_document_close_idle_schedules_window_close(self):
        self.life.mark_document_closed();self.assertFalse(self.life.begin_work());self.idle();self.assertEqual(self.close,['close'])
    def test_report_write_failure_cannot_escape_close(self):
        self.report.fail_emit=True;self.life.request_close();self.life.mark_closed();self.idle()
        self.assertEqual(self.clean,['clean']);self.assertTrue(self.life.failed)
    def test_report_finish_failure_cannot_escape_idle(self):
        self.report.fail_finish=True;self.life.mark_closed();self.idle()
        self.assertTrue(self.life.finalized);self.assertEqual(self.clean,['clean'])
        self.assertIn('FINALIZE_REPORT',pathlib.Path(self.life.emergency_path).read_text())
    def test_cleanup_error_contained(self):
        def bad():raise ValueError('detach failed')
        self.life.cleanup=bad;self.life.mark_closed();self.idle();self.assertTrue(self.life.failed)
    def test_scheduler_error_does_not_finalize_inside_closed(self):
        def bad(unused):raise ValueError('scheduler failed')
        self.life.schedule=bad;self.life.mark_closed();self.assertEqual(self.clean,[]);self.assertFalse(self.life.finalized)
    def test_guard_event_exception_contained(self):
        life=self.life
        class Callback:
            def __init__(self):self.life=life
            @guarded('TEST_EVENT')
            def event(self,*args):raise ValueError('callback failed')
        Callback().event(None,None);self.assertTrue(life.failed)
        self.assertIn('TEST_EVENT',pathlib.Path(life.emergency_path).read_text())
    def test_guard_baseexception_contained(self):
        life=self.life
        class Callback:
            def __init__(self):self.life=life
            @guarded('INTERRUPT')
            def event(self,*args):raise KeyboardInterrupt()
        Callback().event();self.assertTrue(life.failed)
    def test_secondary_error_contained(self):
        class BadLife:
            def error(self,*args):raise RuntimeError('failed logger')
        class Callback:
            life=BadLife()
            @guarded('FAIL')
            def event(self):raise ValueError('original error')
        self.assertIsNone(Callback().event())
    def test_snapshot_ownership_not_in_lifetime(self):
        for name in ('snapshots','master','RhinoDoc','Geometry','Dispose'):
            self.assertNotIn(name,Lifetime.__dict__)
    def test_real_utf8_report_finalizes_with_integrity(self):
        report=Report(self.tmp.name);life=Lifetime(report,self.queue.append,lambda:None,lambda:None)
        life.emit('SESSION_BEGIN',msg='Закрытие');life.request_close();life.mark_closed();self.idle()
        self.assertTrue(report.closed);data=pathlib.Path(report.path).read_text(encoding='utf-8-sig')
        self.assertIn('CLOSE_FINALIZE_BEGIN',data);self.assertIn('INTEGRITY',data)
    def test_no_fictitious_saved_after_io_failure(self):
        messages=[];report=Report(self.tmp.name,messages.append);life=Lifetime(report,self.queue.append,lambda:None,lambda:None)
        report.handle.close();life.mark_closed();self.idle()
        self.assertEqual(messages,[]);self.assertTrue(life.finalized)

class SourceLifecycleTests(unittest.TestCase):
    def setUp(self):self.tree=ast.parse((ROOT/'field_runtime.py').read_text(encoding='utf8'))
    def method(self,name):return next(n for n in ast.walk(self.tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    def test_all_event_entries_guarded(self):
        names=['on_choice','on_check','on_folder','on_closing','on_closed','on_idle','on_document_closed']
        for name in names:self.assertTrue(self.method(name).decorator_list,name)
    def test_close_does_not_access_native_geometry(self):
        s=ast.unparse(self.method('on_closed'))
        for bad in ('Dispose','snapshots','finish','sticky','Redraw','Close()'):self.assertNotIn(bad,s)
    def test_old_window_not_closed_on_duplicate_launch(self):
        self.assertNotIn('old.Close()', (ROOT/'field_runtime.py').read_text())
    def test_no_explicit_form_dispose(self):
        for n in ast.walk(self.tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='Dispose':
                self.assertNotIn(ast.unparse(n.func.value),('self','panel','old'))
    def test_check_snapshots_released_in_finally(self):
        n=self.method('on_check');self.assertIn('release_snapshots(values)',ast.unparse(n));self.assertTrue(any(isinstance(x,ast.Try) and x.finalbody for x in ast.walk(n)))
    def test_document_owner_is_document_scoped(self):
        self.assertIn('MainWindowForDocument(doc)',(ROOT/'field_runtime.py').read_text())
    def test_source_topology_checker_only_adds_document_guard(self):
        s=(ROOT/'native_check.py').read_text()
        self.assertIn('FromRuntimeSerialNumber',s);self.assertIn('NOT_VERIFIED_DOCUMENT_CLOSED',s)
    def test_installer_does_not_autolaunch(self):
        s=(ROOT/'install.ps1').read_text();self.assertIn('$Launch -and -not $NoLaunch',s)
        cmd=(ROOT/'install.cmd').read_text();self.assertNotIn('-Launch',cmd)

if __name__=='__main__':unittest.main()
