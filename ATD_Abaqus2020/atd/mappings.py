# -*- coding: utf-8 -*-
"""Audited, explicit Abaqus-to-LS-DYNA topology mappings."""

from __future__ import unicode_literals


# family, LS-DYNA ELFORM, expected Abaqus connectivity length
ELEMENT_TYPES = {
    'C3D8': ('solid', 1, 8),
    'C3D8R': ('solid', 1, 8),
    'C3D8I': ('solid', 2, 8),
    'C3D4': ('solid', 10, 4),
    'C3D5': ('solid', 15, 5),
    'C3D6': ('solid', 15, 6),
    'C3D10': ('solid10', 16, 10),
    'C3D10M': ('solid10', 16, 10),
    'COH3D8': ('solid', 19, 8),
    'S4': ('shell', 2, 4),
    'S4R': ('shell', 2, 4),
    'S4RS': ('shell', 2, 4),
    'S3': ('shell', 2, 3),
    'S3R': ('shell', 2, 3),
    'M3D4': ('shell', 5, 4),
    'M3D3': ('shell', 5, 3),
    'R3D4': ('shell', 2, 4),
    'R3D3': ('shell', 2, 3),
    'CPE4': ('plane_strain', 13, 4),
    'CPE4R': ('plane_strain', 13, 4),
    'CPE3': ('plane_strain', 13, 3),
    'CPS4': ('plane_stress', 12, 4),
    'CPS4R': ('plane_stress', 12, 4),
    'CPS3': ('plane_stress', 12, 3),
    'CAX4': ('axisymmetric', 15, 4),
    'CAX4R': ('axisymmetric', 15, 4),
    'CAX3': ('axisymmetric', 15, 3),
    'B31': ('beam', 1, 2),
    'B31H': ('beam', 1, 2),
    'T3D2': ('beam', 3, 2),
    'MASS': ('mass', 0, 1),
}


SOLID_FACES = {
    'C3D8': {
        'S1': (0, 1, 2, 3), 'S2': (4, 7, 6, 5),
        'S3': (0, 4, 5, 1), 'S4': (1, 5, 6, 2),
        'S5': (2, 6, 7, 3), 'S6': (3, 7, 4, 0),
    },
    'C3D4': {
        'S1': (0, 1, 2), 'S2': (0, 3, 1),
        'S3': (1, 3, 2), 'S4': (2, 3, 0),
    },
    'C3D6': {
        'S1': (0, 1, 2), 'S2': (3, 5, 4),
        'S3': (0, 3, 4, 1), 'S4': (1, 4, 5, 2),
        'S5': (2, 5, 3, 0),
    },
    'C3D5': {
        'S1': (0, 1, 2, 3), 'S2': (0, 4, 1),
        'S3': (1, 4, 2), 'S4': (2, 4, 3), 'S5': (3, 4, 0),
    },
}


def element_mapping(element_type, overrides=None):
    key = element_type.upper()
    if overrides and key in overrides:
        value = overrides[key]
        return (value['family'], int(value['elform']), int(value['nodes']))
    return ELEMENT_TYPES.get(key)


def surface_face(element_type, face_name, connectivity):
    element_type = element_type.upper()
    if element_type in ('C3D8R', 'C3D8I'):
        element_type = 'C3D8'
    if element_type in ('S4', 'S4R', 'S4RS', 'S3', 'S3R', 'M3D4', 'M3D3', 'R3D4', 'R3D3'):
        nodes = list(connectivity[:4])
        if len(nodes) == 3:
            nodes.append(nodes[-1])
        if str(face_name).upper() == 'SNEG':
            nodes.reverse()
        return nodes
    indices = SOLID_FACES.get(element_type, {}).get(str(face_name).upper())
    if indices is None:
        return None
    nodes = [connectivity[index] for index in indices]
    if len(nodes) == 3:
        nodes.append(nodes[-1])
    return nodes
