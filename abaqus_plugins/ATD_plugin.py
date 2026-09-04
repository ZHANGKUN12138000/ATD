# -*- coding: utf-8 -*-
"""Abaqus/CAE registration entry point (the *_plugin.py suffix is required)."""

import os
import tempfile
import traceback


def _write_startup_log(message):
    """Write an ASCII startup trace without depending on the CAE message area."""
    path = os.path.join(tempfile.gettempdir(), 'ATD_Abaqus2020_plugin.log')
    try:
        stream = open(path, 'ab')
        try:
            if not isinstance(message, str):
                message = str(message)
            stream.write(message + '\r\n')
        finally:
            stream.close()
    except Exception:
        pass


try:
    from abaqusConstants import ALL
    from abaqusGui import AFXMode, getAFXApp
    from atd_gui import ATDForm

    toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
    form = ATDForm(toolset)
    toolset.registerGuiMenuButton(
        # registerGuiMenuButton already targets the Plug-ins menu.  A pipe is
        # only for a deliberate submenu and must not repeat "Plug-ins" here.
        buttonText='ATD - Abaqus to LS-DYNA...',
        object=form,
        messageId=AFXMode.ID_ACTIVATE,
        icon=None,
        kernelInitString='import atd_kernel',
        applicableModules=ALL,
        version='1.0.1',
        author='ATD',
        description='Convert an Abaqus input deck into an auditable LS-DYNA keyword deck.',
        helpUrl='',
    )
    _write_startup_log('OK: ATD 1.0.1 GUI menu registered from %s' % __file__)
    if os.environ.get('ATD_PLUGIN_SELFTEST') == '1':
        probe_dialog = form.getFirstDialog()
        _write_startup_log('OK: ATD conversion dialog constructed.')
        del probe_dialog
except Exception:
    _write_startup_log('ERROR: ATD GUI registration failed.')
    _write_startup_log(traceback.format_exc())
