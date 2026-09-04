# -*- coding: utf-8 -*-

import io
import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, 'abaqus_plugins')
if PLUGIN not in sys.path:
    sys.path.insert(0, PLUGIN)

from atd.converter import ConversionError, convert_file
from atd.diagnostics import Diagnostics
from atd.parser import AbaqusParser


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def test_comprehensive_deck(self):
        source = os.path.join(ROOT, 'examples', 'comprehensive.inp')
        target = os.path.join(self.temp.name, 'cube.k')
        result = convert_file(source, target, {'strict': False})

        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        self.assertIn('*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE', deck)
        self.assertIn('*MAT_ADD_EROSION', deck)
        self.assertIn('*CONTACT_AUTOMATIC_SINGLE_SURFACE_TITLE', deck)
        self.assertIn('*BOUNDARY_SPC_SET', deck)
        self.assertIn('*LOAD_NODE_SET', deck)
        self.assertIn('*LOAD_SEGMENT_SET', deck)
        self.assertIn('*ELEMENT_SOLID', deck)
        self.assertIn('1,10,0,0', deck)  # translated first node
        self.assertEqual(result['model']['nodes_written'], 8)
        self.assertEqual(result['model']['elements_written'], 1)

        with io.open(result['report_path'], encoding='utf-8') as stream:
            report = json.load(stream)
        self.assertEqual(report['summary']['errors'], 0)
        self.assertGreaterEqual(report['summary']['warnings'], 1)

    def test_include_and_generate(self):
        include = os.path.join(self.temp.name, 'mesh.inc')
        main = os.path.join(self.temp.name, 'main.inp')
        with io.open(include, 'w', encoding='utf-8') as stream:
            stream.write('*NODE\n1,0,0,0\n2,1,0,0\n*NSET,NSET=ENDS,GENERATE\n1,2,1\n')
        with io.open(main, 'w', encoding='utf-8') as stream:
            stream.write('*HEADING\ninclude test\n*INCLUDE, INPUT=mesh.inc\n')
        diagnostics = Diagnostics()
        blocks = AbaqusParser(diagnostics).parse(main)
        self.assertEqual([block.keyword for block in blocks], ['HEADING', 'NODE', 'NSET'])
        self.assertEqual(diagnostics.converted_keywords['INCLUDE'], 1)

    def test_implicit_and_nested_sets(self):
        source = os.path.join(self.temp.name, 'nested.inp')
        target = os.path.join(self.temp.name, 'nested.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*PART,NAME=P\n*NODE,NSET=BASE\n1,0,0,0\n2,1,0,0\n'
                '*NSET,NSET=ALLN\nBASE\n'
                '*ELEMENT,TYPE=T3D2,ELSET=E\n1,1,2\n'
                '*BEAM SECTION,ELSET=E,MATERIAL=M,SECTION=RECT\n1,1\n*END PART\n'
                '*MATERIAL,NAME=M\n*DENSITY\n1\n*ELASTIC\n100,0.3\n'
            )
        result = convert_file(source, target, {'strict': True})
        self.assertEqual(result['summary']['errors'], 0)
        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        self.assertIn('*SET_NODE_LIST_TITLE\nP.ALLN', deck)

    def test_strict_mode_writes_report_but_no_deck(self):
        source = os.path.join(self.temp.name, 'unsupported.inp')
        target = os.path.join(self.temp.name, 'unsupported.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write('*HEADING\nunsupported\n*ADAPTIVE MESH\n')
        with self.assertRaises(ConversionError):
            convert_file(source, target, {'strict': True})
        self.assertFalse(os.path.exists(target))
        self.assertTrue(os.path.exists(os.path.splitext(target)[0] + '.conversion.json'))

    def test_material_override_allows_user_material(self):
        source = os.path.join(self.temp.name, 'user.inp')
        target = os.path.join(self.temp.name, 'user.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*NODE\n1,0,0,0\n2,1,0,0\n*ELEMENT,TYPE=T3D2,ELSET=E\n1,1,2\n'
                '*BEAM SECTION,ELSET=E,MATERIAL=U,SECTION=RECT\n1,1\n'
                '*MATERIAL,NAME=U\n*USER MATERIAL\n1,2,3\n'
            )
        result = convert_file(source, target, {
            'strict': True,
            'material_overrides': {'U': {'cards': ['*MAT_ELASTIC', '1,1,100,0.3']}},
        })
        self.assertEqual(result['summary']['errors'], 0)

    def test_node_to_surface_contact_and_instance_rotation(self):
        source = os.path.join(self.temp.name, 'contact.inp')
        target = os.path.join(self.temp.name, 'contact.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*PART,NAME=P\n'
                '*NODE\n1,1,0,0\n2,2,0,0\n3,2,1,0\n4,1,1,0\n'
                '*ELEMENT,TYPE=S4R,ELSET=E\n1,1,2,3,4\n'
                '*NSET,NSET=N\n1,2\n'
                '*SURFACE,NAME=NS,TYPE=NODE\nN,\n'
                '*SURFACE,NAME=ES,TYPE=ELEMENT\nE,SPOS\n'
                '*SHELL SECTION,ELSET=E,MATERIAL=M\n0.1\n'
                '*END PART\n'
                '*MATERIAL,NAME=M\n*DENSITY\n1\n*ELASTIC\n100,0.3\n'
                '*ASSEMBLY\n*INSTANCE,NAME=I,PART=P\n10,0,0\n0,0,0,0,0,1,90\n'
                '*END INSTANCE\n*END ASSEMBLY\n'
                '*CONTACT PAIR\nNS,ES\n'
            )
        result = convert_file(source, target, {'strict': True})
        self.assertEqual(result['summary']['errors'], 0)
        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        self.assertIn('*CONTACT_AUTOMATIC_NODES_TO_SURFACE_TITLE', deck)
        self.assertIn('*SET_NODE_LIST_TITLE\n@SURFACE.NS', deck)
        # (1,0,0) is translated to (11,0,0), then rotated 90 degrees about Z.
        lines = deck.splitlines()
        first_node = lines[lines.index('*NODE') + 1].split(',')
        self.assertAlmostEqual(float(first_node[1]), 0.0, places=10)
        self.assertAlmostEqual(float(first_node[2]), 11.0, places=10)

    def test_static_step_emits_implicit_controls(self):
        source = os.path.join(self.temp.name, 'static.inp')
        target = os.path.join(self.temp.name, 'static.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*NODE\n1,0,0,0\n2,1,0,0\n*ELEMENT,TYPE=T3D2,ELSET=E\n1,1,2\n'
                '*BEAM SECTION,ELSET=E,MATERIAL=M,SECTION=RECT\n1,1\n'
                '*MATERIAL,NAME=M\n*DENSITY\n1\n*ELASTIC\n100,0.3\n'
                '*STEP\n*STATIC\n0.1,2.0\n*END STEP\n'
            )
        convert_file(source, target, {'strict': True})
        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        self.assertIn('*CONTROL_IMPLICIT_GENERAL', deck)
        self.assertIn('*CONTROL_IMPLICIT_SOLUTION', deck)
        self.assertIn('*CONTROL_TERMINATION\n2,', deck)

    def test_system_and_point_mass(self):
        source = os.path.join(self.temp.name, 'mass.inp')
        target = os.path.join(self.temp.name, 'mass.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*SYSTEM\n10,0,0,10,1,0,9,0,0\n'
                '*NODE\n1,2,3,0\n'
                '*ELEMENT,TYPE=MASS,ELSET=PM\n7,1\n'
                '*MASS,ELSET=PM\n4.5\n'
            )
        result = convert_file(source, target, {'strict': True})
        self.assertEqual(result['summary']['errors'], 0)
        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        lines = deck.splitlines()
        node = lines[lines.index('*NODE') + 1].split(',')
        self.assertAlmostEqual(float(node[1]), 7.0)
        self.assertAlmostEqual(float(node[2]), 2.0)
        self.assertIn('*ELEMENT_MASS\n1,1,4.5', deck)

    def test_johnson_cook_damage_and_eos(self):
        source = os.path.join(self.temp.name, 'jc.inp')
        target = os.path.join(self.temp.name, 'jc.k')
        with io.open(source, 'w', encoding='utf-8') as stream:
            stream.write(
                '*NODE\n1,0,0,0\n2,1,0,0\n3,0,1,0\n4,0,0,1\n'
                '*ELEMENT,TYPE=C3D4,ELSET=E\n1,1,2,3,4\n'
                '*SOLID SECTION,ELSET=E,MATERIAL=JC\n,\n'
                '*MATERIAL,NAME=JC\n*DENSITY\n7.8e-9\n'
                '*ELASTIC,TYPE=SHEAR\n80000\n'
                '*PLASTIC,HARDENING=JOHNSON COOK\n200,300,0.4,1.1,1500,20\n'
                '*RATE DEPENDENT,TYPE=JOHNSON COOK\n0.02,1.0\n'
                '*SPECIFIC HEAT\n450\n'
                '*DAMAGE INITIATION,CRITERION=JOHNSON COOK\n0.1,0.2,-0.3,0.01,1.2,1500,20,1\n'
                '*DAMAGE EVOLUTION,TYPE=DISPLACEMENT\n0.2\n'
                '*EOS,TYPE=USUP\n5000,1.5,0,0,2,0\n'
            )
        result = convert_file(source, target, {'strict': True})
        self.assertEqual(result['summary']['errors'], 0)
        with io.open(target, encoding='utf-8') as stream:
            deck = stream.read()
        self.assertIn('*MAT_JOHNSON_COOK_TITLE', deck)
        self.assertIn('200,300,0.4,0.02,1.1,1500,20,1', deck)
        self.assertIn('450,0,2,0,0.1,0.2,-0.3,0.01', deck)
        self.assertIn('*EOS_GRUNEISEN_TITLE', deck)


if __name__ == '__main__':
    unittest.main()
