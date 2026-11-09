"""Context help for controls, including dynamically created engine options."""
from PySide6.QtWidgets import QWidget,QPushButton,QComboBox,QLineEdit,QSpinBox,QCheckBox,QSlider,QTableView,QTextEdit,QLabel,QGroupBox,QTabWidget,QFormLayout


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
            text=f'Choose a whole-number value from {widget.minimum():,} to {widget.maximum():,}.'
        elif isinstance(widget,QLineEdit):
            label=None
            for parent in [root]+root.findChildren(QWidget):
                layout=QWidget.layout(parent)
                if isinstance(layout,QFormLayout):
                    candidate=layout.labelForField(widget)
                    if candidate and isinstance(candidate,QLabel):label=candidate.text();break
            text=widget.placeholderText() or ('Enter '+label+'.' if label else 'Enter or edit this value.')
            if label and any(word in label.lower() for word in ('budget','checkpoint','limit')):
                text+=' Node values accept integers and K, M or B suffixes; time-per-move values are seconds.'

        elif isinstance(widget,QCheckBox):text=widget.text()+': turn this setting on or off.'
        elif isinstance(widget,QSlider):text='Move between recorded checkpoints. Missing thresholds are not invented; requested and actual nodes may differ.'
        elif isinstance(widget,QTableView):text='Select a row or cell to inspect its recorded data. Column headings identify each value; missing analysis is shown as unavailable.'
        elif isinstance(widget,QTextEdit):text='Read the displayed game or variation. Click linked moves to navigate; hover variation moves to preview their positions.'
        elif isinstance(widget,QGroupBox):text=widget.title()+'. Expand to see optional controls.'
        elif isinstance(widget,QLabel):text=widget.text() if len(widget.text())<400 else 'Position and search details for the current selection.'
        elif isinstance(widget,QTabWidget):text='Switch workspaces without interrupting an active match.'
        elif type(widget).__name__ == 'BoardWidget':text='Chessboard: hover a principal-variation move to preview a position. Use Flip to change orientation and Return to Live to follow the running match.'
        elif type(widget).__name__ in ('Evolution','ScalingGraph'):text='Recorded results plotted by node budget. Missing or unbounded values are not plotted; inspect the accompanying table for details.'
        if text: widget.setToolTip(text)
