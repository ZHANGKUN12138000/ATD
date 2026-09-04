# -*- coding: utf-8 -*-
"""Dependency-free Abaqus keyword parser with recursive *INCLUDE support."""

from __future__ import unicode_literals

import codecs
import os
from collections import OrderedDict


class ParseError(Exception):
    pass


class KeywordBlock(object):
    def __init__(self, keyword, params, flags, data, source, line, header):
        self.keyword = keyword
        self.params = params
        self.flags = flags
        self.data = data
        self.source = source
        self.line = line
        self.header = header

    def param(self, name, default=None):
        return self.params.get(name.upper(), default)

    def has_flag(self, name):
        return name.upper() in self.flags


def canonical_keyword(value):
    return ' '.join(value.strip().lstrip('*').upper().replace('_', ' ').split())


def split_csv(line, keep_empty=True):
    # Abaqus keyword data does not use CSV quoting rules in numeric fields, but
    # quoted names do occur.  This small parser preserves empty positional data.
    result = []
    current = []
    quote = None
    for char in line:
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in ('"', "'"):
            quote = char
        elif char == ',':
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    result.append(''.join(current).strip())
    if keep_empty:
        return result
    return [item for item in result if item != '']


def parse_header(line):
    fields = split_csv(line)
    keyword = canonical_keyword(fields[0])
    params = OrderedDict()
    flags = set()
    for field in fields[1:]:
        if not field:
            continue
        if '=' in field:
            key, value = field.split('=', 1)
            params[key.strip().upper()] = value.strip().strip('"\'')
        else:
            flags.add(field.strip().upper())
    return keyword, params, flags


def read_text(path):
    with open(path, 'rb') as stream:
        raw = stream.read()
    for encoding in ('utf-8-sig', 'mbcs', 'gb18030', 'latin-1'):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    raise ParseError('Cannot decode input file: %s' % path)


class AbaqusParser(object):
    def __init__(self, diagnostics=None, max_include_depth=32):
        self.diagnostics = diagnostics
        self.max_include_depth = max_include_depth
        self._stack = []

    def parse(self, path):
        path = os.path.abspath(path)
        return self._parse_file(path, 0)

    def _parse_file(self, path, depth):
        if depth > self.max_include_depth:
            raise ParseError('Maximum *INCLUDE depth exceeded at %s' % path)
        norm = os.path.normcase(os.path.abspath(path))
        if norm in self._stack:
            raise ParseError('Recursive *INCLUDE detected: %s' % path)
        if not os.path.isfile(path):
            raise ParseError('Input file does not exist: %s' % path)

        self._stack.append(norm)
        try:
            lines = read_text(path).splitlines()
            blocks = []
            current = None
            for index, raw_line in enumerate(lines):
                stripped = raw_line.strip()
                if not stripped or stripped.startswith('**'):
                    continue
                if stripped.startswith('*'):
                    if current is not None:
                        blocks.extend(self._finish_block(current, path, depth))
                    keyword, params, flags = parse_header(stripped)
                    current = KeywordBlock(
                        keyword, params, flags, [], path, index + 1, stripped
                    )
                elif current is not None:
                    current.data.append(stripped)
                elif self.diagnostics is not None:
                    self.diagnostics.warning(
                        'ORPHAN_DATA',
                        'Data before the first keyword was ignored.',
                        context={'source': path, 'line': index + 1},
                    )
            if current is not None:
                blocks.extend(self._finish_block(current, path, depth))
            return blocks
        finally:
            self._stack.pop()

    def _finish_block(self, block, parent_path, depth):
        if block.keyword != 'INCLUDE':
            return [block]
        include_name = block.param('INPUT') or block.param('FILE')
        if not include_name and block.data:
            include_name = split_csv(block.data[0], False)[0]
        if not include_name:
            raise ParseError('*INCLUDE has no INPUT value at %s:%s' % (
                block.source, block.line))
        include_name = os.path.expandvars(include_name.strip().strip('"\''))
        if not os.path.isabs(include_name):
            include_name = os.path.join(os.path.dirname(parent_path), include_name)
        if self.diagnostics is not None:
            self.diagnostics.converted('INCLUDE')
        return self._parse_file(os.path.abspath(include_name), depth + 1)


def joined_data_rows(block):
    """Join comma-continued Abaqus records while retaining positional blanks."""
    rows = []
    pending = ''
    for raw in block.data:
        pending = pending + raw if pending else raw
        if raw.rstrip().endswith(','):
            continue
        rows.append(split_csv(pending))
        pending = ''
    if pending:
        rows.append(split_csv(pending))
    return rows


def as_float(value, default=None):
    try:
        return float(str(value).strip().replace('D', 'E').replace('d', 'e'))
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise


def as_int(value):
    return int(float(str(value).strip()))
