# -*- coding: utf-8 -*-
"""User entry point. Installer launches this in Rhino's IronPython automatically."""
from __future__ import print_function
import os, sys, traceback
ROOT=os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from field_core import read_manifest, sha256_file, Report, text, PACKAGE

def main():
    import Rhino as R
    import System
    import scriptcontext as sc
    import Eto.Forms as F
    import Eto.Drawing as D
    from native_check import check_case
    manifest=read_manifest(ROOT)
    model=os.path.join(ROOT,'comparison.3dm')
    if sha256_file(model)!=manifest['model_sha256']: raise ValueError('MASTER_MODEL_HASH_MISMATCH')
    doc=R.RhinoDoc.ActiveDoc
    report_dir=os.environ.get('SMARTSKIN_FIELD_REPORTS',os.path.join(os.environ['LOCALAPPDATA'],'SmartSkin','Field','reports'))
    master=R.FileIO.File3dm.Read(model)
    if master is None: raise ValueError('MASTER_MODEL_READ_FAILED')
    snapshots={}
    for obj in master.Objects:
        snapshots[text(obj.Attributes.ObjectId)]=obj.Geometry.Duplicate()
    master.Dispose()
    for oid,snap in snapshots.items():
        current=doc.Objects.FindId(System.Guid(oid))
        if current is None or not R.Geometry.GeometryBase.GeometryEquals(current.Geometry,snap):
            for g in snapshots.values(): g.Dispose()
            raise ValueError('OPEN_THE_INSTALLED_FIELD_WORKING_COPY')
    old=sc.sticky.get('SmartSkin.Field.Panel')
    if old is not None:
        try: old.Close()
        except Exception: pass
    session=Report(report_dir,R.RhinoApp.WriteLine)
    session.emit('SESSION_BEGIN',package=PACKAGE,rhino=text(R.RhinoApp.Version),
                 kind='PRECOMPUTED_REJECTED_CANDIDATE_REVIEW',model_path=doc.Path,
                 source_geometry_writes=False,solver_running=False)
    class Panel(F.Form):
        def __init__(self):
            F.Form.__init__(self)
            self.busy=False; self.abort=False; self.disposed=False
            self.Title=u'Smart Skin Field — P08D1B-FIELD01'
            self.ClientSize=D.Size(590,265); self.Padding=D.Padding(12)
            self.Owner=R.UI.RhinoEtoApp.MainWindow
            self.choice=F.DropDown(); self.choice.DataStore=[c['label'] for c in manifest['cases']]
            self.status=F.Label(); self.status.Text=u'Предрассчитанные варианты. Форма НЕ принята. Это не новый решатель.'
            self.note=F.Label(); self.note.Text=u'Виден только выбранный вариант. Исходные поверхности не изменяются.\nПроверка Join выполняется на копиях; результат не добавляется в модель.'
            self.check=F.Button(); self.check.Text=u'Проверить показанный вариант → TXT'
            self.folder=F.Button(); self.folder.Text=u'Открыть папку отчётов'
            self.help=F.Label(); self.help.Text=u'Zebra запускается штатно на выбранной крышке и её соседях.\nЗакрытие окна не принимает геометрию. Старый Smart Skin не используется.'
            layout=F.DynamicLayout(); layout.Spacing=D.Size(8,10)
            layout.AddRow(self.status); layout.AddRow(self.choice); layout.AddRow(self.note)
            layout.AddRow(self.check,self.folder); layout.AddRow(self.help); layout.AddRow(None)
            self.Content=layout
            self.choice.SelectedIndexChanged+=self.on_choice
            self.check.Click+=self.on_check; self.folder.Click+=self.on_folder
            self.Closing+=self.on_closing; self.Closed+=self.on_closed
            self.choice.SelectedIndex=[c['id'] for c in manifest['cases']].index(manifest['default_case'])
        def active(self):
            active=R.RhinoDoc.ActiveDoc
            return active is not None and active.RuntimeSerialNumber==doc.RuntimeSerialNumber
        def on_choice(self,sender,event):
            if self.busy or self.choice.SelectedIndex<0: return
            if not self.active():
                self.status.Text=u'Вернись в документ полевого пакета.'; return
            selected=manifest['cases'][self.choice.SelectedIndex]
            try:
                names=set(c['layer'] for c in manifest['cases'])
                for layer in doc.Layers:
                    if not layer.IsDeleted and layer.Name in names:
                        layer.IsVisible=(layer.Name==selected['layer'])
                        if not doc.Layers.Modify(layer,layer.Index,True): raise ValueError('FIELD_LAYER_CHANGE_FAILED')
                doc.Objects.UnselectAll(); doc.Views.Redraw()
                self.status.Text=u'Форма: НЕ ПРИНЯТА. '+text(selected['id'])
                session.emit('SHOW_CASE',case=selected['id'],candidate_hash=selected['candidate_hash'],
                             upstream_form=selected['form_status'],geometry_commit=False)
            except Exception as exc:
                self.status.Text=u'Ошибка переключения: '+text(exc)
                R.RhinoApp.WriteLine('SMARTSKIN_FIELD_STOP | '+text(exc))
        def on_check(self,sender,event):
            if self.busy: return
            if not self.active(): self.status.Text=u'Активируй документ полевого пакета.'; return
            self.busy=True; self.abort=False; self.choice.Enabled=False; self.check.Enabled=False
            self.status.Text=u'Проверка на копиях. Esc — отмена между нативными вызовами.'
            R.RhinoApp.Wait()
            try:
                case=manifest['cases'][self.choice.SelectedIndex]
                path,state=check_case(doc,manifest,case,report_dir,snapshots,lambda:self.abort)
                self.status.Text=(u'TXT сохранён. '+state+u'. Форма всё ещё не принята.')
                session.emit('CHECK_FINISHED',case=case['id'],state=state,report=path,geometry_commit=False)
            except BaseException as exc:
                self.status.Text=u'Ошибка проверки: '+text(exc)
                R.RhinoApp.WriteLine('SMARTSKIN_FIELD_REPORT_STOP | '+text(exc))
            finally:
                self.busy=False; self.choice.Enabled=True; self.check.Enabled=True
        def on_folder(self,sender,event):
            System.Diagnostics.Process.Start('explorer.exe',u'"'+report_dir+u'"')
        def on_closing(self,sender,event):
            if self.busy:
                self.abort=True; event.Cancel=True
                self.status.Text=u'Отмена запрошена; дождись текущего нативного вызова.'
        def on_closed(self,sender,event):
            if self.disposed: return
            self.disposed=True
            try:
                session.emit('SESSION_END',geometry_commit=False,layer_visibility_changed=True)
                session.finish()
            finally:
                for g in snapshots.values(): g.Dispose()
                sc.sticky.pop('SmartSkin.Field.Panel',None)
    panel=Panel(); sc.sticky['SmartSkin.Field.Panel']=panel; panel.Show()
    # This changes the view only. Original model geometry and units stay intact.
    selected=manifest['cases'][panel.choice.SelectedIndex]
    box=R.Geometry.BoundingBox.Unset
    for cap in selected['caps']:
        obj=doc.Objects.FindId(System.Guid(cap['object_id']))
        box.Union(obj.Geometry.GetBoundingBox(True))
    if box.IsValid and doc.Views.ActiveView is not None:
        doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(box); doc.Views.Redraw()
    R.RhinoApp.WriteLine('SMARTSKIN_FIELD_READY | '+PACKAGE+' | solver=NOT_RUN | form=REJECTED_RESEARCH_ONLY')

if __name__=='__main__':
    try: main()
    except BaseException as exc:
        import Rhino
        message='SMARTSKIN_FIELD_START_STOP | '+text(exc)+'\n'+traceback.format_exc()
        Rhino.RhinoApp.WriteLine(message)
        try:
            import System.Windows.Forms as W
            W.MessageBox.Show(message,'Smart Skin Field')
        except Exception: pass
