from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

from .controller import StudioController
from .contracts import WaveError
from .geometry import freeze_model
from .native_bridge import open_in_current_orca
from .studio_ui import get_studio_html

try:
    import orca
except ImportError:
    orca=None


CAPTURE_NAME="Orca Wave Studio Capture"
ICON_SVG='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#15171b"/><path d="M5 32Q12 8 20 32T35 32T50 32T65 32" stroke="#00bfa5" stroke-width="5" fill="none"/></svg>'
_controller=None
_last_settings={}


def preview_cache_read_targets(environment=None) -> list[str]:
    """Declare a reviewable read-only cache tree without probing the filesystem.

    Orca itself prompts and persists this permission. Never edit its grants.
    Missing/ambiguous environment paths retain the per-file approval fallback.
    """
    env=os.environ if environment is None else environment
    configured=env.get('TEMP') or env.get('TMP') or env.get('TMPDIR')
    if not configured:return []
    root=Path(configured)
    if not root.is_absolute() or '..' in root.parts or '*' in str(root):return []
    return [str(root/'orcaslicer_model'/'*')]


def _storage() -> Path:
    if orca is not None:
        return Path(orca.host.plugin.storage())
    return Path(__file__).resolve().parent/"standalone-data"


def _settings(keys,getter) -> dict:
    forbidden=("password","apikey","api_key","token","access_code","print_host","printhost","certificate","ca_file")
    return {str(key):getter(key) for key in keys
            if not any(word in str(key).lower() for word in forbidden)}


def _config_settings(bundle: Any) -> dict:
    return _settings(bundle.full_config_keys(),bundle.full_config_value)


class NativeHost:
    def allowed_source_roots(self):
        # gettempdir() probes candidate folders by creating/deleting a random
        # file on its first call. In Orca that unrelated probe asks the user
        # for a new file permission. Use the Windows-provided path directly;
        # actual cache reads still go through host audit and validate_source.
        configured=os.environ.get("TEMP") or os.environ.get("TMP")
        temp=Path(configured) if configured else Path(tempfile.gettempdir())
        if not temp.is_absolute():
            raise WaveError("A pasta temporária do Orca precisa de um caminho absoluto.")
        return (_storage().resolve(),temp.resolve())

    def validate_source(self,path:Path,model_id:str):
        if any(any(word in part.casefold() for word in ("secret","cert","conf")) for part in path.parts):
            return False
        if path.parent.name!="Metadata" or "orcaslicer_model" not in path.parts:
            return False
        if re.fullmatch(r"\."+str(os.getpid())+r"\.\d+\.gcode",path.name) is None:
            return False
        # Imported projects can transfer a loader model's backup directory to the
        # live model. Its trailing ID is not the slicing snapshot's model ID.
        # CaptureStore binds the model and path to the matching start/end events.
        return re.fullmatch(r".+#"+str(os.getpid())+r"#\d+",path.parent.parent.name) is not None

    def validate_preview_source(self,path:Path,plate_index:int):
        if path.name!=f"plate_{plate_index+1}.gcode" or path.parent.name!="Metadata":
            return False
        if not re.fullmatch(r".+#"+str(os.getpid())+r"#\d+",path.parent.parent.name):
            return False
        cache_root=path.parent.parent.parent.parent
        return cache_root.name=="orcaslicer_model" and any(
            cache_root.is_relative_to(root) for root in self.allowed_source_roots())

    def snapshot(self):
        global _last_settings
        _last_settings=_config_settings(orca.host.preset_bundle())
        return freeze_model(orca.host.model(),_last_settings)

    def capture_ready(self):
        try:
            bundle=orca.host.preset_bundle()
            label=str(bundle.full_config_value("gcode_label_objects")).strip('"').lower() in {"1","true"}
            pipeline=str(bundle.full_config_value("slicing_pipeline_plugin"))
            return label and CAPTURE_NAME in pipeline
        except Exception:
            return False

    def prepare_capture(self):
        controller=get_controller()
        def work():
            try:
                editor=orca.host.preset.process
                transaction=editor.begin_update()
                transaction.set("gcode_label_objects","1")
                transaction.set("slicing_pipeline_plugin",CAPTURE_NAME)
                transaction.commit()
                controller.event("capture_prepared")
            except Exception as exc:
                with controller.lock:
                    controller._status="error"
                    controller._message="Não foi possível preparar a captura: "+str(exc)
                controller.event("capture_prepare_failed",error=str(exc))
        threading.Thread(target=work,name="OrcaWave-Preset",daemon=True).start()

    def export_project(self,path: Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        # Python's public binding returns None; C++ raises if the export fails.
        orca.host.plater().export_3mf_copy(str(path))
        if not path.is_file():
            raise WaveError("O Orca não gerou a cópia de configurações do projeto.")

    def prepare_vase(self):
        # Called by the Studio action on the host thread. This changes only
        # the active process; the controller first saves the original project.
        transaction=orca.host.preset.process.begin_update()
        for key,value in {
            "wall_loops":"1", "sparse_infill_density":"0%", "top_shell_layers":"0",
            "bottom_shell_layers":"3", "bottom_shell_thickness":"0",
            "spiral_mode":"0", "detect_overhang_wall":"0", "enable_arc_fitting":"0",
            "gcode_label_objects":"1", "slicing_pipeline_plugin":CAPTURE_NAME,
        }.items():
            transaction.set(key,value)
        transaction.commit()

    def open_preview(self,path: Path):
        open_in_current_orca(path)

    def slicer_executable(self):
        # Resolve the running host, not a hardcoded installation or printer.
        import sys
        if sys.platform=='win32':
            import ctypes
            path=ctypes.create_unicode_buffer(32768)
            if not ctypes.windll.kernel32.GetModuleFileNameW(None,path,len(path)):
                raise WaveError('Não foi possível localizar este OrcaSlicer.')
            return path.value
        return sys.executable

    def slicer_workspace(self):
        return _storage()/'native-slicer'

    def open_model(self,path: Path):
        open_in_current_orca(path,sliced_only=False)

    def project_path(self) -> str:
        return orca.host.plater().project_path()

    def open_panel(self):
        return WaveDock().execute()

    def hide_panel(self):
        if WaveDock.panel is not None and WaveDock.panel.is_open():
            WaveDock.panel.hide()
            WaveDock.visible=False


def get_controller() -> StudioController:
    global _controller
    if _controller is None:
        _controller=StudioController(_storage(),NativeHost() if orca else None)
    return _controller


def _status(status: str="success", message: str=""):
    if not orca:
        return {"status":status,"message":message}
    if status=="success":
        return orca.ExecutionResult.success(message)
    return orca.ExecutionResult.failure(orca.PluginResult.RecoverableError,message)


_PageBase=orca.pages.PagesPluginCapabilityBase if orca else object
_ScriptBase=orca.script.ScriptPluginCapabilityBase if orca else object
_PipelineBase=orca.slicing.SlicingPipelineCapabilityBase if orca else object


class WavePage(_PageBase):
    def get_name(self):
        return "Estúdio de Ondas Senoidais"

    def get_icon(self):
        path=_storage()/"wave-icon.svg"
        if not path.is_file():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(ICON_SVG,encoding="utf-8")
        return str(path)

    def get_ui(self):
        controller=get_controller()
        controller.event('page_ui_requested')
        try:
            controller.refresh()
        except Exception as exc:
            controller.event("initial_refresh_deferred",reason=str(exc))
        try:
            initial=controller.state()
            # Geometry arrives over the bridge after the document is ready.
            initial={**initial,'model_preview':None,'objects':[], 'result':None}
            html=get_studio_html(initial)
            controller.event('page_ui_built',bytes=len(html.encode()))
            return html
        except Exception as exc:
            controller.event('page_ui_failed',error=str(exc))
            return get_studio_html({'native':True,'status':'error','message':str(exc)})

    def on_message(self,data):
        self.post_message(get_controller().handle(data))


class WaveDock(_ScriptBase):
    panel=None
    visible=False

    def get_name(self):
        return "Orca Wave Studio • Painel"

    def execute(self):
        if WaveDock.panel is not None and WaveDock.panel.is_open():
            if WaveDock.visible:
                WaveDock.panel.hide()
                WaveDock.visible=False
                return _status(message="Painel ocultado; o ícone permanece disponível.")
            WaveDock.panel.show()
            WaveDock.visible=True
            return _status(message="Painel exibido.")
        def receive(data):
            if WaveDock.panel is not None:
                WaveDock.panel.post(get_controller().handle(data))
        def close():
            WaveDock.panel=None
            WaveDock.visible=False
        WaveDock.panel=orca.host.ui.create_dock_panel(get_studio_html(get_controller().state(),dock=True),
                    title="Orca Wave Studio",width=430,height=800,dock="right",on_message=receive,on_close=close)
        WaveDock.visible=True
        return _status(message="Painel aberto.")


class WaveCapturePipeline(_PipelineBase):
    def get_name(self):
        return CAPTURE_NAME

    def execute(self,ctx):
        if ctx.print is None or ctx.step!=orca.slicing.Step.psSkirtBrim:
            return _status()
        controller=get_controller()
        try:
            settings=_settings(ctx.print.config_keys(),ctx.print.config_value)
            snapshot=freeze_model(ctx.print.model(),settings)
            mapping={i:str(obj.model_object().id()) for i,obj in enumerate(ctx.print.objects())}
            controller.capture_begin(snapshot,mapping)
            return _status(message="Mapa das peças registrado.")
        except Exception as exc:
            controller.invalidate("A captura precisa de novo fatiamento completo: "+str(exc))
            return _status("error",str(exc))

    def on_lifecycle_event(self,event,ctx):
        controller=get_controller()
        name=getattr(event,"name",str(event).split(".")[-1])
        try:
            if controller._opening_preview:
                details={k:str(getattr(ctx,k,"") or "")[:512] for k in ("id","name","source","msg","index")}
                controller.event("preview_lifecycle",lifecycle=name,ctx=details)
            if name=="SliceStarted":
                controller.slice_started(str(ctx.id))
            elif name in {"GCodeExportStarted","GCodeExportFinished"}:
                start=name=="GCodeExportStarted"
                model_id,path=str(ctx.id),str(ctx.msg)
                ok=ctx.code==orca.LifecycleEvtCode.Ok
                if controller._opening_preview:
                    controller.preview_cache_event(start,model_id,path,ok)
                elif re.fullmatch(r"plate_\d+\.gcode",Path(path.splitlines()[0] if path else "").name):
                    # Imported plates are never original slicer exports.
                    return
                elif start:
                    controller.captures.export_started(model_id,path)
                else:
                    controller.capture_finished(model_id,path,ok)
            elif name=="ProjectOpened":
                if controller.prepared_project_opened(str(ctx.name or "")):
                    return
                if (controller._preview_request and ctx.name and
                        Path(str(ctx.name)).resolve()==Path(controller._preview_request["package"])):
                    controller.event("preview_project_opened",path=str(ctx.name))
                    return
                try:
                    path=orca.host.plater().project_path()
                    own=controller.verify_preview(path)
                except Exception:
                    own=False
                if not own:
                    controller.invalidate("Outro projeto foi aberto. Analise as peças e fatie a mesa.")
                    controller.refresh()
            elif name in {"ObjectAdded","ObjectDeleted","ObjectTransformed","ObjectChanged","ObjectRenamed",
                          "PlateCreated","PlateDeleted","PlateSelected","PresetSelected","PresetSaved",
                          "ProjectClosed","NewProject"}:
                if not controller.preview_transition(name,ctx) and not controller.prepared_transition(name,ctx):
                    controller.event("project_mutation",lifecycle=name,
                                     ctx={k:str(getattr(ctx,k,"") or "")[:512] for k in ("id","name","msg","source")})
                    controller.invalidate("O projeto mudou. Atualize a análise e fatie novamente.")
                    # Coalesce bursts while Orca is still applying a project or
                    # preset. Poll refreshes once on the GUI thread when focused.
                    controller._refresh_pending=True
                    controller._objects=[]
                    controller._model_preview=None
            elif name=="SlicingJobComplete":
                if controller._opening_preview:
                    controller.preview_completed(str(ctx.id),ctx.code==orca.LifecycleEvtCode.Ok)
                else:
                    controller.slicing_completed(str(ctx.id),ctx.code==orca.LifecycleEvtCode.Ok)
        except Exception as exc:
            controller.event("lifecycle_error",lifecycle=name,error=str(exc))


if orca is not None:
    from .native_agent import WaveOctoPrintAgent, configure_native_agent

    @orca.plugin
    class OrcaWaveStudioPlugin(orca.base):
        def register_capabilities(self):
            # Orca grants exact process commands only, during discovery. Keep
            # the executable/arguments stable and move job data under its own
            # private workspace; do not request a shell or arbitrary commands.
            import subprocess
            from .surface_workflow import slice_command
            executable=NativeHost().slicer_executable()
            commands=[subprocess.list2cmdline(slice_command(executable,native_local=local)) for local in (False,True)]
            orca.request_permissions(fs_read=preview_cache_read_targets(),
                                       threading=True,network=["http://127.0.0.1","http://[::1]"],
                                       process=commands)
            configure_native_agent(lambda:get_controller().agent_context())
            for capability in (WavePage,WaveDock,WaveCapturePipeline,WaveOctoPrintAgent):
                orca.register_capability(capability)
