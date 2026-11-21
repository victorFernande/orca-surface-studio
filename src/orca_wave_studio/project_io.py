"""Independent model project for reproducible, isolated native slicing."""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .contracts import ProjectSnapshot, WaveError
from .geometry import transform_point


def write_model_project(snapshot:ProjectSnapshot, path:Path, settings:dict) -> None:
    """Copy printable mesh instances into world coordinates without touching the host."""
    ns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("",ns)
    def sub(parent,tag,**attrs):
        return ET.SubElement(parent,"{"+ns+"}"+tag,attrs)
    model=ET.Element("{"+ns+"}model",unit="millimeter")
    sub(model,"metadata",name="Application").text="OrcaSlicer-2.5.1"
    sub(model,"metadata",name="BambuStudio:3mfVersion").text="1"
    resources=sub(model,"resources")
    build=sub(model,"build")
    config=ET.Element("config")
    plate=ET.SubElement(config,"plate")
    ET.SubElement(plate,"metadata",key="plater_id",value="1")
    count=0
    for obj in snapshot.objects:
        for instance in obj["instances_data"]:
            if not instance.get("printable",True):
                continue
            vertices=[]
            triangles=[]
            for volume in obj["volumes"]:
                if volume.get("negative") or volume["kind"]!="part":
                    raise WaveError("A cópia de estudo requer volumes sólidos sem modificadores.")
                offset=len(vertices)
                vertices.extend(transform_point(p,instance["matrix"],volume["matrix"])
                                for p in volume["vertices"])
                triangles.extend(tuple(i+offset for i in tri) for tri in volume["triangles"])
            count+=1
            identifier=str(count)
            mesh=sub(sub(resources,"object",id=identifier,type="model"),"mesh")
            vs=sub(mesh,"vertices")
            for p in vertices:
                sub(vs,"vertex",**{axis:f"{value:.9f}" for axis,value in zip("xyz",p)})
            ts=sub(mesh,"triangles")
            for tri in triangles:
                sub(ts,"triangle",**{f"v{i+1}":str(v) for i,v in enumerate(tri)})
            sub(build,"item",objectid=identifier)
            item=ET.SubElement(config,"object",id=identifier)
            ET.SubElement(item,"metadata",key="name",value=obj["name"])
            for key,value in obj.get("config",{}).items():
                if key!="name":
                    ET.SubElement(item,"metadata",key=str(key),value=str(value))
            part=ET.SubElement(item,"part",id=identifier,subtype="normal_part")
            ET.SubElement(part,"metadata",key="name",value=obj["name"])
            link=ET.SubElement(plate,"model_instance")
            for key,value in (("object_id",identifier),("instance_id","0"),("identify_id",str(count-1))):
                ET.SubElement(link,"metadata",key=key,value=value)
    if not count:
        raise WaveError("A cópia não contém peças imprimíveis.")
    ET.SubElement(config,"assemble")
    rels=b'''<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    types=b'''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(path,"w",ZIP_DEFLATED) as archive:
        entries={"3D/3dmodel.model":ET.tostring(model,encoding="utf-8",xml_declaration=True),
            "Metadata/model_settings.config":ET.tostring(config,encoding="utf-8",xml_declaration=True),
            "Metadata/project_settings.config":json.dumps(settings,ensure_ascii=False).encode(),
            "_rels/.rels":rels,"[Content_Types].xml":types}
        for name,data in entries.items():
            info=ZipInfo(name,(2026,1,1,0,0,0))
            info.compress_type=ZIP_DEFLATED
            archive.writestr(info,data)
