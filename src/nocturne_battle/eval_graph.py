"""Completed playing-search evaluations, always from White's perspective."""
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Signal
from .adjudication import white_cp


class MoveEvaluationGraph(QWidget):
    selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(120)
        self.setMaximumHeight(160)
        self.points = [[], []]
        self.cursor = 0
        self.setToolTip('Final recorded evaluations by move. Mint: A; blue: B. Positive favors White. Display clipped at ±5 pawns. Click to review a move. Book moves and missing/exact-bound scores have no point.')

    def load(self, item, db, cursor):
        self.points = [[], []]
        self.cursor = cursor
        for key, link in item.get('move_searches', {}).items():
            run = db.search_run(link['search_run_id'])
            if not run: continue
            turn = 1 if run['fen'].split()[1] == 'w' else -1
            side = 0 if (turn == 1) == item['a_white'] else 1
            lines = run.get('final_result', {}).get('lines', {})
            value = white_cp(lines.get('1', lines.get(1)), turn)
            if value is not None: self.points[side].append((int(key), value / 100))
        for points in self.points: points.sort()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#142231'))
        w, h = self.width()-54, self.height()-44
        maximum = max([x for series in self.points for x, y in series] + [2])
        self.maximum = maximum
        p.setPen(QColor('#a9bbce'))
        p.drawText(10, 17, 'EVALUATION · final per move     A mint / B blue     + White / − Black')
        for value in [-5, 0, 5]:
            y = int(28 + h*(5-value)/10)
            p.setPen(QColor('#304459')); p.drawLine(38,y,self.width()-16,y)
            p.setPen(QColor('#a9bbce')); p.drawText(3,y+4,str(value))
        for series, color in zip(self.points, ['#8ed5c5','#77baff']):
            p.setPen(QPen(QColor(color),2)); previous=None
            for ply, value in series:
                point=(int(38+w*ply/maximum),int(28+h*(5-max(-5,min(5,value)))/10))
                if previous: p.drawLine(*previous,*point)
                p.drawEllipse(point[0]-2,point[1]-2,4,4); previous=point
        p.setPen(QColor('#a9bbce')); p.drawText(38,self.height()-3,'Move 1')
        p.drawText(self.width()-90,self.height()-3,f'Move {(maximum+1)//2}')
        x=int(38+w*self.cursor/maximum); p.drawLine(x,25,x,28+h)
        p.end()

    def mousePressEvent(self, event):
        ply=round((event.position().x()-38)/max(1,self.width()-54)*getattr(self,'maximum',2))
        self.selected.emit(max(0,min(getattr(self,'maximum',2),ply)))
