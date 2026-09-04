# -*- coding: utf-8 -*-
"""Abaqus kernel bridge."""

from __future__ import print_function

import json
import os

from atd.converter import convert_file


def convert_inp(input_path, output_path, strict=False, d3plot_interval=0.0, config_path=''):
    """Convert an Abaqus INP and print a compact result to the CAE message area."""
    options = {
        'strict': bool(strict),
        'd3plot_interval': float(d3plot_interval or 0.0),
    }
    if config_path:
        with open(os.path.abspath(config_path), 'rb') as stream:
            raw = stream.read()
        if not isinstance(raw, str):
            raw = raw.decode('utf-8-sig')
        options.update(json.loads(raw))

    result = convert_file(input_path, output_path, options)
    print('ATD conversion complete')
    print('  LS-DYNA deck : %s' % result['output_path'])
    print('  Report       : %s' % result['report_path'])
    print('  ID map       : %s' % result['idmap_path'])
    print('  Diagnostics  : %d error(s), %d warning(s)' % (
        result['summary']['errors'], result['summary']['warnings']))
    return result
