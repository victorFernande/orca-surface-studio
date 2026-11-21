from __future__ import annotations

from dataclasses import asdict, fields
import json
import re
from pathlib import Path
import threading
import time
import uuid
from typing import Any

from .capture import CaptureStore, atomic_write
from .contracts import ProjectSnapshot, StaleArtifactError, WaveError, WaveParameters, digest
from .engine import process_gcode
from .geometry import analyze_snapshot
from .package import build_sliced_package, extract_plate_gcode
from .prepared_model import PreparedMesh, exported_settings
from .project_io import write_model_project


BUILTIN_PRESETS = [
    {"id":"sine-vase","name":"Vaso senoidal · combinado","parameters":{"mode":"combined","amplitude_mm":1.0,"wave_count":6,"z_ratio":.5,"start_height_mm":1.0}},
    {"id":"gentle-xy","name":"Ondas suaves","parameters":{"mode":"xy","amplitude_mm":.08,"wavelength_mm":12}},
    {"id":"wide-xy","name":"Ondas largas","parameters":{"mode":"xy","amplitude_mm":.12,"wavelength_mm":20}},
    {"id":"ribbed-xy","name":"Nervuras finas","parameters":{"mode":"xy","amplitude_mm":.06,"wavelength_mm":4}},
    {"id":"spiral-xy","name":"Torção planar","parameters":{"mode":"xy","amplitude_mm":.08,"wavelength_mm":10,"twist_deg_per_mm":12}},
    {"id":"aligned-z","name":"Z alinhado • bancada","parameters":{"mode":"z","amplitude_mm":.08,"wavelength_mm":10}},
    {"id":"gentle-z","name":"Z sutil • bancada","parameters":{"mode":"z","amplitude_mm":.05,"wavelength_mm":15}},
    {"id":"wide-z","name":"Z largo • bancada","parameters":{"mode":"z","amplitude_mm":.06,"wavelength_mm":25}},
    {"id":"control","name":"Controle sem onda","parameters":{"mode":"z","amplitude_mm":0,"wavelength_mm":10}},
]


class StudioController:
    def __init__(self, storage: Path, host: Any = None) -> None:
        self.storage = Path(storage).resolve()
        self.host = host
        self.captures = CaptureStore(self.storage,host.allowed_source_roots() if host else (),
                                     host.validate_source if host else None)
        self.lock = threading.RLock()
        self.snapshot: ProjectSnapshot | None = None
        self._objects: list = []
        self._status = "idle"
        self._message = "Adicione as peças, prepare a captura e fatie a mesa no Orca."
        self._job = None
        self._result: dict | None = None
        self._parameters: dict = {}
        self._pending_open = False
        self._preview_verified = False
        self._opening_preview = False
        self._importing_preview = False
        self._preview_request = None
        self._capture_access_pending = None
        self._events: list[dict] = []
        self._sequence=0
        self._analysis_job=None
        self._gui_armed=False
        self._slice_gui: ProjectSnapshot | None=None
        self._effective_revision=None
        self._conformal_session=None
        self._surface_rejection=None

    def event(self, name: str, **details: Any) -> None:
        with self.lock:
            self._events.append({"event": name, **details})
            self._events = self._events[-100:]
            try:
                atomic_write(self.storage/"events.json", json.dumps(self._events,ensure_ascii=False,indent=2).encode())
            except OSError:
                pass

    def _presets(self) -> list:
        try:
            user = json.loads((self.storage/"presets.json").read_text(encoding="utf-8"))
            if not isinstance(user,list):
                user=[]
        except (OSError,ValueError):
            user=[]
        return [*BUILTIN_PRESETS,*user]

    def state(self) -> dict:
        with self.lock:
            self._sequence+=1
            session=self._conformal_session
            conformal={k:session[k] for k in ("phase","original_id","native_id","settings","origin_backup","prepared_path","region_catalog") if k in session} if session else None
            return {"status":self._status,"message":self._message,"objects":self._objects,
                    "revision":self.snapshot.revision if self.snapshot else None,
                    "capture":self.captures.captured.to_dict() if self.captures.captured else None,
                    "result":self._result,"presets":self._presets(),"bench_only":True,
                    "capture_setup_required":bool(self.host and not self.host.capture_ready()),
                    "native":bool(self.host),"events":self._events[-8:],"sequence":self._sequence,
                    "parameters_by_object":self._parameters,"conformal":conformal,
                    "surface_rejection":self._surface_rejection}

    def invalidate(self, reason: str, *, preserve_conformal: bool=False) -> None:
        with self.lock:
            if not preserve_conformal:
                self._conformal_session=None
            self._job=None
            self._surface_rejection=None
            self._analysis_job=None
            self._result=None
            self._preview_verified=False
            self._opening_preview=False
            self._importing_preview=False
            self._preview_request=None
            self._capture_access_pending=None
            self._pending_open=False
            self._gui_armed=False
            self._slice_gui=None
            self._effective_revision=None
            self.captures.invalidate(reason)
            self._status="slicing_required"
            self._message=reason
            self.event("invalidated",reason=reason)

    def refresh(self) -> None:
        if self.host is None:
            return
        session=self._conformal_session
        if session and session["phase"] in {"opening","checking"}:
            self.prepared_project_opened("")
            return
        snapshot=self.host.snapshot()
        if (self.storage/"study_connection.json").is_file():
            atomic_write(self.storage/"last-live-snapshot.json",json.dumps(snapshot.to_dict(),ensure_ascii=False,indent=2).encode())
        with self.lock:
            if self.snapshot and self.snapshot.revision==snapshot.revision and self._objects:
                self._gui_armed=True
                return
            if self.snapshot and self.snapshot.revision!=snapshot.revision:
                changed_settings=sorted(key for key in set(self.snapshot.settings)|set(snapshot.settings)
                                        if self.snapshot.settings.get(key)!=snapshot.settings.get(key))
                self.event("snapshot_mismatch",before=self.snapshot.revision,after=snapshot.revision,
                           settings_keys=changed_settings,objects_equal=self.snapshot.objects==snapshot.objects,
                           session_equal=self.snapshot.session_id==snapshot.session_id,plate_equal=self.snapshot.plate_index==snapshot.plate_index)
                self.invalidate("As peças ou configurações mudaram. Fatie novamente.")
            self.snapshot=snapshot
            self._gui_armed=bool(snapshot.objects)
            self._objects=[]
            if not snapshot.objects:
                return
            job=uuid.uuid4().hex
            self._analysis_job=job
            self._status="analyzing"
            self._message="Analisando as peças em segundo plano…"
        def work():
            try:
                objects=analyze_snapshot(snapshot)
                from .roof_regions import roof_region_catalog
                for obj in objects:
                    obj['roof_regions']=roof_region_catalog(snapshot,str(obj['id']))
                with self.lock:
                    if self._analysis_job!=job:
                        return
                    self._objects=objects
                    self._analysis_job=None
                    self._status="idle" if self.captures.captured else "slicing_required"
                    self._message="Sugestões geométricas disponíveis. Fatie a mesa para validar as trajetórias."
            except Exception as exc:
                with self.lock:
                    if self._analysis_job==job:
                        self._status="error"
                        self._message=str(exc)
                        self._analysis_job=None
        threading.Thread(target=work,name="OrcaWave-Analyze",daemon=True).start()

    def analyze(self, selected: list[str]) -> None:
        self.refresh()
        if self.snapshot is None:
            raise WaveError("Adicione as peças à mesa do Orca.")
        with self.lock:
            if selected and not set(selected).issubset({str(x["id"]) for x in self.snapshot.objects}):
                raise WaveError("A seleção não pertence à mesa atual.")
            if self._analysis_job is None:
                self._status="idle" if self.captures.captured else "slicing_required"
                self._message="Sugestões calculadas. Ajuste os parâmetros e fatie a mesa para validar as trajetórias."

    def slice_started(self, model_id: str) -> None:
        # Print::process runs on the slicing worker; only use data frozen by the GUI.
        with self.lock:
            gui=self.snapshot if self._gui_armed and self.snapshot and self.snapshot.session_id==model_id else None
            overlaps=self._slice_gui is not None
            ctx=self._conformal_session
            keep=bool(ctx and gui and not overlaps and ctx.get("bound_revision")==gui.revision
                      and ctx["phase"] in {"awaiting_slice","captured","ready"})
            self.invalidate("Atualize as peças no estúdio antes de fatiar a mesa.",preserve_conformal=keep)
            if keep:
                ctx.update(phase="slicing",capture_id=None,capture_sha=None)
            if gui is not None and not overlaps:
                self._slice_gui=gui
                self._status="processing"
                self._message="Acompanhando o fatiamento do Orca…"
                self.event("slice_started",model_id=model_id,gui_revision=gui.revision)

    def capture_begin(self, snapshot: ProjectSnapshot, mapping: dict[int,str]) -> None:
        if (self.storage/"study_connection.json").is_file():
            atomic_write(self.storage/"last-slice-snapshot.json",json.dumps(snapshot.to_dict(),ensure_ascii=False,indent=2).encode())
        with self.lock:
            gui=self._slice_gui if self.host else snapshot
            if gui is None:
                raise StaleArtifactError("Atualize as peças no estúdio e fatie novamente.")
            if (gui.session_id!=snapshot.session_id or gui.plate_index!=snapshot.plate_index
                    or gui.objects!=snapshot.objects):
                raise StaleArtifactError("As peças ou a placa divergem entre a interface e o fatiador.")
            ctx=self._conformal_session
            if ctx and (ctx["phase"]!="slicing" or len(mapping)!=1 or set(mapping.values())!={ctx.get("native_id")}):
                self.invalidate("O fatiador não identificou exclusivamente a peça achatada verificada.")
                raise StaleArtifactError(self._message)
            self.snapshot=gui
            self._analysis_job=None
            self._objects=analyze_snapshot(gui)
            self._job=None
            self._result=None
            self._preview_verified=False
            self._effective_revision=snapshot.revision
            self.captures.begin(gui,mapping,effective_snapshot=snapshot if self.host else None)
            self._status="processing"
            self._message="Acompanhando o fatiamento do Orca…"
            self.event("capture_begin",plate_index=snapshot.plate_index,revision=gui.revision,
                       effective_revision=snapshot.revision,mapping=mapping)

    def capture_finished(self, model_id: str, path: str, success: bool) -> None:
        try:
            with self.lock:
                capture=self.captures.finish(model_id,path,success=success)
                self._status="processing" if self.host else "idle"
                self._message=("Aguardando a conclusão do fatiamento na interface." if self.host else
                               "Fatiamento capturado. Escolha as peças e gere o G-code com ondas.")
                self.event("capture_finished",sha256=capture.sha256,plate_index=capture.plate_index)
        except Exception as exc:
            with self.lock:
                if success and self.host and self._slice_gui and self._audit_access_pending(exc):
                    source=Path(path).resolve(strict=True)
                    info=source.stat()
                    self._capture_access_pending={"model_id":model_id,"path":str(source),
                        "fingerprint":(info.st_size,info.st_mtime_ns,info.st_ino),
                        "expires":time.monotonic()+180,"retry_after":time.monotonic()+3,"completed":False}
                    self._message="Confirme no Orca a leitura do G-code para concluir a captura."
                    self.event("capture_access_pending",model_id=model_id,path=str(source))
                    return
                self._status="error"
                self._message=str(exc)
                self.event("capture_failed",error=str(exc))

    def slicing_completed(self, model_id: str, success: bool) -> None:
        # Plater::priv::on_process_completed is a wx UI event. Do not read GUI
        # objects on the layer/export worker or compare raw GUI settings to engine outputs.
        with self.lock:
            if not success:
                self.invalidate("O fatiamento falhou ou foi cancelado.")
                return
            if self._slice_gui is None:
                return
            pending=self._capture_access_pending
            if pending:
                if pending["model_id"]!=model_id:
                    self.invalidate("A conclusão não pertence à captura que aguarda acesso.")
                else:
                    pending["completed"]=True
                return
            try:
                snapshot=self.host.snapshot()
                capture=self.captures.confirm_gui(model_id,snapshot)
            except Exception as exc:
                self.invalidate(str(exc))
                return
            self.snapshot=snapshot
            self._slice_gui=None
            self._gui_armed=True
            self._status="idle"
            self._message="Fatiamento capturado. Escolha as peças e gere o G-code com ondas."
            ctx=self._conformal_session
            if ctx and ctx["phase"]=="slicing" and ctx["bound_revision"]==snapshot.revision:
                if (Path(self.host.project_path()).resolve()!=Path(ctx["prepared_path"])
                        or set(capture.print_object_map.values())!={ctx["native_id"]}):
                    self.invalidate("A captura não corresponde à peça achatada preparada.")
                    return
                ctx.update(phase="captured",capture_id=capture.capture_id,capture_sha=capture.sha256)
                self._message="Fatiamento da cópia achatada confirmado. Gere o percurso conformal."
            self.event("capture_gui_verified",capture_id=capture.capture_id,
                       gui_revision=snapshot.revision,effective_revision=self._effective_revision)

    @staticmethod
    def _audit_access_pending(exc: Exception) -> bool:
        return 'without permission: audit permission required' in str(exc)

    def poll_capture_access(self, *, ui_focused: bool=False) -> None:
        with self.lock:
            pending=self._capture_access_pending
            if pending is None:
                return
            if time.monotonic()>=pending["expires"]:
                self.invalidate("O acesso à captura não foi confirmado dentro de três minutos. Fatie novamente.")
                return
            if (not ui_focused or pending.get("checking") or not pending["completed"] or
                    time.monotonic()<pending["retry_after"]):
                return
            pending["checking"]=True
            try:
                if self.host.snapshot().revision!=self._slice_gui.revision:
                    raise StaleArtifactError("O projeto mudou enquanto a captura aguardava acesso.")
                info=Path(pending["path"]).stat()
                if (info.st_size,info.st_mtime_ns,info.st_ino)!=pending["fingerprint"]:
                    raise StaleArtifactError("O arquivo mudou enquanto a captura aguardava acesso.")
                capture=self.captures.finish(pending["model_id"],pending["path"],success=True)
                self._capture_access_pending=None
                self.event("capture_finished",sha256=capture.sha256,plate_index=capture.plate_index)
                self.slicing_completed(pending["model_id"],True)
            except Exception as exc:
                # One retry on the GUI thread can resume the asynchronous
                # worker prompt. A further denial must stop, not prompt in a loop.
                self.invalidate(str(exc))
            finally:
                pending["checking"]=False

    def prepare_conformal(self, selected: list[str], settings: dict) -> None:
        from .conformal_geometry import ConformalSettings, ConformalWarp
        if not self.host or len(selected)!=1:
            raise WaveError("Abra a peça original no Orca e escolha um objeto.")
        if set(settings)-{"step_mm","max_slope_deg","retain_native_short_edges","backend","region_id"}:
            raise WaveError("Parâmetro conformal desconhecido.")
        settings=dict(settings)
        backend=settings.pop('backend','legacy_top')
        region_id=settings.pop('region_id',None)
        if backend not in {'legacy_top','regional_paired'}:
            raise WaveError('Escolha um motor de superfície conhecido.')
        if backend=='regional_paired':
            from .regional_shell import RegionalShellSettings,RegionalShellWarp
            options=RegionalShellSettings(**settings)
        else:
            options=ConformalSettings(**settings,full_slope_deg=min(20.0,2*settings.get("max_slope_deg",30)/3))
        self.refresh()
        with self.lock:
            original=self.snapshot
            if self._conformal_session or self._preview_request:
                raise WaveError("Conclua o estudo atual ou reabra o projeto original antes de preparar outra cópia.")
            if (not original or len(original.objects)!=1 or str(original.objects[0]["id"])!=selected[0]
                    or len(original.objects[0]["instances_data"])!=1):
                raise WaveError("Prepare o estudo com uma única peça e uma instância na mesa.")
            job=uuid.uuid4().hex
            folder=self.storage/"models"/job
            backup=folder/"original.3mf"
            self.host.export_project(backup)
            self.invalidate("Preparando a cópia de estudo.")
            ctx={"phase":"preparing","original":original,"original_id":selected[0],"origin_backup":str(backup),
                 "origin":str(self.host.project_path() or ""),"prepared_path":str(folder/("flat-"+job[:10]+".3mf")),
                 "settings":{"step_mm":options.step_mm,"max_slope_deg":options.max_slope_deg,
                             "retain_native_short_edges":options.retain_native_short_edges,
                             "backend":backend,"region_id":region_id}}
            self._conformal_session=ctx
            self._job=job
            self._status="processing"
            self._message="Preparando a malha achatada. Uma cópia do projeto original foi salva."
        def work():
            try:
                if backend=='regional_paired':
                    from .roof_regions import roof_region_catalog,selected_region
                    catalog=roof_region_catalog(original,selected[0])
                    with self.lock:
                        if self._conformal_session is ctx:
                            ctx['region_catalog']=catalog
                    region=selected_region(catalog,region_id)
                    warp=RegionalShellWarp(original,selected[0],options,region)
                else:
                    warp=ConformalWarp(original,selected[0],options)
                expected=PreparedMesh(warp.flattened_snapshot)
                path=Path(ctx["prepared_path"])
                write_model_project(warp.flattened_snapshot,path,exported_settings(backup,regional=backend=='regional_paired'))
                artifact=digest(path.read_bytes())
                with self.lock:
                    if self._conformal_session is not ctx or self._job!=job:
                        return
                    ctx.update(warp=warp,expected=expected,artifact=artifact,phase="needs_open",
                               region_catalog=catalog if backend=='regional_paired' else None)
                    self.event("flat_model_prepared",sha256=artifact,geometry=expected.sha256,
                               original_revision=original.revision,backup=str(backup))
            except Exception as exc:
                self._conformal_failed(ctx,exc)
        threading.Thread(target=work,name="OrcaWave-PrepareModel",daemon=True).start()

    def _conformal_failed(self, ctx: dict, error: Exception) -> None:
        with self.lock:
            if self._conformal_session is ctx:
                self.invalidate(str(error))
                self._status="error"
                if ctx['settings'].get('backend')=='regional_paired':
                    detail=re.sub(r'^REGIONAL_[A-Z_]+(?: \[[^\]]+\])?:\s*','',str(error))
                    self._surface_rejection={'revision':ctx['original'].revision,
                        'object_id':ctx['original_id'],'regions':['top','underside','border'],
                        'region_catalog':ctx.get('region_catalog'),'detail':str(error),
                        'digital_approval':False,'print_allowed':False}
                    self._message='Não foi possível preparar toda a região: '+detail+' O original foi preservado.'
                self.event("flat_model_failed",reason=str(error))

    def poll_prepared(self) -> None:
        with self.lock:
            ctx=self._conformal_session
            if not ctx:
                return
            if ctx["phase"]=="opening":
                if time.monotonic()>=ctx["expires"]:
                    self._conformal_failed(ctx,WaveError("A abertura da cópia achatada foi cancelada ou expirou."))
                    return
                self.prepared_project_opened("")
                return
            if ctx["phase"]!="needs_open":
                return
            try:
                if (self.host.snapshot().revision!=ctx["original"].revision or
                        str(self.host.project_path() or "")!=ctx["origin"]):
                    raise StaleArtifactError("O projeto original mudou durante a preparação.")
                path=Path(ctx["prepared_path"])
                if digest(path.read_bytes())!=ctx["artifact"]:
                    raise StaleArtifactError("O arquivo de estudo preparado foi alterado.")
                ctx.update(phase="opening",expires=time.monotonic()+180,sending=True,closed=False)
            except Exception as exc:
                self._conformal_failed(ctx,exc)
                return
        try:
            self.host.open_model(path)
        except Exception as exc:
            self._conformal_failed(ctx,exc)
        finally:
            with self.lock:
                ctx["sending"]=False

    def prepared_transition(self, name: str, event) -> bool:
        with self.lock:
            ctx=self._conformal_session
            if not ctx or ctx["phase"]!="opening" or time.monotonic()>=ctx["expires"]:
                return False
            subject=str(getattr(event,"name","") or "")
            if name=="PresetSelected":
                return ctx["sending"] or subject.casefold().endswith("("+Path(ctx["prepared_path"]).name.casefold()+")")
            if name=="ProjectClosed" and not ctx["closed"]:
                origin=Path(ctx["origin"]).resolve() if ctx["origin"] else None
                from_origin=origin and subject and Path(subject).resolve() in {origin,origin.with_suffix("")}
                if not from_origin and subject and not ctx["sending"]:
                    # Save As from Orca's unsaved-changes prompt can give the original
                    # a new name between dispatching the open and its close event.
                    saved=self.host.project_path()
                    if saved and Path(subject).resolve() in {Path(saved).resolve(),Path(saved).resolve().with_suffix("")}:
                        active=self.host.snapshot()
                        original=ctx["original"]
                        from_origin=(active.session_id==original.session_id and
                                     active.plate_index==original.plate_index and active.objects==original.objects)
                if ctx["sending"] or from_origin or (not origin and not subject):
                    ctx["closed"]=True
                    return True
            # Resets during import stage no capture. The actual path, copied file
            # digest and complete oriented mesh must still verify before arming.
            return (ctx["sending"] or ctx["closed"]) and name in {
                "NewProject","ObjectAdded","ObjectDeleted","PlateCreated","PlateDeleted","PlateSelected"}

    def prepared_project_opened(self, announced_path: str) -> bool:
        with self.lock:
            ctx=self._conformal_session
            if not ctx:
                return False
            path=Path(ctx["prepared_path"])
            if announced_path and Path(announced_path).resolve() not in {path,path.with_suffix("")}:
                return False
            if ctx["phase"] not in {"opening","checking"}:
                if announced_path and ctx["phase"]=="awaiting_slice" and self.host.project_path():
                    return (Path(self.host.project_path()).resolve()==path
                            and self.host.snapshot().revision==ctx["bound_revision"])
                return False
            actual=self.host.project_path()
            if not actual or Path(actual).resolve()!=path:
                return bool(announced_path)
            if ctx["phase"]=="checking":
                return True
            if not self.host.capture_ready():
                # The project path may be assigned before Orca has applied its
                # embedded process profile. Do not arm or start the geometry check yet.
                self._message="Aguardando a aplicação do perfil com identificação das peças e captura."
                return True
            snapshot=self.host.snapshot()
            ctx["phase"]="checking"
        def work():
            try:
                if (digest(path.read_bytes())!=ctx["artifact"] or snapshot.plate_index!=0 or
                        not ctx["expected"].matches(snapshot)):
                    raise StaleArtifactError("A malha aberta, sua posição ou a placa diverge da cópia achatada.")
                critical=("nozzle_diameter","layer_height","initial_layer_print_height","printer_model",
                          "gcode_flavor","filament_diameter")
                if any(snapshot.settings.get(k)!=ctx["original"].settings.get(k) for k in critical):
                    raise StaleArtifactError("O perfil, bico ou altura de camada da cópia diverge do projeto original.")
                objects=analyze_snapshot(snapshot)
                revision=snapshot.revision
                with self.lock:
                    if self._conformal_session is not ctx or ctx["phase"]!="checking":
                        return
                    self.snapshot=snapshot
                    self._analysis_job=None
                    self._gui_armed=True
                    self._objects=objects
                    self._job=None
                    ctx.update(phase="awaiting_slice",native_id=str(snapshot.objects[0]["id"]),bound_revision=revision)
                    self._status="slicing_required"
                    self._message="Cópia achatada verificada. Clique em Fatiar no Orca."
                    self.event("flat_model_bound",revision=revision,native_id=ctx["native_id"],
                               original_id=ctx["original_id"],geometry=ctx["expected"].sha256)
            except Exception as exc:
                self._conformal_failed(ctx,exc)
        threading.Thread(target=work,name="OrcaWave-VerifyModel",daemon=True).start()
        return True

    def generate(self, selected: list[str], raw_parameters: dict, per_object: dict | None=None, *, conformal=False) -> None:
        if self.host:
            self.refresh()
        if self.snapshot is None:
            raise WaveError("Não há projeto acompanhado.")
        if not selected:
            raise WaveError("Escolha ao menos uma peça.")
        keys={field.name for field in fields(WaveParameters)}
        if set(raw_parameters).difference(keys):
            raise WaveError("A configuração contém parâmetros desconhecidos.")
        raw_parameters={**raw_parameters,"bench_only":True}
        common=WaveParameters(**raw_parameters)
        with self.lock:
            snapshot=self.snapshot
            capture=self.captures.current(snapshot)
            effective_revision=self._effective_revision
            ctx=self._conformal_session
            if ctx and not conformal:
                raise WaveError("A cópia achatada deve ser processada com a transformação conformal.")
            if conformal and (not ctx or ctx["phase"] not in {"captured","ready"} or selected!=[ctx["native_id"]]
                or ctx["bound_revision"]!=snapshot.revision or capture.capture_id!=ctx["capture_id"]
                or capture.sha256!=ctx["capture_sha"] or set(capture.print_object_map.values())!={ctx["native_id"]}
                or Path(self.host.project_path()).resolve()!=Path(ctx["prepared_path"])):
                raise StaleArtifactError("O fatiamento atual não está vinculado à cópia achatada verificada.")
            if not set(selected).issubset(set(capture.print_object_map.values())):
                raise WaveError("A seleção inclui peças sem trajetória identificada nesta mesa.")
            overrides=per_object or {}
            if not isinstance(overrides,dict) or not set(overrides).issubset(set(selected)):
                raise WaveError("Os parâmetros individuais não correspondem à seleção.")
            params={str(key):WaveParameters(**{**common.to_dict(),**overrides.get(str(key),{}),"bench_only":True})
                    for key in selected}
            project_path=self.storage/"captures"/(capture.capture_id+".3mf")
            if self.host:
                self.host.export_project(project_path)
            job=uuid.uuid4().hex
            self._job=job
            self._result=None
            self._preview_verified=False
            self._parameters={key:value.to_dict() for key,value in params.items()}
            params_snapshot={key:value.to_dict() for key,value in params.items()}
            self._status="processing"
            if conformal:
                ctx["phase"]="generating"
            self._message="Calculando as trajetórias e preparando o Preview…"

        def work():
            try:
                source=Path(capture.copy_path).read_bytes()
                if digest(source)!=capture.sha256:
                    raise StaleArtifactError("A captura foi alterada.")
                if conformal:
                    from .conformal import process_conformal_gcode
                    mapped={key:ctx["original_id"] for key in capture.print_object_map}
                    result=process_conformal_gcode(source,ctx["warp"],mapped,ctx["original_id"])
                else:
                    result=process_gcode(source,params,capture.print_object_map)
                # A unique job owns its output, including stale workers. Keep paths
                # short enough for Orca's Windows build without long-path support.
                output=self.storage/"results"/job
                stem="surface-part" if conformal else "waves"
                gcode_path=output/(stem+".gcode")
                package_path=output/(stem+".gcode.3mf")
                atomic_write(gcode_path,result.gcode)
                package_info=build_sliced_package(result.gcode,package_path,
                    project_3mf=project_path if project_path.is_file() else None,
                    plate_index=capture.plate_index,metadata={"bench_only":True})
                if digest(extract_plate_gcode(package_path,capture.plate_index))!=result.sha256:
                    raise WaveError("O pacote não preservou a trajetória gerada.")
                report={**result.report,"package":package_info,"capture_sha256":capture.sha256,
                        "effective_snapshot_revision":effective_revision,
                        "snapshot_revision":snapshot.revision,"parameters":params_snapshot,
                        "native_preview_validated":False,"physical_validation":False}
                if conformal:
                    if ctx['settings'].get('backend')=='regional_paired':
                        from .roof_audit import audit_regional_roof
                        report['regional_audit']=audit_regional_roof(result.gcode,ctx['warp'],mapped,ctx['original_id'])
                    report.update(print_allowed=False,profile_preview_only=True,prepared_geometry_sha256=ctx["expected"].sha256,
                        original_object_id=ctx["original_id"],prepared_object_id=ctx["native_id"],
                        prepared_print_object_map=capture.print_object_map,original_revision=ctx["original"].revision,
                        prepared_model_sha256=ctx["artifact"],conformal_settings=ctx["settings"],
                        warp=getattr(ctx["warp"],"summary",{}),
                        preview_profile_overrides={"detect_narrow_internal_solid_infill":"0","zaa_enabled":"0"})
                atomic_write(output/"report.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
                with self.lock:
                    if self._job!=job or self.snapshot is None or self.snapshot.revision!=snapshot.revision:
                        return
                    self._result={"sha256":result.sha256,"package_path":str(package_path),
                        "gcode_path":str(gcode_path),"report":report,"plate_index":capture.plate_index,
                        "original_points":report.get("original_points",[]),
                        "deformed_points":report.get("deformed_points",[]),
                        "layer_ids":report.get("layer_ids",[]),"break_indices":report.get("break_indices",[])}
                    if conformal:
                        ctx["phase"]="ready"
                        self._result.update(study_kind="conformal",object_id=ctx["native_id"],settings=ctx["settings"],
                                            revision=snapshot.revision)
                    self._status="ready"
                    self._message="Trajetória de bancada gerada. Abrindo a prévia nativa…" if self.host else "Trajetória de bancada gerada."
                    self._pending_open=bool(self.host)
                    self.event("generated",sha256=result.sha256,plate_index=capture.plate_index)
            except Exception as exc:
                with self.lock:
                    if self._job==job:
                        if conformal and self._conformal_session is ctx:
                            ctx["phase"]="captured"
                        self._status="error"
                        self._message=str(exc)
                        self.event("generation_failed",error=str(exc))
        threading.Thread(target=work,name="OrcaWave-Generate",daemon=True).start()

    def surface_study(self, selected: list[str], settings: dict) -> None:
        from .surface import SurfaceSettings, build_surface_study
        if self.host:
            self.refresh()
        if self.snapshot is None or len(selected)!=1:
            raise WaveError("Escolha uma peça para estudar sua superfície superior.")
        options=SurfaceSettings(**settings)
        with self.lock:
            snapshot=self.snapshot
            if selected[0] not in {str(obj['id']) for obj in snapshot.objects}:
                raise WaveError("A peça não pertence à mesa atual.")
            job=uuid.uuid4().hex
            self._job=job
            self._result=None
            self._preview_verified=False
            self._preview_request=None
            self._pending_open=False
            self._opening_preview=False
            self._status="processing"
            self._message="Calculando o percurso sobre a superfície da peça…"
        def work():
            try:
                result=build_surface_study(snapshot,selected[0],options)
                output=self.storage/"results"/job
                path=output/"surface-study.gcode"
                report={**result.report,"snapshot_revision":snapshot.revision,
                        "print_allowed":False,"physical_validation":False}
                atomic_write(path,result.gcode)
                atomic_write(output/"report.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
                with self.lock:
                    if self._job!=job or self.snapshot is None or self.snapshot.revision!=snapshot.revision:
                        return
                    self._result={"sha256":result.sha256,"gcode_path":str(path),"report":report,
                        "study_kind":"surface","object_id":selected[0],"settings":asdict(options),
                        "revision":snapshot.revision,"plate_index":snapshot.plate_index,
                        **{key:report.get(key,[]) for key in
                           ("original_points","deformed_points","layer_ids","break_indices")}}
                    self._status="ready"
                    self._message="Percurso da superfície no Studio. Deposição e impressão ainda não validadas."
                    self.event("surface_study_generated",sha256=result.sha256,object_id=selected[0],print_allowed=False)
            except Exception as exc:
                with self.lock:
                    if self._job==job:
                        self._status="error"
                        self._message=str(exc)
                        self.event("surface_study_failed",error=str(exc))
        threading.Thread(target=work,name="OrcaWave-Surface",daemon=True).start()

    def open_preview(self) -> None:
        if self.host is None:
            raise WaveError("A abertura nativa só está disponível dentro do Orca.")
        with self.lock:
            if not self._result:
                raise WaveError("Gere a trajetória antes de abrir o Preview.")
            if self._result.get("study_kind")=="surface":
                raise WaveError("O estudo de superfície é visualizado no Studio; não contém deposição imprimível.")
            path=Path(self._result["package_path"])
            data=extract_plate_gcode(path,self._result["plate_index"])
            if digest(data)!=self._result["sha256"]:
                self.invalidate("O pacote mudou após a geração.")
                raise WaveError("O pacote mudou após a geração.")
            origin=self.host.project_path()
            self._pending_open=False
            self._opening_preview=True
            self._importing_preview=True
            self._preview_verified=False
            self._preview_request={"origin":str(Path(origin).resolve()) if origin else "",
                "package":str(path.resolve()),"plate":self._result["plate_index"],"sha256":digest(data),
                "expires":time.monotonic()+180,"closed":False,"parsed":False,"completed":False,
                "model_id":None,"cache":None}
        try:
            self.host.open_preview(path)
            self.event("preview_requested",sha256=digest(data))
        except Exception:
            self._opening_preview=False
            self._preview_request=None
            raise
        finally:
            with self.lock:
                self._importing_preview=False

    def preview_transition(self, name: str, ctx) -> bool:
        """Only recognize reset of the known origin or a preset named by this import."""
        with self.lock:
            request=self._preview_request
            if not request or time.monotonic()>=request["expires"] or request["parsed"]:
                return False
            subject=str(getattr(ctx,"name","") or "")
            if name=="ProjectClosed" and not request["closed"]:
                origin=Path(request["origin"]) if request["origin"] else None
                # Orca's event omits the extension, while project_path() supplies .3mf.
                if origin is not None and subject and Path(subject).resolve() in {origin,origin.with_suffix("")}:
                    request["closed"]=True
                    return True
            if name=="PresetSelected":
                return (self._importing_preview or
                        subject.casefold().endswith("("+Path(request["package"]).name.casefold()+")"))
            return self._importing_preview and name in {"ProjectClosed","NewProject","ObjectDeleted",
                                                      "PlateDeleted","PlateCreated","PlateSelected"}

    def preview_cache_event(self, start: bool, model_id: str, path: str, success: bool) -> None:
        with self.lock:
            request=self._preview_request
            if request is None:
                return
            try:
                if not success or time.monotonic()>=request["expires"]:
                    raise WaveError("A importação de Preview falhou, foi cancelada ou expirou.")
                cache=Path(path).resolve(strict=True)
                if not self.host.validate_preview_source(cache,request["plate"]):
                    raise WaveError("O caminho analisado não identifica o cache da placa neste processo Orca.")
                if start:
                    if request["cache"] or not model_id:
                        raise WaveError("Início duplicado ou sem modelo no carregamento do Preview.")
                    request.update(cache=str(cache),model_id=model_id)
                    self.event("preview_parse_started",path=str(cache),model_id=model_id)
                else:
                    if (str(cache)!=request["cache"] or model_id!=request["model_id"] or request["parsed"]
                            or not cache.is_file() or cache.stat().st_size>512*1024*1024):
                        raise WaveError("O fim da análise do Preview não corresponde ao início acompanhado.")
                    if digest(cache.read_bytes())!=request["sha256"]:
                        raise WaveError("O G-code analisado pelo Orca difere da trajetória gerada.")
                    request["parsed"]=True
                    self.event("preview_parse_finished",model_id=model_id,sha256=request["sha256"])
            except Exception as exc:
                if not start and self._wait_for_preview_access(exc):
                    request["read_pending"]=True
                else:
                    self.invalidate(str(exc))

    def _wait_for_preview_access(self, exc: Exception) -> bool:
        # Orca asks the user asynchronously, then raises from the audited open.
        # Keep the same import identity; never approve or widen its permissions.
        if (self._preview_request is None or
                not self._audit_access_pending(exc)):
            return False
        request=self._preview_request
        if request.get("waiting_access"):
            return False
        request["retry_after"]=time.monotonic()+3
        if not request.get("waiting_access"):
            self.event("preview_access_pending",path=request.get("cache"))
        request["waiting_access"]=True
        self._message="Preview aberto. Confirme no Orca a leitura do arquivo para concluir a verificação."
        return True

    def preview_completed(self, model_id: str, success: bool) -> None:
        with self.lock:
            request=self._preview_request
            if request is None:
                return
            if (not success or model_id!=request["model_id"] or
                    not (request["parsed"] or request.get("read_pending"))):
                self.invalidate("A tarefa de Preview não confirmou o mesmo G-code e modelo.")
                return
            request["completed"]=True
            self.event("preview_job_completed",model_id=model_id)
            self.verify_preview(self.host.project_path())

    def verify_preview(self, path: str, *, resume_access: bool=False) -> bool:
        with self.lock:
            if self._result is None:
                return False
            result=self._result
            expected=Path(self._result["package_path"]).resolve()
            request=self._preview_request
            if request is None:
                return self._preview_verified and bool(path) and Path(path).resolve()==expected
            if time.monotonic()>=request["expires"]:
                self.invalidate("O Orca não confirmou a abertura e análise do pacote dentro de três minutos.")
                return False
            if not request["completed"] or not path or Path(path).resolve()!=expected:
                return False
            if time.monotonic()<request.get("retry_after",0):
                return False
            if request.get("waiting_access") and not resume_access:
                return False
            if request.get("checking"):
                return False
            receipt={"model_id":request["model_id"],"plate_index":request["plate"],
                "cache_path":request["cache"],"sha256":request["sha256"],"package_path":str(expected)}
            request["checking"]=True
            try:
                data=extract_plate_gcode(expected,self._result["plate_index"])
                cache=Path(request["cache"]).resolve(strict=True)
                if (digest(data)!=request["sha256"] or not self.host.validate_preview_source(cache,request["plate"])
                        or cache.stat().st_size!=len(data) or digest(cache.read_bytes())!=request["sha256"]):
                    raise WaveError("O pacote ou o cache do Preview mudou após a análise.")
                if self._preview_request is not request or self._result is not result:
                    return False
                atomic_write(expected.with_name("preview-receipt.json"),json.dumps(receipt,
                             ensure_ascii=False,indent=2).encode("utf-8"))
            except Exception as exc:
                if self._preview_request is not request or self._result is not result:
                    return False
                if self._wait_for_preview_access(exc):
                    return False
                self.invalidate(str(exc))
                return False
            finally:
                request["checking"]=False
            if request.get("read_pending"):
                request["parsed"]=True
                self.event("preview_parse_finished",model_id=request["model_id"],sha256=request["sha256"])
            self._preview_verified=True
            self._opening_preview=False
            self._preview_request=None
            self._result["native_preview"]=receipt
            self._message="Preview do Orca confirmado com o mesmo G-code. Somente simulação."
            self.event("preview_package_verified",sha256=digest(data),valid=self._preview_verified)
            return self._preview_verified

    def agent_context(self) -> dict:
        settings={}
        try:
            settings=json.loads((self.storage/"study_connection.json").read_text(encoding="utf-8"))
        except (OSError,ValueError):
            pass
        with self.lock:
            return {"base_url":settings.get("base_url","http://127.0.0.1:18080"),
                    "api_key":settings.get("api_key","orca-wave-bench"),"bench_only":True,
                    "expected_sha256":self._result["sha256"] if self._result else "",
                    "plate_index":self._result["plate_index"] if self._result else 0,
                    "approval_current":bool(self._result and self._preview_verified
                        and self._result.get("report",{}).get("print_allowed",True))}

    def handle(self, message: Any) -> dict:
        try:
            payload=json.loads(message) if isinstance(message,str) else message
            if not isinstance(payload,dict):
                raise WaveError("Mensagem inválida.")
            action=payload.get("action")
            selected=[str(x) for x in payload.get("object_ids",[])]
            if action=="refresh":
                self.refresh()
            elif action=="analyze":
                self.analyze(selected)
            elif action=="prepare_capture":
                if not self.host:
                    raise WaveError("Prepare a captura dentro do Orca.")
                self.host.prepare_capture()
                self._message="Captura preparada. Clique em Fatiar no Orca."
            elif action=="prepare_vase":
                if not self.host:
                    raise WaveError("Prepare o vaso dentro do Orca.")
                self.refresh()
                if (self.snapshot is None or len(self.snapshot.objects)!=1
                        or selected!=[str(self.snapshot.objects[0]["id"])]):
                    with self.lock:
                        self._analysis_job=None
                    raise WaveError("Para preparar o vaso, deixe somente a peça selecionada na placa.")
                backup=self.storage/"backups"/("before-vase-"+uuid.uuid4().hex[:12]+".3mf")
                self.host.export_project(backup)
                self.invalidate("Preparando parede única e base do vaso…")
                self.host.prepare_vase()
                self.refresh()
                self._message="Vaso preparado com base, uma parede e topo aberto. Clique em Fatiar no Orca e depois Gerar e abrir Preview."
                self.event("vase_prepared",original_backup=str(backup))
            elif action=="generate":
                self.generate(selected,payload.get("parameters",{}),payload.get("parameters_by_object"))
            elif action=="prepare_conformal":
                self.prepare_conformal(selected,payload.get("settings",{}))
            elif action=="generate_conformal":
                self.generate(selected,{},conformal=True)
            elif action=="surface_study":
                if self._conformal_session:
                    raise WaveError("Abra o projeto original para estudar sua superfície.")
                self.surface_study(selected,payload.get("settings",{}))
            elif action=="open_preview":
                if not self._opening_preview:
                    self.open_preview()
            elif action in {"open_panel","hide_panel"}:
                if self.host is None:
                    raise WaveError("O painel só está disponível dentro do Orca.")
                getattr(self.host,action)()
            elif action=="poll":
                if self._capture_access_pending:
                    self.poll_capture_access(ui_focused=payload.get("ui_focused") is True)
                elif self._pending_open:
                    self.open_preview()
                elif self._opening_preview and self.host:
                    self.verify_preview(self.host.project_path(),resume_access=payload.get("ui_focused") is True)
                elif self._conformal_session:
                    self.poll_prepared()
            elif action in {"save_preset","delete_preset"}:
                user=[x for x in self._presets() if str(x["id"]).startswith("user-")]
                preset_id=str(payload.get("id","user-"+uuid.uuid4().hex))
                if action=="delete_preset":
                    user=[x for x in user if x["id"]!=preset_id]
                else:
                    name=str(payload.get("name","Meu preset")).strip()[:80]
                    parameters=WaveParameters(**payload.get("parameters",{})).to_dict()
                    existing=next((item for item in user if item["id"]==preset_id),None)
                    if existing is not None:
                        existing.update({"name":name,"parameters":parameters})
                    else:
                        user.append({"id":"user-"+uuid.uuid4().hex,"name":name,"parameters":parameters})
                atomic_write(self.storage/"presets.json",json.dumps(user,ensure_ascii=False,indent=2).encode())
            else:
                raise WaveError("Ação desconhecida.")
        except Exception as exc:
            with self.lock:
                self._status="error"
                self._message=str(exc)
                self.event("action_failed",action=str(message.get("action")) if isinstance(message,dict) else "message",error=str(exc))
        return {"type":"state","state":self.state()}
