from __future__ import annotations

import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from orca_wave_studio.fixtures import cylinder_mesh


def create() -> Path:
    folder=ROOT/"study"/"fixtures"
    settings=json.loads((folder/"sovol-bench-settings.json").read_text(encoding="utf-8"))
    connection=json.loads((ROOT/"study"/"isolated_profile"/"orca_plugins"/"plugin_data"/
                           "orca_wave_generator"/"study_connection.json").read_text(encoding="utf-8"))
    from orca_wave_studio.octoprint import OctoPrintTransport
    transport=OctoPrintTransport(connection["base_url"],connection["api_key"])
    if transport.status()["version"].get("wave_studio_simulator") is not True:
        raise ValueError("O projeto exige um receptor identificado de bancada.")
    settings.update({"slicing_pipeline_plugin":["Orca Wave Studio Capture"],"gcode_label_objects":"1",
                     "wall_loops":"1","top_shell_layers":"0","bottom_shell_layers":"3",
                     "sparse_infill_density":"0%","enable_arc_fitting":"0","seam_position":"aligned",
                     "seam_gap":"0%","top_shell_thickness":"0","bottom_shell_thickness":"0.6",
                     "post_process":[],"print_settings_id":"Orca Wave Bench 0.20",
                     "printer_settings_id":"Orca Wave Sovol SV06 Bench 0.4"})
    settings.update({"printer_agent":"orca_wave_octoprint","print_host":connection["base_url"],
                     "printhost_apikey":connection["api_key"]})
    settings.update({"machine_start_gcode":"G90\nG21\nM83\nG92 E0\n",
                     "machine_end_gcode":"M104 S0\nM140 S0\nM84\n",
                     "filament_start_gcode":["; Orca Wave study fixture"],
                     "filament_end_gcode":["; end study fixture"],
                     "before_layer_change_gcode":"","layer_change_gcode":"G92 E0\n",
                     "wipe":["0"],"retraction_length":["0"],"filament_retraction_length":["0"]})
    vertices,triangles=cylinder_mesh(radius=20,height=8,segments=320)
    ns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("",ns)
    def sub(parent,tag,**attrs):
        return ET.SubElement(parent,"{"+ns+"}"+tag,attrs)
    model=ET.Element("{"+ns+"}model",unit="millimeter")
    sub(model,"metadata",name="Application").text="OrcaSlicer-2.5.1"
    sub(model,"metadata",name="BambuStudio:3mfVersion").text="1"
    resources=sub(model,"resources")
    obj=sub(resources,"object",id="1",type="model")
    mesh=sub(obj,"mesh")
    vs=sub(mesh,"vertices")
    for point in vertices:
        sub(vs,"vertex",x=f"{point[0]:.7f}",y=f"{point[1]:.7f}",z=f"{point[2]:.7f}")
    ts=sub(mesh,"triangles")
    for a,b,c in triangles:
        sub(ts,"triangle",v1=str(a),v2=str(b),v3=str(c))
    sub(sub(model,"build"),"item",objectid="1",transform="1 0 0 0 1 0 0 0 1 110 110 0")
    config=b'''<?xml version="1.0"?><config><object id="1"><metadata key="name" value="Cilindro OWS - bancada"/><part id="1" subtype="normal_part"><metadata key="name" value="Cilindro OWS - bancada"/></part></object><plate><metadata key="plater_id" value="1"/><model_instance><metadata key="object_id" value="1"/><metadata key="instance_id" value="0"/><metadata key="identify_id" value="0"/></model_instance></plate><assemble/></config>'''
    rels=b'''<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    types=b'''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    path=folder/"cylinder-native-study.3mf"
    with ZipFile(path,"w",ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model",ET.tostring(model,encoding="utf-8",xml_declaration=True))
        archive.writestr("Metadata/model_settings.config",config)
        archive.writestr("Metadata/project_settings.config",json.dumps(settings))
        archive.writestr("_rels/.rels",rels)
        archive.writestr("[Content_Types].xml",types)
    return path


if __name__=="__main__":
    print(create())
