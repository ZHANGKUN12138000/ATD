# -*- coding: utf-8 -*-
"""Public conversion API and sidecar report generation."""

from __future__ import print_function, unicode_literals

import io
import json
import os

from .diagnostics import Diagnostics
from .model import build_source_model, flatten_model
from .parser import AbaqusParser, ParseError
from .writer import LSDynaWriter


class ConversionError(Exception):
    pass


def _write_text(path, value):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(value)


def _safe_options(options):
    result = {}
    for key, value in options.items():
        try:
            json.dumps(value)
            result[key] = value
        except (TypeError, ValueError):
            result[key] = repr(value)
    return result


def convert_file(input_path, output_path, options=None):
    """Convert *input_path* and return paths plus a diagnostic summary.

    ``strict=True`` still writes the JSON report, but deliberately does not
    write a K file when any ERROR diagnostic exists.
    """
    options = dict(options or {})
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    if not output_path.lower().endswith(('.k', '.key')):
        output_path += '.k'
    stem = os.path.splitext(output_path)[0]
    report_path = stem + '.conversion.json'
    idmap_path = stem + '.idmap.csv'

    diagnostics = Diagnostics()
    try:
        blocks = AbaqusParser(diagnostics).parse(input_path)
    except ParseError as exc:
        diagnostics.error('PARSE_ERROR', str(exc))
        report = diagnostics.as_dict()
        report.update({'input_path': input_path, 'output_path': output_path})
        _write_text(report_path, json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        raise ConversionError(str(exc))

    source = build_source_model(blocks, diagnostics)
    flat = flatten_model(source, diagnostics)
    writer = LSDynaWriter(flat, diagnostics, options)
    deck = writer.build()

    report = diagnostics.as_dict()
    report.update({
        'tool': {'name': 'ATD', 'version': '1.0.0'},
        'input_path': input_path,
        'output_path': output_path,
        'idmap_path': idmap_path,
        'options': _safe_options(options),
        'model': {
            'source_blocks': len(blocks),
            'source_parts': max(0, len(source.parts) - 1),
            'instances': len(source.instances),
            'nodes_written': len(flat.nodes),
            'elements_read': len(flat.elements),
            'elements_written': sum(1 for element in flat.elements.values() if element.pid is not None),
            'materials': len(source.materials),
            'lsdyna_parts': len(writer.parts),
            'steps': len(source.steps),
        },
        'review_required': True,
        'review_note': (
            'Finite-element keyword conversion is not a proof of physical equivalence. '
            'Confirm units, element formulations, material calibration, failure, contact, '
            'loads, constraints, timestep and energy balance in LS-DYNA.'
        ),
    })
    _write_text(report_path, json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))

    if options.get('strict') and diagnostics.count('ERROR'):
        raise ConversionError(
            'Strict conversion stopped with %d error(s). See %s' % (
                diagnostics.count('ERROR'), report_path)
        )

    _write_text(output_path, deck)
    id_lines = ['entity,instance,abaqus_id,lsdyna_id']
    for values in writer.id_rows:
        id_lines.append(','.join(str(value) for value in values))
    _write_text(idmap_path, '\n'.join(id_lines) + '\n')

    return {
        'output_path': output_path,
        'report_path': report_path,
        'idmap_path': idmap_path,
        'summary': report['summary'],
        'model': report['model'],
    }
