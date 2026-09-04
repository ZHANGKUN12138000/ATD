# -*- coding: utf-8 -*-
"""Command-line entry point for the same core used by Abaqus/CAE."""

from __future__ import print_function

import argparse
import json
import os
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.join(ROOT, 'abaqus_plugins')
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from atd.converter import ConversionError, convert_file  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Convert an Abaqus .inp file to an LS-DYNA .k keyword deck.'
    )
    parser.add_argument('input', help='Abaqus input deck')
    parser.add_argument('output', nargs='?', help='LS-DYNA K file (default: input name + .k)')
    parser.add_argument('--strict', action='store_true', help='Do not emit K when ERROR diagnostics exist')
    parser.add_argument('--config', help='JSON material/contact/element mapping overrides')
    parser.add_argument('--d3plot-interval', type=float, default=0.0)
    args = parser.parse_args(argv)

    output = args.output or os.path.splitext(os.path.abspath(args.input))[0] + '.k'
    options = {'strict': args.strict, 'd3plot_interval': args.d3plot_interval}
    if args.config:
        with open(args.config, 'rb') as stream:
            raw = stream.read()
        if not isinstance(raw, str):
            raw = raw.decode('utf-8-sig')
        options.update(json.loads(raw))
    try:
        result = convert_file(args.input, output, options)
    except ConversionError as exc:
        print('ATD: %s' % exc, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
