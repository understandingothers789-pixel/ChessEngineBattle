"""Interactive chart of final playing evaluations in White's perspective."""
import math
from PySide6.QtWidgets import QWidget, QSizePolicy, QToolTip
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Signal, Qt, QRectF
from .adjudication import white_cp


def scale_for(values):
    """A symmetric, readable scale including every recorded centipawn score."""
    largest = max([abs(v) for v in values] + [0.25])
    raw = largest / 2
    power = 10 ** math.floor(math.log10(raw))
    step = next(n * power for n in (1, 2, 2.5, 5, 10) if n * power >= raw)
    return math.ceil(largest / step) * step, step


class MoveEvaluationGraph(QWidget):
    selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.points = [[], []]
        self.cursor = 0
        self.hover = None
        self.initial_move = 1
        self.initial_black = False
        self.last_ply = 0
        self.setToolTip('Final exact evaluations from each engine’s completed search. Scores are from White’s perspective; positive favors White. Click a point to review that move.')

    def load(self, item, db, cursor):
        self.points = [[], []]
        self.cursor = cursor
        self.last_ply = len(item.get('moves', []))
        for key, link in item.get('move_searches', {}).items():
            run = db.search_run(link['search_run_id'])
            if not run: continue
            fen = run['fen'].split()
            turn = 1 if fen[1] == 'w' else -1
            side = 0 if (turn == 1) == item['a_white'] else 1
            lines = run.get('final_result', {}).get('lines', {})
            value = white_cp(lines.get('1', lines.get(1)), turn)
            ply = int(key)
            if value is not None:
                self.points[side].append((ply, value / 100, int(fen[5]), turn))
        for series in self.points: series.sort()
        all_points = sorted(p for series in self.points for p in series)
        if all_points:
            ply, _, move, turn = all_points[0]
            # The opening may start on either side and include unanalysed book moves.
            halfmove = (move - 1) * 2 + (turn == -1) - (ply - 1)
            self.initial_move = halfmove // 2 + 1
            self.initial_black = bool(halfmove % 2)
        self.update()

    def geometry(self):
        return QRectF(64, 72, max(1, self.width()-86), max(1, self.height()-122))

    def xy(self, ply, value):
        rect = self.geometry()
        limit, _ = scale_for([p[1] for series in self.points for p in series])
        end = max(2, self.last_ply, *(p[0] for series in self.points for p in series))
        return rect.left() + rect.width() * (ply-1) / (end-1), rect.center().y() - value / limit * rect.height()/2

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#111e2c'))
        p.setPen(QColor('#e4eff7')); p.drawText(16, 23, 'Evaluation by move')
        p.setPen(QColor('#9fb4c7')); p.drawText(16, 43, 'Final engine scores · pawns · positive favors White')
        p.setPen(QColor('#8ed5c5')); p.drawText(16, 61, '━━  Engine A')
        p.setPen(QColor('#86b9ff')); p.drawText(130, 61, '╌╌  Engine B')
        rect = self.geometry()
        limit, step = scale_for([v for series in self.points for _, v, _, _ in series])
        count = round(limit / step)
        for i in range(-count, count+1):
            v = i*step; y = rect.center().y() - v/limit*rect.height()/2
            p.setPen(QPen(QColor('#708598' if i == 0 else '#304153'), 1))
            p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            p.setPen(QColor('#bdcedd'))
            label = f'{v:+g}' if i else '0'
            p.drawText(QRectF(0,y-9,rect.left()-9,18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
        end = max(2, self.last_ply, *(q[0] for series in self.points for q in series))
        max_move = self.initial_move + (end-1+int(self.initial_black))//2
        span = max(1, max_move-self.initial_move)
        raw = max(1, math.ceil(span/6)); power = 10**math.floor(math.log10(raw))
        interval = next(n*power for n in (1,2,5,10) if n*power >= raw)
        first = math.ceil(self.initial_move/interval)*interval
        for move in range(first, max_move+1, interval):
            ply = (move-self.initial_move)*2+1-int(self.initial_black)
            if not 1 <= ply <= end: continue
            x = rect.left()+rect.width()*(ply-1)/(end-1)
            p.setPen(QColor('#304153')); p.drawLine(int(x),int(rect.top()),int(x),int(rect.bottom()))
            p.setPen(QColor('#bdcedd')); p.drawText(QRectF(x-25,rect.bottom()+6,50,18),Qt.AlignmentFlag.AlignHCenter,str(move))
        p.setPen(QColor('#9fb4c7')); p.drawText(QRectF(rect.left(),self.height()-20,rect.width(),18),Qt.AlignmentFlag.AlignCenter,'Move number')
        for series, color, style in zip(self.points, ['#8ed5c5','#86b9ff'], [Qt.PenStyle.SolidLine,Qt.PenStyle.DashLine]):
            p.setPen(QPen(QColor(color), 2, style)); previous = None
            for ply, value, move, turn in series:
                x,y = self.xy(ply,value)
                if previous and ply-previous[0] == 2: p.drawLine(int(previous[1]),int(previous[2]),int(x),int(y))
                p.setBrush(QColor(color)); p.drawEllipse(QRectF(x-2.5,y-2.5,5,5)); previous=(ply,x,y)
        if self.cursor and self.cursor <= end:
            x=rect.left()+rect.width()*(self.cursor-1)/(end-1)
            p.setPen(QPen(QColor('#d8e4ee'),1,Qt.PenStyle.DotLine)); p.drawLine(int(x),int(rect.top()),int(x),int(rect.bottom()))
        if not any(self.points):
            p.setPen(QColor('#bdcedd')); p.drawText(rect,Qt.AlignmentFlag.AlignCenter,'No recorded exact evaluations for this game yet')
        p.end()

    def nearest(self, pos):
        candidates=[]
        for side, series in enumerate(self.points):
            for ply,value,move,turn in series:
                x,y=self.xy(ply,value)
                candidates.append(((x-pos.x())**2+(y-pos.y())**2,side,ply,value,move,turn))
        return min(candidates, default=None)

    def mouseMoveEvent(self, event):
        point=self.nearest(event.position())
        if point and point[0] <= 225:
            _,side,ply,value,move,turn=point
            QToolTip.showText(event.globalPosition().toPoint(), f"Engine {'AB'[side]} · move {move}{'…' if turn == -1 else '.'}\n{value:+.2f} pawns (White perspective)\nClick to review", self)
        else: QToolTip.hideText()

    def mousePressEvent(self, event):
        point=self.nearest(event.position())
        if point and point[0] <= 400: self.selected.emit(point[2])
