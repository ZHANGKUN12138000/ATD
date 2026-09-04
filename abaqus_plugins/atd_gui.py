# -*- coding: utf-8 -*-
"""Abaqus/CAE 2020 GUI for ATD.

Keep this module limited to Abaqus GUI Toolkit imports.  The conversion core is
ordinary Python and is consequently testable without an Abaqus licence.
"""

from abaqusConstants import ALL
from abaqusGui import (
    AFXBoolKeyword,
    AFXDataDialog,
    AFXFileSelectorDialog,
    AFXFloatKeyword,
    AFXForm,
    AFXGuiCommand,
    AFXStringKeyword,
    AFXTextField,
    AFXVerticalAligner,
    AFXSELECTFILE_ANY,
    AFXSELECTFILE_EXISTING,
    DIALOG_ACTIONS_SEPARATOR,
    FRAME_GROOVE,
    LAYOUT_FILL_X,
    SEL_COMMAND,
    FXButton,
    FXCheckButton,
    FXGroupBox,
    FXHorizontalFrame,
    FXLabel,
    FXMAPFUNC,
    getAFXApp,
)


class ATDForm(AFXForm):
    def __init__(self, owner):
        AFXForm.__init__(self, owner)
        self.command = AFXGuiCommand(
            mode=self,
            method='convert_inp',
            objectName='atd_kernel',
            registerQuery=False,
        )
        self.inputKw = AFXStringKeyword(self.command, 'input_path', True, '')
        self.outputKw = AFXStringKeyword(self.command, 'output_path', True, '')
        self.strictKw = AFXBoolKeyword(
            self.command,
            'strict',
            AFXBoolKeyword.TRUE_FALSE,
            True,
            False,
        )
        self.d3plotKw = AFXFloatKeyword(self.command, 'd3plot_interval', True, 0.0)
        self.configKw = AFXStringKeyword(self.command, 'config_path', True, '')

    def getFirstDialog(self):
        return ATDDialog(self)

    def doCustomChecks(self):
        if not self.inputKw.getValue().strip():
            getAFXApp().getAFXMainWindow().writeToMessageArea(
                'ATD: please select an Abaqus .inp file.'
            )
            return False
        if not self.outputKw.getValue().strip():
            getAFXApp().getAFXMainWindow().writeToMessageArea(
                'ATD: please select an LS-DYNA .k output file.'
            )
            return False
        return True


class ATDDialog(AFXDataDialog):
    ID_INPUT = AFXDataDialog.ID_LAST
    ID_OUTPUT = ID_INPUT + 1
    ID_CONFIG = ID_OUTPUT + 1

    def __init__(self, form):
        AFXDataDialog.__init__(
            self,
            form,
            'ATD - Abaqus INP to LS-DYNA K',
            self.OK | self.CANCEL,
            DIALOG_ACTIONS_SEPARATOR,
        )
        self.form = form
        self.getActionButton(self.ID_CLICKED_OK).setText('Convert')

        # FOX message maps must be registered against the dialog instance in
        # Abaqus/CAE 2020.  Registering them globally against the Python class
        # can abort plug-in discovery before the menu item is created.
        FXMAPFUNC(self, SEL_COMMAND, self.ID_INPUT, ATDDialog.onCmdInput)
        FXMAPFUNC(self, SEL_COMMAND, self.ID_OUTPUT, ATDDialog.onCmdOutput)
        FXMAPFUNC(self, SEL_COMMAND, self.ID_CONFIG, ATDDialog.onCmdConfig)

        box = FXGroupBox(self, 'Files', FRAME_GROOVE | LAYOUT_FILL_X)
        aligner = AFXVerticalAligner(box, LAYOUT_FILL_X)

        row = FXHorizontalFrame(aligner, LAYOUT_FILL_X)
        AFXTextField(row, 48, 'Abaqus INP:', form.inputKw, 0)
        FXButton(row, 'Browse...', None, self, self.ID_INPUT)

        row = FXHorizontalFrame(aligner, LAYOUT_FILL_X)
        AFXTextField(row, 48, 'LS-DYNA K:', form.outputKw, 0)
        FXButton(row, 'Browse...', None, self, self.ID_OUTPUT)

        row = FXHorizontalFrame(aligner, LAYOUT_FILL_X)
        AFXTextField(row, 48, 'Mapping JSON (optional):', form.configKw, 0)
        FXButton(row, 'Browse...', None, self, self.ID_CONFIG)

        options = FXGroupBox(self, 'Conversion options', FRAME_GROOVE | LAYOUT_FILL_X)
        AFXTextField(options, 16, 'D3PLOT interval (0 = automatic):', form.d3plotKw, 0)
        FXCheckButton(
            options,
            'Strict mode: stop when a physical definition has no safe mapping',
            form.strictKw,
            0,
        )
        FXLabel(
            self,
            'The converter writes <name>.conversion.json and <name>.idmap.csv next to the K file.\n'
            'Always review warnings and validate units, contacts, material curves and energy balance.',
        )

    def _choose(self, title, keyword, mode, pattern):
        dialog = AFXFileSelectorDialog(
            getAFXApp().getAFXMainWindow(),
            title,
            keyword,
            None,
            mode,
            pattern,
        )
        dialog.create()
        dialog.showModal()

    def onCmdInput(self, sender, sel, ptr):
        self._choose('Select Abaqus input file', self.form.inputKw, AFXSELECTFILE_EXISTING, 'Abaqus input (*.inp)')
        if self.form.inputKw.getValue() and not self.form.outputKw.getValue():
            value = self.form.inputKw.getValue()
            if value.lower().endswith('.inp'):
                value = value[:-4] + '.k'
            else:
                value += '.k'
            self.form.outputKw.setValue(value)
        return 1

    def onCmdOutput(self, sender, sel, ptr):
        self._choose('Select LS-DYNA output file', self.form.outputKw, AFXSELECTFILE_ANY, 'LS-DYNA keyword (*.k)')
        return 1

    def onCmdConfig(self, sender, sel, ptr):
        self._choose('Select mapping overrides', self.form.configKw, AFXSELECTFILE_EXISTING, 'JSON mapping (*.json)')
        return 1
