# -*- coding: utf-8 -*-
"""FIELD01F1 user entry. Launch explicitly; close does not dispose native geometry."""
from __future__ import print_function
import os, sys, traceback
ROOT=os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from field_core import read_manifest, sha256_file, Report, text, PACKAGE
from field_lifecycle import Lifetime, guarded


def main():
    import Rhino as R
    import System
    import scriptcontext as sc
    import Eto.Forms as F
    import Eto.Drawing as D
    from native_check import check_case
    key='SmartSkin.Field.Panel'
    # Never close an existing modeless panel from a second script invocation.
    old=sc.sticky.get(key)
    if old is not None:
        R.RhinoApp.WriteLine('SMARTSKIN_FIELD_ALREADY_OPEN | close the existing panel first')
        return
    manifest=read_manifest(ROOT)
    model=os.path.join(ROOT,'comparison.3dm')
    if sha256_file(model)!=manifest['model_sha256']: raise ValueError('MASTER_MODEL_HASH_MISMATCH')
    doc=R.RhinoDoc.ActiveDoc
    if doc is None: raise ValueError('NO_ACTIVE_DOCUMENT')
    serial=doc.RuntimeSerialNumber
    report_dir=os.environ.get('SMARTSKIN_FIELD_REPORTS',os.path.join(os.environ['LOCALAPPDATA'],'SmartSkin','Field','reports'))

    def current_document():
        return R.RhinoDoc.FromRuntimeSerialNumber(serial)

    def get_snapshots():
        """Read and own explicit duplicates only inside startup or Check scope."""
        master=R.FileIO.File3dm.Read(model)
        if master is None: raise ValueError('MASTER_MODEL_READ_FAILED')
        result={}
        try:
            for item in master.Objects:
                duplicate=item.Geometry.Duplicate()
                if duplicate is None: raise ValueError('SNAPSHOT_DUPLICATION_FAILED')
                result[text(item.Attributes.ObjectId)]=duplicate
            return result
        except BaseException:
            release_snapshots(result)
            raise
        finally:
            master.Dispose()

    def release_snapshots(values):
        # These are owned duplicates. Never dispose borrowed Rhino document geometry.
        owned=list(values.values()); values.clear()
        first_error=None
        for value in owned:
            try: value.Dispose()
            except BaseException as exc:
                if first_error is None: first_error=exc
        if first_error is not None: raise first_error

    def verify_document(current,values):
        if current is None: raise ValueError('FIELD_DOCUMENT_CLOSED')
        for oid,snap in values.items():
            found=current.Objects.FindId(System.Guid(oid))
            if found is None or not R.Geometry.GeometryBase.GeometryEquals(found.Geometry,snap):
                raise ValueError('OPEN_THE_UNMODIFIED_FIELD_WORKING_COPY')

    snapshots=get_snapshots()
    try: verify_document(doc,snapshots)
    finally: release_snapshots(snapshots)
    # No native snapshot survives into the lifetime of the modeless form.
    def console(message):
        try: R.RhinoApp.WriteLine(message)
        except BaseException: pass
    session=Report(report_dir,console)
    session.emit('SESSION_BEGIN',package=PACKAGE,rhino=text(R.RhinoApp.Version),
                 kind='PRECOMPUTED_REJECTED_CANDIDATE_REVIEW',model_path=doc.Path,
                 source_geometry_writes=False,solver_running=False,window_owned_geometry=0,
                 runtime=text(System.Environment.Version),python=text(sys.version))

    class Panel(F.Form):
        def __init__(self):
            F.Form.__init__(self)
            self._idle_jobs=[]; self._idle_hooked=False
            self.life=Lifetime(session,self.schedule,self.detach,self.close_window)
            self.Title=u'Smart Skin Field — '+PACKAGE
            self.ClientSize=D.Size(640,285); self.Padding=D.Padding(12)
            self.Owner=R.UI.RhinoEtoApp.MainWindowForDocument(doc)
            self.choice=F.DropDown(); self.choice.DataStore=[c['label'] for c in manifest['cases']]
            self.status=F.Label(); self.status.Text=u'Форма НЕ принята. Полевой просмотр, не генератор.'
            self.note=F.Label(); self.note.Text=u'Виден только выбранный вариант. Исходная геометрия не изменяется.\nПроверка Join выполняется на копиях; результат не добавляется.'
            self.check=F.Button(); self.check.Text=u'Проверить показанный вариант → TXT'
            self.folder=F.Button(); self.folder.Text=u'Открыть папку отчётов'
            self.help=F.Label(); self.help.Text=u'Первый тест F1: закрой это окно крестиком без запуска проверки.\nRhino должен остаться открыт. Затем приложи TXT сеанса.\nСтарый P07F2 не заменяется; закрытие не принимает геометрию.'
            layout=F.DynamicLayout(); layout.Spacing=D.Size(8,10)
            layout.AddRow(self.status); layout.AddRow(self.choice); layout.AddRow(self.note)
            layout.AddRow(self.check,self.folder); layout.AddRow(self.help); layout.AddRow(None)
            self.Content=layout
            self.choice.SelectedIndexChanged+=self.on_choice
            self.check.Click+=self.on_check; self.folder.Click+=self.on_folder
            self.Closing+=self.on_closing; self.Closed+=self.on_closed
            R.RhinoDoc.CloseDocument+=self.on_document_closed
            self.choice.SelectedIndex=[c['id'] for c in manifest['cases']].index(manifest['default_case'])

        def active(self):
            if self.life.closed or not self.life.document_available: return None
            current=current_document(); active=R.RhinoDoc.ActiveDoc
            if current is None or active is None or active.RuntimeSerialNumber!=serial: return None
            return current

        def schedule(self,action):
            self._idle_jobs.append(action)
            if not self._idle_hooked:
                R.RhinoApp.Idle+=self.on_idle
                self._idle_hooked=True

        @guarded('IDLE')
        def on_idle(self,sender,event):
            R.RhinoApp.Idle-=self.on_idle
            self._idle_hooked=False
            actions=self._idle_jobs; self._idle_jobs=[]
            for action in actions:
                try: action()
                except BaseException as exc: self.life.error('IDLE_ACTION',exc)

        def close_window(self):
            if not self.life.closed: self.Close()

        @guarded('SHOW_CASE')
        def on_choice(self,sender,event):
            if self.life.busy or self.life.close_pending or self.choice.SelectedIndex<0: return
            current=self.active()
            if current is None:
                self.status.Text=u'Вернись в документ полевого пакета.'; return
            selected=manifest['cases'][self.choice.SelectedIndex]
            names=set(c['layer'] for c in manifest['cases'])
            for layer in current.Layers:
                if not layer.IsDeleted and layer.Name in names:
                    layer.IsVisible=(layer.Name==selected['layer'])
                    if not current.Layers.Modify(layer,layer.Index,True): raise ValueError('FIELD_LAYER_CHANGE_FAILED')
            current.Objects.UnselectAll(); current.Views.Redraw()
            self.status.Text=u'Форма: НЕ ПРИНЯТА. '+text(selected['id'])
            self.life.emit('SHOW_CASE',case=selected['id'],candidate_hash=selected['candidate_hash'],
                           upstream_form=selected['form_status'],geometry_commit=False)

        @guarded('CHECK')
        def on_check(self,sender,event):
            current=self.active()
            if current is None or not self.life.begin_work(): return
            values={}
            try:
                self.choice.Enabled=False; self.check.Enabled=False
                self.status.Text=u'Проверка на копиях. Esc — отмена между нативными вызовами.'
                self.life.emit('CHECK_SCOPE_BEGIN',native_snapshots='SCOPED_TO_CHECK')
                values=get_snapshots(); verify_document(current,values)
                case=manifest['cases'][self.choice.SelectedIndex]
                path,state=check_case(current,manifest,case,report_dir,values,self.life.cancelled,lambda:self.life.document_available)
                if not self.life.closed and self.life.document_available:
                    self.status.Text=u'TXT сохранён. '+state+u'. Форма всё ещё не принята.'
                self.life.emit('CHECK_FINISHED',case=case['id'],state=state,report=path,geometry_commit=False)
            except BaseException as exc:
                self.life.error('CHECK',exc)
                console('SMARTSKIN_FIELD_REPORT_STOP | '+text(exc))
            finally:
                try: release_snapshots(values)
                except BaseException as exc: self.life.error('CHECK_RELEASE_SNAPSHOTS',exc)
                self.life.emit('CHECK_SCOPE_END',window_owned_geometry=0)
                self.life.end_work()
                if not self.life.closed and self.life.document_available:
                    self.choice.Enabled=not self.life.close_pending
                    self.check.Enabled=not self.life.close_pending

        @guarded('OPEN_REPORT_FOLDER')
        def on_folder(self,sender,event):
            if not self.life.closed:
                System.Diagnostics.Process.Start('explorer.exe',u'"'+report_dir+u'"')

        @guarded('CLOSING_CALLBACK')
        def on_closing(self,sender,event):
            event.Cancel=not self.life.request_close()
            if event.Cancel:
                self.status.Text=u'Отмена запрошена. Окно закроется после выхода из проверки.'

        @guarded('CLOSED_CALLBACK')
        def on_closed(self,sender,event):
            # No file finalization, geometry access, native Dispose or sticky removal here.
            self.life.mark_closed()

        @guarded('DOCUMENT_CLOSED_CALLBACK')
        def on_document_closed(self,sender,event):
            if event.Document.RuntimeSerialNumber==serial: self.life.mark_document_closed()

        def detach(self):
            # Called on a later UI turn, never inside the Closed callback.
            try:
                self.choice.SelectedIndexChanged-=self.on_choice
                self.check.Click-=self.on_check; self.folder.Click-=self.on_folder
                self.Closing-=self.on_closing; self.Closed-=self.on_closed
            except BaseException as exc: self.life.error('DETACH_UI',exc)
            try: R.RhinoDoc.CloseDocument-=self.on_document_closed
            except BaseException as exc: self.life.error('DETACH_DOCUMENT',exc)
            if sc.sticky.get(key) is self: sc.sticky.pop(key,None)
            # Do not call self.Dispose(); Eto owns the closed window.

    panel=None
    try:
        panel=Panel(); sc.sticky[key]=panel; panel.Show()
        selected=manifest['cases'][panel.choice.SelectedIndex]
        box=R.Geometry.BoundingBox.Unset
        for cap in selected['caps']:
            obj=doc.Objects.FindId(System.Guid(cap['object_id']))
            box.Union(obj.Geometry.GetBoundingBox(True))
        if box.IsValid and doc.Views.ActiveView is not None:
            doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(box); doc.Views.Redraw()
        console('SMARTSKIN_FIELD_READY | '+PACKAGE+' | solver=NOT_RUN | form=REJECTED_RESEARCH_ONLY')
        console('SMARTSKIN_FIELD_SESSION | '+session.path)
    except BaseException:
        if panel is not None:
            try: panel.Close()
            except BaseException: pass
        else:
            try: session.finish()
            except BaseException: pass
        raise

if __name__=='__main__':
    try: main()
    except BaseException as exc:
        import Rhino
        message='SMARTSKIN_FIELD_START_STOP | '+text(exc)+'\n'+traceback.format_exc()
        Rhino.RhinoApp.WriteLine(message)
