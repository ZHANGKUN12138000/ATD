# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class Diagnostics(object):
    def __init__(self):
        self.items = []
        self.converted_keywords = {}
        self.ignored_keywords = {}
        self.unsupported_keywords = {}

    def add(self, severity, code, message, block=None, context=None):
        item = {
            'severity': severity.upper(),
            'code': code,
            'message': message,
        }
        if block is not None:
            item['source'] = block.source
            item['line'] = block.line
            item['abaqus_keyword'] = block.keyword
        if context:
            item['context'] = context
        self.items.append(item)

    def info(self, code, message, block=None, context=None):
        self.add('INFO', code, message, block, context)

    def warning(self, code, message, block=None, context=None):
        self.add('WARNING', code, message, block, context)

    def error(self, code, message, block=None, context=None):
        self.add('ERROR', code, message, block, context)

    def converted(self, keyword):
        self.converted_keywords[keyword] = self.converted_keywords.get(keyword, 0) + 1

    def ignored(self, keyword):
        self.ignored_keywords[keyword] = self.ignored_keywords.get(keyword, 0) + 1

    def unsupported(self, keyword, block=None, detail=None):
        self.unsupported_keywords[keyword] = self.unsupported_keywords.get(keyword, 0) + 1
        message = 'No safe automatic LS-DYNA mapping for *%s.' % keyword
        if detail:
            message += ' ' + detail
        self.error('UNSUPPORTED_KEYWORD', message, block)

    def count(self, severity):
        severity = severity.upper()
        return sum(1 for item in self.items if item['severity'] == severity)

    def as_dict(self):
        return {
            'summary': {
                'errors': self.count('ERROR'),
                'warnings': self.count('WARNING'),
                'info': self.count('INFO'),
            },
            'keyword_coverage': {
                'converted': self.converted_keywords,
                'ignored_as_metadata': self.ignored_keywords,
                'unsupported': self.unsupported_keywords,
            },
            'diagnostics': self.items,
        }
