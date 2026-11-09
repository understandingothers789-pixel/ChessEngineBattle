"""Context help for controls, including dynamically created engine options."""
from PySide6.QtWidgets import QWidget,QPushButton,QComboBox,QLineEdit,QSpinBox,QCheckBox,QSlider,QTableView,QTextEdit,QLabel,QGroupBox,QTabWidget


def install_tooltips(root):
    for widget in [root]+root.findChildren(QWidget):
        if widget.toolTip(): continue
        text = ''
        if isinstance(widget,QPushButton):
            text = widget.text().replace('&','').strip('… .')
            text = {'Test engine':'Run the selected executable and check its UCI chess-engine connection.',
                    'Save engine':'Save the tested engine and its settings for future matches.',
                    'Unload Engine A':'Pause first. Disconnect Engine A while keeping saved settings and history.',
                    'Unload Engine B':'Pause first. Disconnect Engine B while keeping saved settings and history.',
                    'Final result':'Show the engine’s final reported result, separately from historical checkpoints.',
                    'Original thinking':'Show the search recorded as the source of the selected move; legacy attribution may be uncertain.',
                    'Return to Live':'Follow the running game again without interrupting engine searches.'}.get(text,text+'.')
        elif isinstance(widget,QComboBox):
            choices=[widget.itemText(i) for i in range(min(widget.count(),8))]
            text='Choose an option'+(': '+ '; '.join(choices) if choices else '. Load an engine file to populate saved engine choices.')
        elif isinstance(widget,QSpinBox):
            text=f'Choose a whole-number value from {widget.minimum():,} to {widget.maximum():,}. Current value: {widget.value():,}.'
        elif isinstance(widget,QLineEdit):
            text=widget.placeholderText() or 'Enter or edit this value. Node budgets accept whole numbers and K, M or B suffixes; file fields require a local path.'
        elif isinstance(widget,QCheckBox):text=widget.text()+': turn this setting on or off.'
        elif isinstance(widget,QSlider):text='Move between recorded checkpoints. Missing thresholds are not invented; requested and actual nodes may differ.'
        elif isinstance(widget,QTableView):text='Select a row or cell to inspect its recorded data. Column headings identify each value; missing analysis is shown as unavailable.'
        elif isinstance(widget,QTextEdit):text='Read the displayed game or variation. Click linked moves to navigate; hover variation moves to preview their positions.'
        elif isinstance(widget,QGroupBox):text=widget.title()+'. Expand to see optional controls.'
        elif isinstance(widget,QLabel):text=widget.text() if len(widget.text())<400 else 'Position and search details for the current selection.'
        elif isinstance(widget,QTabWidget):text='Switch workspaces without interrupting an active match.'
        if text: widget.setToolTip(text)
