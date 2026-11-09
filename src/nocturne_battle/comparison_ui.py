"""Rank matrix and clickable candidate history using only recorded observations."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QComboBox,QTableWidget,QTableWidgetItem
from .history import ranked
from nocturne.snapshots import node_label


class CandidateViews(QWidget):
    inspect = Signal(int,object,int)
    def __init__(self):
        super().__init__();layout=QVBoxLayout(self)
        label=QLabel('Rank matrix and evolution · — means absent from the recorded MultiPV set, not disproved.');label.setWordWrap(True);layout.addWidget(label)
        self.matrix=QTableWidget(5,3);self.matrix.setHorizontalHeaderLabels(['Rank','Engine A','Engine B']);layout.addWidget(self.matrix)
        self.side=QComboBox();self.side.addItems(['Engine A history','Engine B history']);layout.addWidget(self.side)
        self.heatmap=QTableWidget();layout.addWidget(self.heatmap)
        self.matrix.cellClicked.connect(self.matrix_click);self.heatmap.cellClicked.connect(self.heatmap_click)
        self.side.currentIndexChanged.connect(self.render_heatmap);self.panels=[]
    def refresh(self,panels):
        self.panels=panels
        roots=[{line['pv'][0] for _,line in ranked(p.record['lines'])} if p.record else set() for p in panels]
        for rank in range(1,6):
            self.matrix.setItem(rank-1,0,QTableWidgetItem(str(rank)))
            for side,panel in enumerate(panels):
                line=next((line for r,line in ranked(panel.record['lines']) if r==rank),None) if panel.record else None
                text=(line.get('san',line['pv'])[0] + (' ↔' if line['pv'][0] in roots[1-side] else ' · unique')) if line else '—'
                cell=QTableWidgetItem(text)
                if line:
                    cell.setToolTip(f"Rank {rank}; {line.get('nodes',0):,} reported nodes, depth {line.get('depth',0)}")
                    if line['pv'][0] in roots[1-side]:cell.setBackground(QColor('#284d4c'))
                self.matrix.setItem(rank-1,side+1,cell)
        self.render_heatmap()
    def render_heatmap(self):
        if not self.panels:return
        records=self.panels[self.side.currentIndex()].records
        candidates={line['pv'][0]:line.get('san',line['pv'])[0] for record in records for _,line in ranked(record['lines'])}
        self.moves=sorted(candidates);self.records=records
        self.heatmap.setRowCount(len(self.moves));self.heatmap.setColumnCount(len(records))
        self.heatmap.setHorizontalHeaderLabels([node_label(r['requested']) for r in records]);self.heatmap.setVerticalHeaderLabels([candidates[m] for m in self.moves])
        for col,record in enumerate(records):
            ranks={line['pv'][0]:rank for rank,line in ranked(record['lines'])}
            for row,move in enumerate(self.moves):
                rank=ranks.get(move);cell=QTableWidgetItem('#'+str(rank) if rank else '—')
                if rank:cell.setBackground(QColor(30,65+15*(6-rank),75))
                self.heatmap.setItem(row,col,cell)
    def matrix_click(self,row,col):
        if col and self.panels[col-1].record:self.inspect.emit(col-1,self.panels[col-1].record,row+1)
    def heatmap_click(self,row,col):
        record=self.records[col]
        rank=next((rank for rank,line in ranked(record['lines']) if line['pv'][0]==self.moves[row]),None)
        if rank:self.inspect.emit(self.side.currentIndex(),record,rank)
