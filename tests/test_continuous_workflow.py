import shutil
import tempfile
import unittest
import numpy as np
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from orca_wave_studio.bending import BendingWarp
from orca_wave_studio.fixtures import cylinder_snapshot
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.surface_workflow import build_surface
from orca_wave_studio.package import extract_plate_gcode
from test_bending import roof_with_hole


class ContinuousWorkflowTests(unittest.TestCase):
    def test_planar_source_is_mapped_once_with_active_profile_and_explicit_preview_transfer(self):
        settings={**cylinder_snapshot().settings,'initial_layer_print_height':'.24',
                  'min_layer_height':['.07'],'max_layer_height':['.28']}
        snapshot=replace(roof_with_hole(),settings=settings)
        warp=BendingWarp(snapshot,'1',RegionalShellSettings(nominal_layer_height_mm=.12,retain_native_short_edges=True))
        warp.summary['mesh_normal_and_crease_error_budget_mm']=np.float64(.0099)
        lines=['G90','M83','; zaa_enabled = 0',';WIDTH:0.42','G0 X96 Y96 Z0.24 F1200']
        for i in range(75):
            z=.24+i*.12
            lines+=[';LAYER_CHANGE',f';Z:{z:.6f}',f';HEIGHT:{.24 if i==0 else .12}',
                    '; printing object roof id:0 copy 0',f'G0 X96 Y96 Z{z:.6f}',
                    ';TYPE:Outer wall','G1 X114 Y96 E0.02','G1 X114 Y114 E0.02',
                    'G1 X96 Y114 E0.02','G1 X96 Y96 E0.02',
                    '; stop printing object roof id:0 copy 0']
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);backup=root/'original.3mf';write_model_project(snapshot,backup,settings)
            def slicer(executable,model,folder,cancelled,*,workspace):
                with ZipFile(model) as archive:
                    doc=ET.fromstring(archive.read('Metadata/model_settings.config'))
                    for node in (doc.find('object'),doc.find('object/part')):
                        self.assertEqual(node.find("metadata[@key='zaa_enabled']").get('value'),'0')
                folder.mkdir();source=folder/'plate_1.gcode';source.write_text('\n'.join(lines)+'\n')
                package=folder/'source.gcode.3mf';shutil.copyfile(model,package)
                return source,package
            with patch('orca_wave_studio.continuous_workflow.ContinuousLayerWarp',return_value=warp) as factory:
                result=build_surface(snapshot,'1',backup,root/'job','unused',
                    {'backend':'continuous_layers','selection_mode':'all'},slicer=slicer)
            self.assertEqual(factory.call_args.args[2].tolerance_mm,.01)
            budget=result['report']['coordinate_error_budget_mm']
            self.assertLessEqual(budget['mesh']+budget['path_chords'],budget['total'])
            self.assertEqual(result['settings']['backend'],'continuous_layers')
            self.assertTrue(result['report']['native_contouring_disabled'])
            self.assertTrue(result['report']['finishing']['path_audit']['first_layer_preserved'])
            self.assertGreater(sum(result['report']['nonplanar_extrusion_segments_by_role'].values()),0)
            self.assertFalse(result['report']['print_allowed'])
            self.assertEqual(extract_plate_gcode(result['package_path'],0),Path(result['gcode_path']).read_bytes())
