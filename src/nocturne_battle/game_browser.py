"""Incremental game model and stable source-row mapping under sorting/filtering."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView


class GameModel(QAbstractTableModel):
    columns = ['Game','Pair','White','Black','Result','Plies','Opening','Status']

    def __init__(self):
        super().__init__(); self.rows = []; self.tournament = None

    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()): return 8
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole: return self.columns[section]
        return super().headerData(section,orientation,role)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        if role == Qt.ItemDataRole.DisplayRole: return self.rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:return str(self.rows[index.row()][index.column()])
        if role == Qt.ItemDataRole.UserRole: return index.row()

    def update_state(self,state,active,dirty_rows=None):
        reset = self.tournament != state['id'] or len(self.rows) != len(state['games'])
        if reset:
            self.beginResetModel(); self.rows = [['']*8 for _ in range(len(state['games']))]; self.tournament = state['id']; self.endResetModel()
        indices = range(len(state['games'])) if reset or dirty_rows is None else sorted(set(dirty_rows))
        for row in indices:
            if not 0 <= row < len(state['games']):continue
            g=state['games'][row]
            white = 0 if g['a_white'] else 1
            values = [row+1,g['pair']+1,state['profiles'][white]['name'],state['profiles'][1-white]['name'],g['result'],len(g['moves']),g.get('opening_name',''),
                      (g.get('termination') or 'Completed · reason unavailable') if g['result'] != '*' else 'Running' if active and row == state['index'] else 'Paused / pending']
            if values != self.rows[row]:
                self.rows[row] = values
                self.dataChanged.emit(self.index(row,0),self.index(row,7))


class GameBrowser(QTableView):
    def __init__(self):
        super().__init__()
        self.games = GameModel(); self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.games); self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setModel(self.proxy); self.setSortingEnabled(True)
        self.sortByColumn(0,Qt.SortOrder.AscendingOrder)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalScrollBar().setSingleStep(24)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(26)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setMinimumSectionSize(34)
        self.horizontalHeader().setResizeContentsPrecision(1000)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._fit_timer=QTimer(self);self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_columns)
        self.games.modelReset.connect(lambda:self._fit_timer.start(0))
        self._fit_timer.start(0)

    def fit_columns(self):
        restored=getattr(self,'_restore_widths',None)
        if restored and len(restored)==8:
            self._restore_widths=None
            for i,width in enumerate(restored):self.setColumnWidth(i,max(34,min(1500,int(width))))
            return
        self.resizeColumnsToContents()
        for column,cap in {0:64,1:60,2:180,3:180,4:85,5:64,6:160,7:135}.items():
            self.setColumnWidth(column,min(cap,max(40,self.columnWidth(column))))

    def source_row(self,row): return self.proxy.mapToSource(self.proxy.index(row,0)).row()
    def rowCount(self): return self.proxy.rowCount()
