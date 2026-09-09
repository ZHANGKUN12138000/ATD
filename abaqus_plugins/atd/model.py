# -*- coding: utf-8 -*-
"""Abaqus semantic model and assembly flattener."""

from __future__ import unicode_literals

import math
from collections import OrderedDict

from .parser import as_float, as_int, joined_data_rows

try:
    integer_types = (int, long)
except NameError:
    integer_types = (int,)


MATERIAL_KEYWORDS = set([
    'ACOUSTIC MEDIUM', 'ANISOTROPIC HYPERELASTIC', 'BRITTLE CRACKING',
    'BRITTLE FAILURE', 'BRITTLE SHEAR', 'CAP PLASTICITY', 'CAST IRON PLASTICITY',
    'CLAY PLASTICITY', 'CONCRETE', 'CONCRETE COMPRESSION DAMAGE',
    'CONCRETE COMPRESSION HARDENING', 'CONCRETE DAMAGED PLASTICITY',
    'CONCRETE TENSION DAMAGE', 'CONCRETE TENSION STIFFENING', 'CREEP',
    'CRUSHABLE FOAM', 'CYCLIC HARDENING', 'DAMAGE EVOLUTION',
    'DAMAGE INITIATION', 'DAMAGE STABILIZATION', 'DEFORMATION PLASTICITY',
    'DENSITY', 'DEPVAR', 'DRUCKER PRAGER', 'DRUCKER PRAGER HARDENING',
    'DETONATION POINT', 'ELASTIC', 'EOS', 'ELECTRICAL CONDUCTIVITY', 'EQUATION OF STATE',
    'EXPANSION', 'FAIL STRESS', 'FAIL STRAIN', 'HYPERELASTIC',
    'HYPERFOAM', 'JOHNSON COOK', 'LOW DENSITY FOAM', 'MAGNETIC PERMEABILITY',
    'MOHR COULOMB', 'MOHR COULOMB HARDENING', 'MULLINS EFFECT', 'NO COMPRESSION',
    'NO TENSION', 'PERMEABILITY', 'PLASTIC', 'RATE DEPENDENT', 'SHEAR FAILURE',
    'SPECIFIC HEAT', 'TENSILE FAILURE', 'USER MATERIAL', 'VISCOELASTIC',
])

INTERACTION_KEYWORDS = set([
    'FRICTION', 'NORMAL BEHAVIOR', 'SURFACE BEHAVIOR', 'SURFACE INTERACTION',
    'COHESIVE BEHAVIOR', 'DAMAGE INITIATION', 'DAMAGE EVOLUTION', 'DAMPING',
])

IGNORED_METADATA = set([
    'HEADING', 'PREPRINT', 'PRINT', 'OUTPUT', 'NODE OUTPUT', 'ELEMENT OUTPUT',
    'CONTACT OUTPUT', 'ENERGY OUTPUT', 'FILE OUTPUT', 'FILE FORMAT',
    'RESTART', 'MONITOR', 'HISTORY OUTPUT', 'FIELD OUTPUT',
])


class SourcePart(object):
    def __init__(self, name):
        self.name = name
        self.nodes = OrderedDict()
        self.elements = OrderedDict()
        self.nsets = OrderedDict()
        self.elsets = OrderedDict()
        self.sections = []
        self.surfaces = OrderedDict()


class SourceElement(object):
    def __init__(self, label, element_type, nodes, block):
        self.label = label
        self.element_type = element_type.upper()
        self.nodes = nodes
        self.block = block


class SetDefinition(object):
    def __init__(self, name, kind, members, instance=None, generated=False, block=None):
        self.name = name
        self.kind = kind
        self.members = members
        self.instance = instance
        self.generated = generated
        self.block = block


class SurfaceDefinition(object):
    def __init__(self, name, surface_type, rows, block, scope=None):
        self.name = name
        self.surface_type = surface_type
        self.rows = rows
        self.block = block
        self.scope = scope


class SectionDefinition(object):
    def __init__(self, kind, elset, material, values, params, block):
        self.kind = kind
        self.elset = elset
        self.material = material
        self.values = values
        self.params = params
        self.block = block


class MaterialDefinition(object):
    def __init__(self, name, block):
        self.name = name
        self.block = block
        self.properties = OrderedDict()

    def add(self, block):
        self.properties.setdefault(block.keyword, []).append(block)

    def first(self, keyword):
        values = self.properties.get(keyword, [])
        return values[0] if values else None


class InteractionDefinition(object):
    def __init__(self, name, block):
        self.name = name
        self.block = block
        self.properties = OrderedDict()

    def add(self, block):
        self.properties.setdefault(block.keyword, []).append(block)


class InstanceDefinition(object):
    def __init__(self, name, part, rows, block):
        self.name = name
        self.part = part
        self.rows = rows
        self.block = block
        # Abaqus/CAE commonly writes orphan-mesh nodes, elements, sets and
        # sections between *INSTANCE and *END INSTANCE while leaving the
        # referenced *PART block empty.  Keep that mesh private to the
        # instance so repeated labels in another instance cannot overwrite it.
        self.mesh = SourcePart(part or name)


class Action(object):
    def __init__(self, kind, block, step_name=None):
        self.kind = kind
        self.block = block
        self.step_name = step_name


class StepDefinition(object):
    def __init__(self, name, block):
        self.name = name
        self.block = block
        self.period = 1.0
        self.start_time = 0.0
        self.procedure = 'EXPLICIT'


class SourceModel(object):
    def __init__(self, title):
        self.title = title
        self.parts = OrderedDict()
        self.instances = []
        self.global_sets = []
        self.global_surfaces = []
        self.materials = OrderedDict()
        self.interactions = OrderedDict()
        self.amplitudes = OrderedDict()
        self.section_controls = OrderedDict()
        self.actions = []
        self.steps = OrderedDict()
        self.blocks = []


class FlatElement(object):
    def __init__(self, label, source_label, element_type, nodes, instance, source_part, block):
        self.label = label
        self.source_label = source_label
        self.element_type = element_type
        self.nodes = nodes
        self.instance = instance
        self.source_part = source_part
        self.block = block
        self.pid = None


class FlatModel(object):
    def __init__(self, source):
        self.source = source
        self.nodes = OrderedDict()
        self.elements = OrderedDict()
        self.node_map = OrderedDict()
        self.element_map = OrderedDict()
        self.nsets = OrderedDict()
        self.elsets = OrderedDict()
        self.surfaces = OrderedDict()
        self.section_assignments = []
        self.instance_names = []


def _name(value):
    return str(value or '').strip().upper()


def _values(block):
    rows = joined_data_rows(block)
    return rows[0] if rows else []


def _node_system(block, diagnostics):
    values = []
    for value in _values(block):
        if value != '':
            try:
                values.append(as_float(value))
            except ValueError:
                diagnostics.error('BAD_SYSTEM', 'Invalid coordinate-system value %s.' % value, block)
                return None
    if not values:
        return None
    if len(values) == 3:
        return (tuple(values), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if len(values) < 9:
        diagnostics.error('BAD_SYSTEM', '*SYSTEM requires 3 or 9 coordinates.', block)
        return None
    origin = values[0:3]
    bx = [values[3 + i] - origin[i] for i in range(3)]
    cx = [values[6 + i] - origin[i] for i in range(3)]
    blen = math.sqrt(sum(value * value for value in bx))
    if blen == 0.0:
        diagnostics.error('BAD_SYSTEM', '*SYSTEM X-axis point equals the origin.', block)
        return None
    e1 = [value / blen for value in bx]
    projection = sum(cx[i] * e1[i] for i in range(3))
    e2raw = [cx[i] - projection * e1[i] for i in range(3)]
    e2len = math.sqrt(sum(value * value for value in e2raw))
    if e2len == 0.0:
        diagnostics.error('BAD_SYSTEM', '*SYSTEM plane point is collinear with the X axis.', block)
        return None
    e2 = [value / e2len for value in e2raw]
    e3 = [e1[1]*e2[2] - e1[2]*e2[1],
          e1[2]*e2[0] - e1[0]*e2[2],
          e1[0]*e2[1] - e1[1]*e2[0]]
    return (tuple(origin), tuple(e1), tuple(e2), tuple(e3))


def _apply_node_system(coords, system):
    if system is None:
        return tuple(coords)
    origin, e1, e2, e3 = system
    return tuple(origin[i] + coords[0]*e1[i] + coords[1]*e2[i] + coords[2]*e3[i]
                 for i in range(3))


def _parse_set(block, kind):
    set_name = block.param('NSET' if kind == 'node' else 'ELSET')
    members = []
    generate = block.has_flag('GENERATE') or block.param('GENERATE') is not None
    for row in joined_data_rows(block):
        clean = [item for item in row if item != '']
        if generate:
            if len(clean) < 2:
                continue
            first, last = as_int(clean[0]), as_int(clean[1])
            increment = as_int(clean[2]) if len(clean) > 2 else 1
            members.extend(range(first, last + (1 if increment > 0 else -1), increment))
        else:
            for item in clean:
                try:
                    members.append(as_int(item))
                except ValueError:
                    members.append(_name(item))
    return SetDefinition(
        _name(set_name), kind, members, _name(block.param('INSTANCE')) or None,
        generate, block,
    )


def build_source_model(blocks, diagnostics):
    title = 'Converted Abaqus model'
    model = SourceModel(title)
    model.blocks = blocks
    global_part = SourcePart('__GLOBAL__')
    model.parts[global_part.name] = global_part
    current_part = None
    current_instance = None
    current_material = None
    current_interaction = None
    current_step = None
    current_system = None
    recognized = set()

    for block in blocks:
        kw = block.keyword

        if current_material is not None and kw in MATERIAL_KEYWORDS:
            current_material.add(block)
            recognized.add(id(block))
            diagnostics.converted(kw)
            continue
        if current_interaction is not None and kw in INTERACTION_KEYWORDS and kw != 'SURFACE INTERACTION':
            current_interaction.add(block)
            recognized.add(id(block))
            diagnostics.converted(kw)
            continue
        if kw not in MATERIAL_KEYWORDS:
            current_material = None
        if kw not in INTERACTION_KEYWORDS:
            current_interaction = None

        if kw == 'HEADING':
            if block.data:
                title = block.data[0].strip()
                model.title = title
            diagnostics.ignored(kw)
        elif kw == 'PART':
            name = _name(block.param('NAME') or 'PART_%d' % len(model.parts))
            current_part = SourcePart(name)
            model.parts[name] = current_part
            current_instance = None
            current_system = None
            diagnostics.converted(kw)
        elif kw == 'END PART':
            current_part = None
            current_system = None
            diagnostics.converted(kw)
        elif kw == 'SYSTEM':
            current_system = _node_system(block, diagnostics)
            diagnostics.converted(kw)
        elif kw == 'NODE':
            part = current_part or (current_instance.mesh if current_instance else global_part)
            implicit_set = _name(block.param('NSET'))
            implicit_members = []
            for row in joined_data_rows(block):
                if len(row) < 3:
                    diagnostics.error('BAD_NODE', 'A node row requires an ID and at least two coordinates.', block)
                    continue
                try:
                    nid = as_int(row[0])
                    coords = [as_float(value, 0.0) for value in row[1:4]]
                    while len(coords) < 3:
                        coords.append(0.0)
                    part.nodes[nid] = _apply_node_system(coords, current_system)
                    implicit_members.append(nid)
                except ValueError:
                    diagnostics.error('BAD_NODE', 'Invalid numeric value in node row: %s' % row, block)
            if implicit_set:
                existing = part.nsets.get(implicit_set)
                if existing:
                    existing.members.extend(implicit_members)
                else:
                    part.nsets[implicit_set] = SetDefinition(
                        implicit_set, 'node', implicit_members, block=block)
            diagnostics.converted(kw)
        elif kw == 'ELEMENT':
            part = current_part or (current_instance.mesh if current_instance else global_part)
            element_type = _name(block.param('TYPE'))
            implicit_set = _name(block.param('ELSET'))
            implicit_members = []
            for row in joined_data_rows(block):
                clean = [item for item in row if item != '']
                if len(clean) < 2:
                    diagnostics.error('BAD_ELEMENT', 'An element row requires an ID and connectivity.', block)
                    continue
                try:
                    eid = as_int(clean[0])
                    conn = [as_int(value) for value in clean[1:]]
                    part.elements[eid] = SourceElement(eid, element_type, conn, block)
                    implicit_members.append(eid)
                except ValueError:
                    diagnostics.error('BAD_ELEMENT', 'Invalid element row: %s' % row, block)
            if implicit_set:
                existing = part.elsets.get(implicit_set)
                if existing:
                    existing.members.extend(implicit_members)
                else:
                    part.elsets[implicit_set] = SetDefinition(
                        implicit_set, 'element', implicit_members, block=block)
            diagnostics.converted(kw)
        elif kw in ('NSET', 'ELSET'):
            kind = 'node' if kw == 'NSET' else 'element'
            definition = _parse_set(block, kind)
            if not definition.name:
                diagnostics.error('UNNAMED_SET', '*%s has no set name.' % kw, block)
            elif current_part is not None or current_instance is not None:
                scoped_part = current_part or current_instance.mesh
                target = scoped_part.nsets if kind == 'node' else scoped_part.elsets
                if definition.name in target:
                    target[definition.name].members.extend(definition.members)
                else:
                    target[definition.name] = definition
            else:
                model.global_sets.append(definition)
            diagnostics.converted(kw)
        elif kw in ('SOLID SECTION', 'SHELL SECTION', 'BEAM SECTION', 'MEMBRANE SECTION', 'MASS'):
            part = current_part or (current_instance.mesh if current_instance else global_part)
            kind = kw.split()[0].lower()
            section = SectionDefinition(
                kind,
                _name(block.param('ELSET')),
                _name(block.param('MATERIAL')),
                _values(block),
                block.params,
                block,
            )
            part.sections.append(section)
            diagnostics.converted(kw)
        elif kw == 'SURFACE':
            surface = SurfaceDefinition(
                _name(block.param('NAME')),
                _name(block.param('TYPE') or 'ELEMENT'),
                joined_data_rows(block),
                block,
                (current_part.name if current_part else
                 current_instance.name if current_instance else None),
            )
            if current_part or current_instance:
                scoped_part = current_part or current_instance.mesh
                scoped_part.surfaces[surface.name] = surface
            else:
                model.global_surfaces.append(surface)
            diagnostics.converted(kw)
        elif kw == 'INSTANCE':
            current_instance = InstanceDefinition(
                _name(block.param('NAME')),
                _name(block.param('PART')),
                joined_data_rows(block),
                block,
            )
            model.instances.append(current_instance)
            current_system = None
            diagnostics.converted(kw)
        elif kw == 'END INSTANCE':
            current_instance = None
            current_system = None
            diagnostics.converted(kw)
        elif kw in ('ASSEMBLY', 'END ASSEMBLY', 'CONTACT'):
            diagnostics.converted(kw)
        elif kw == 'MATERIAL':
            material = MaterialDefinition(_name(block.param('NAME')), block)
            model.materials[material.name] = material
            current_material = material
            diagnostics.converted(kw)
        elif kw == 'SURFACE INTERACTION':
            interaction = InteractionDefinition(_name(block.param('NAME')), block)
            model.interactions[interaction.name] = interaction
            current_interaction = interaction
            diagnostics.converted(kw)
        elif kw == 'AMPLITUDE':
            model.amplitudes[_name(block.param('NAME'))] = block
            diagnostics.converted(kw)
        elif kw == 'SECTION CONTROLS':
            control_name = _name(block.param('NAME'))
            if not control_name:
                diagnostics.error(
                    'UNNAMED_SECTION_CONTROLS',
                    '*SECTION CONTROLS has no NAME.',
                    block,
                )
            else:
                model.section_controls[control_name] = block
                diagnostics.converted(kw)
        elif kw == 'CONTACT INITIALIZATION DATA':
            if block.data:
                diagnostics.unsupported(
                    kw,
                    block,
                    'Non-empty contact initialization data has no general LS-DYNA equivalent.',
                )
            else:
                # Abaqus/CAE can leave an unused, empty named definition in
                # the deck.  It carries no parameters to the active contact.
                diagnostics.ignored(kw)
                diagnostics.info(
                    'EMPTY_CONTACT_INITIALIZATION',
                    'Empty contact initialization definition %s has no active data and was omitted.' % (
                        _name(block.param('NAME')) or '<UNNAMED>'),
                    block,
                )
        elif kw == 'STEP':
            step_name = _name(block.param('NAME') or 'STEP_%d' % (len(model.steps) + 1))
            current_step = StepDefinition(step_name, block)
            model.steps[step_name] = current_step
            diagnostics.converted(kw)
        elif kw == 'END STEP':
            current_step = None
            diagnostics.converted(kw)
        elif kw in ('DYNAMIC', 'DYNAMIC EXPLICIT', 'STATIC'):
            if current_step:
                values = []
                for value in _values(block):
                    if value != '':
                        try:
                            values.append(as_float(value))
                        except ValueError:
                            pass
                if values:
                    if kw == 'STATIC':
                        current_step.procedure = 'STATIC'
                        current_step.period = values[1] if len(values) > 1 else values[0]
                    elif kw == 'DYNAMIC' and not block.has_flag('EXPLICIT'):
                        current_step.procedure = 'IMPLICIT_DYNAMIC'
                        current_step.period = values[1] if len(values) > 1 else values[-1]
                    else:
                        current_step.procedure = 'EXPLICIT'
                        current_step.period = values[-1]
            diagnostics.converted(kw)
        elif kw in (
            'BOUNDARY', 'CLOAD', 'DLOAD', 'DSLOAD', 'INITIAL CONDITIONS',
            'CONTACT PAIR', 'CONTACT INCLUSIONS', 'CONTACT PROPERTY ASSIGNMENT',
            'TIE', 'RIGID BODY', 'TEMPERATURE', 'BULK VISCOSITY',
        ):
            model.actions.append(Action(kw, block, current_step.name if current_step else None))
            diagnostics.converted(kw)
        elif kw in IGNORED_METADATA:
            diagnostics.ignored(kw)
        elif kw in ('END',):
            diagnostics.ignored(kw)
        else:
            # Property children caught above.  Unknown analysis keywords are not
            # silently dropped because that could change the physical problem.
            diagnostics.unsupported(kw, block)

    running = 0.0
    for step in model.steps.values():
        step.start_time = running
        running += step.period
    return model


def _rotation_matrix(p1, p2, degrees):
    axis = [p2[i] - p1[i] for i in range(3)]
    length = math.sqrt(sum(value * value for value in axis))
    if length == 0.0:
        return None
    x, y, z = [value / length for value in axis]
    angle = math.radians(degrees)
    c = math.cos(angle)
    s = math.sin(angle)
    q = 1.0 - c
    return (
        (c + x*x*q, x*y*q - z*s, x*z*q + y*s),
        (y*x*q + z*s, c + y*y*q, y*z*q - x*s),
        (z*x*q - y*s, z*y*q + x*s, c + z*z*q),
    )


def _instance_transform(instance, diagnostics):
    translation = (0.0, 0.0, 0.0)
    rotation = None
    origin = (0.0, 0.0, 0.0)
    if instance is None:
        return translation, rotation, origin
    if instance.rows:
        first = [item for item in instance.rows[0] if item != '']
        if len(first) == 3:
            translation = tuple(as_float(value, 0.0) for value in first)
        elif len(first) == 7:
            values = [as_float(value, 0.0) for value in first]
            origin = tuple(values[0:3])
            rotation = _rotation_matrix(values[0:3], values[3:6], values[6])
    if len(instance.rows) > 1:
        second = [item for item in instance.rows[1] if item != '']
        if len(second) == 7:
            values = [as_float(value, 0.0) for value in second]
            origin = tuple(values[0:3])
            rotation = _rotation_matrix(values[0:3], values[3:6], values[6])
    return translation, rotation, origin


def _transform(point, transform):
    translation, rotation, origin = transform
    # Abaqus applies positioning operations in order: translation, then
    # rotation about the assembly-space axis on the second data line.
    translated = [point[i] + translation[i] for i in range(3)]
    shifted = [translated[i] - origin[i] for i in range(3)]
    if rotation:
        shifted = [sum(rotation[i][j] * shifted[j] for j in range(3)) for i in range(3)]
    return tuple(shifted[i] + origin[i] for i in range(3))


def _unique(values):
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _expand_source_set(definitions, set_name, diagnostics, stack=None):
    stack = list(stack or [])
    if set_name in stack:
        definition = definitions.get(set_name)
        diagnostics.error(
            'RECURSIVE_SET',
            'Recursive set reference: %s.' % ' -> '.join(stack + [set_name]),
            definition.block if definition else None,
        )
        return []
    definition = definitions.get(set_name)
    if definition is None:
        return []
    values = []
    for member in definition.members:
        if isinstance(member, integer_types):
            values.append(member)
        elif member in definitions:
            values.extend(_expand_source_set(
                definitions, member, diagnostics, stack + [set_name]
            ))
        else:
            diagnostics.error(
                'SET_MEMBER_MISSING',
                'Set %s references missing nested set %s.' % (set_name, member),
                definition.block,
            )
    return _unique(values)


def flatten_model(source, diagnostics):
    flat = FlatModel(source)
    global_part = source.parts.get('__GLOBAL__')
    placements = []
    if global_part and (global_part.nodes or global_part.elements):
        placements.append(('GLOBAL', global_part, None))
    if source.instances:
        for instance in source.instances:
            template_part = source.parts.get(instance.part)
            embedded = instance.mesh
            has_embedded_mesh = bool(embedded.nodes or embedded.elements)
            part = embedded if has_embedded_mesh else template_part
            if part is None:
                diagnostics.error(
                    'MISSING_INSTANCE_PART',
                    'Instance %s references missing part %s.' % (instance.name, instance.part),
                    instance.block,
                )
                continue
            if (has_embedded_mesh and template_part is not None and
                    (template_part.nodes or template_part.elements)):
                diagnostics.warning(
                    'INSTANCE_MESH_OVERRIDES_PART',
                    'Instance %s contains its own mesh; embedded instance data was used instead of part %s.' % (
                        instance.name, instance.part),
                    instance.block,
                )
            placements.append((instance.name, part, instance))
    else:
        for part_name, part in source.parts.items():
            if part_name == '__GLOBAL__':
                continue
            placements.append((part_name, part, None))

    next_node = 1
    next_element = 1
    placement_by_name = {}
    for instance_name, part, instance in placements:
        placement_by_name[instance_name] = (part, instance)
        flat.instance_names.append(instance_name)
        transform = _instance_transform(instance, diagnostics)
        for source_id, coords in part.nodes.items():
            flat.nodes[next_node] = _transform(coords, transform)
            flat.node_map[(instance_name, source_id)] = next_node
            next_node += 1
        for source_id, element in part.elements.items():
            mapped = []
            missing = False
            for node_id in element.nodes:
                new_id = flat.node_map.get((instance_name, node_id))
                if new_id is None:
                    diagnostics.error(
                        'MISSING_CONNECTIVITY_NODE',
                        'Element %s in %s references missing node %s.' % (
                            source_id, instance_name, node_id),
                        element.block,
                    )
                    missing = True
                    break
                mapped.append(new_id)
            if missing:
                continue
            flat_element = FlatElement(
                next_element, source_id, element.element_type, mapped,
                instance_name, part.name, element.block,
            )
            flat.elements[next_element] = flat_element
            flat.element_map[(instance_name, source_id)] = next_element
            next_element += 1

        for set_name, definition in part.nsets.items():
            values = []
            for member in _expand_source_set(part.nsets, set_name, diagnostics):
                mapped = flat.node_map.get((instance_name, member))
                if mapped is not None:
                    values.append(mapped)
            flat.nsets[instance_name + '.' + set_name] = _unique(values)
        for set_name, definition in part.elsets.items():
            values = []
            for member in _expand_source_set(part.elsets, set_name, diagnostics):
                mapped = flat.element_map.get((instance_name, member))
                if mapped is not None:
                    values.append(mapped)
            flat.elsets[instance_name + '.' + set_name] = _unique(values)

        for section in part.sections:
            flat.section_assignments.append((instance_name, section))
        for surface_name, surface in part.surfaces.items():
            flat.surfaces[instance_name + '.' + surface_name] = SurfaceDefinition(
                instance_name + '.' + surface_name,
                surface.surface_type,
                surface.rows,
                surface.block,
                instance_name,
            )

    # Add unqualified aliases for part-level sets/surfaces.  When repeated
    # instances exist the alias is a union, matching typical Abaqus intent.
    for collection in (flat.nsets, flat.elsets):
        aliases = OrderedDict()
        for qualified, values in list(collection.items()):
            base = qualified.split('.', 1)[-1]
            aliases.setdefault(base, []).extend(values)
        for base, values in aliases.items():
            if base not in collection:
                collection[base] = _unique(values)
    surface_aliases = OrderedDict()
    for qualified, surface in list(flat.surfaces.items()):
        base = qualified.split('.', 1)[-1]
        surface_aliases.setdefault(base, []).append(surface)
    for base, surfaces in surface_aliases.items():
        if base not in flat.surfaces:
            rows = []
            for surface in surfaces:
                for row in surface.rows:
                    rows.append([surface.scope + '.' + row[0]] + row[1:])
            flat.surfaces[base] = SurfaceDefinition(
                base, surfaces[0].surface_type, rows, surfaces[0].block, None)

    for definition in source.global_sets:
        values = []
        target = flat.nsets if definition.kind == 'node' else flat.elsets
        mapping = flat.node_map if definition.kind == 'node' else flat.element_map
        for member in definition.members:
            if isinstance(member, integer_types):
                if definition.instance:
                    mapped = mapping.get((definition.instance, member))
                    if mapped is not None:
                        values.append(mapped)
                else:
                    mapped = mapping.get(('GLOBAL', member))
                    if mapped is not None:
                        values.append(mapped)
            else:
                key = member
                # Abaqus assembly sets may use INSTANCE.label directly.
                if '.' in key:
                    prefix, suffix = key.rsplit('.', 1)
                    try:
                        mapped = mapping.get((prefix, as_int(suffix)))
                        if mapped is not None:
                            values.append(mapped)
                            continue
                    except ValueError:
                        pass
                if '.' not in key and definition.instance:
                    key = definition.instance + '.' + key
                values.extend(target.get(key, []))
        if definition.name in target:
            target[definition.name] = _unique(target[definition.name] + values)
        else:
            target[definition.name] = _unique(values)

    for surface in source.global_surfaces:
        flat.surfaces[surface.name] = surface

    return flat


def resolve_named(collection, name):
    key = _name(name)
    if key in collection:
        return collection[key]
    matches = [value for candidate, value in collection.items()
               if candidate.endswith('.' + key)]
    if len(matches) == 1:
        return matches[0]
    return None
