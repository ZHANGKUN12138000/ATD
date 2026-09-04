# -*- coding: utf-8 -*-
"""ATD Abaqus-to-LS-DYNA conversion core."""

from .converter import ConversionError, convert_file

__all__ = ['ConversionError', 'convert_file']
__version__ = '1.0.1'
