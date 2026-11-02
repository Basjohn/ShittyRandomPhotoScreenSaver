"""Gesture-based ribbon authoring widgets; values use the same neutral validators as runtime."""
from __future__ import annotations
from copy import deepcopy
import math
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QTabWidget
from core.waveform_ribbon_authoring import SOURCES, TARGETS, admit_routing, admit_ribbons, admit_palette
from ui.widgets import StyledComboBox
from ui.styled_popup import ColorSwatchButton
from ui.tabs.shared_styles import NoWheelSlider


def display_colour(rgb):
    return QColor.fromRgbF(*(12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055 for v in rgb))


def linear_colour(colour):
    return [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in colour.getRgbF()[:3]]


class _ValueEditor(QWidget):
    valueChanged = Signal(object)
    valueCommitted = Signal(object)
    validator = staticmethod(lambda value:value)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._value = None
        self._loading = False

    def value(self):
        return deepcopy(self._value)

    def setValue(self,value):
        self._value = self.validator(value)
        self._loading = True
        try:self.refresh()
        finally:self._loading = False
        self.update()

    def changed(self,commit=True):
        if self._loading or self._value is None:return
        self._value = self.validator(self._value)
        self.valueChanged.emit(self.value())
        if commit:self.valueCommitted.emit(self.value())
        self.update()


class _MatrixCanvas(QWidget):
    selected = Signal(int,int)

    def __init__(self,owner):
        super().__init__(owner)
        self.owner = owner
        self.setMinimumSize(390,260)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.owner._value is None:return
        x0,y0=82.,24.;cw=(self.width()-x0)/6;rh=(self.height()-y0)/len(TARGETS)
        p.setPen(self.palette().text().color())
        for col,source in enumerate(SOURCES):p.drawText(QRectF(x0+col*cw,0,cw,22),Qt.AlignmentFlag.AlignCenter,source)
        for row,target in enumerate(TARGETS):
            p.setPen(self.palette().text().color());p.drawText(QRectF(0,y0+row*rh,x0-5,rh),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,target.title())
            for col,(gain,_power) in enumerate(self.owner._value[target]):
                rect=QRectF(x0+col*cw+1,y0+row*rh+1,cw-2,rh-2)
                tone=QColor(self.palette().highlight().color());tone.setAlphaF(.08+.6*gain/2.)
                p.fillRect(rect,tone)
                p.setPen(self.palette().highlight().color() if (row,col)==self.owner.active else self.palette().mid().color())
                p.drawRoundedRect(rect,3,3)
                p.setPen(self.palette().text().color());p.drawText(rect,Qt.AlignmentFlag.AlignCenter,f'{gain:.2g}')

    def mousePressEvent(self,event):
        col=int((event.position().x()-82.)/((self.width()-82.)/6))
        row=int((event.position().y()-24.)/((self.height()-24.)/len(TARGETS)))
        if event.position().x()>=82 and event.position().y()>=24 and 0<=col<6 and 0<=row<len(TARGETS):
            self.selected.emit(row,col)


class _PowerCurve(QWidget):
    changed = Signal(float)
    committed = Signal()

    def __init__(self,parent=None):
        super().__init__(parent);self.power=1.;self.setMinimumSize(180,100)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area=self.rect().adjusted(12,12,-12,-12)
        p.setPen(self.palette().mid().color());p.drawRect(area)
        path=QPainterPath()
        for i in range(65):
            x=i/64;point=QPointF(area.left()+area.width()*x,area.bottom()-area.height()*x**self.power)
            path.moveTo(point) if i==0 else path.lineTo(point)
        p.setPen(QPen(self.palette().highlight().color(),2));p.drawPath(path)
        p.setBrush(self.palette().highlight());p.drawEllipse(QPointF(area.center().x(),area.bottom()-area.height()*.5**self.power),5,5)

    def _drag(self,event):
        area=self.rect().adjusted(12,12,-12,-12)
        value=max(.5**4,min(.5**.25,(area.bottom()-event.position().y())/max(1,area.height())))
        self.power=max(.25,min(4.,math.log(value)/math.log(.5)));self.changed.emit(self.power);self.update()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self._drag(event)

    def mouseMoveEvent(self,event):
        if event.buttons()&Qt.MouseButton.LeftButton:self._drag(event)

    def mouseReleaseEvent(self,event):self.committed.emit()


class RoutingEditor(_ValueEditor):
    validator=staticmethod(admit_routing)

    def __init__(self,parent=None):
        super().__init__(parent);self.active=(0,0)
        layout=QVBoxLayout(self);self.matrix=_MatrixCanvas(self);layout.addWidget(self.matrix)
        row=QHBoxLayout();layout.addLayout(row)
        self.caption=QLabel();row.addWidget(self.caption)
        self.gain=NoWheelSlider(Qt.Orientation.Horizontal);self.gain.setRange(0,200);row.addWidget(self.gain)
        self.curve=_PowerCurve(self);row.addWidget(self.curve)
        self.matrix.selected.connect(self.select)
        self.gain.valueChanged.connect(self._gain)
        self.gain.sliderReleased.connect(lambda:self.changed())
        self.curve.changed.connect(self._curve)
        self.curve.committed.connect(lambda:self.changed())
        self.curve.setToolTip('Drag the point to change the response curve. Left is quiet input; right is peak input.')

    def select(self,row,col):
        self.active=(row,col);self.refresh();self.matrix.update()

    def refresh(self):
        if self._value is None:return
        row,col=self.active;gain,power=self._value[TARGETS[row]][col]
        blocked=self.gain.blockSignals(True)
        try:self.gain.setValue(round(gain*100))
        finally:self.gain.blockSignals(blocked)
        self.curve.power=power;self.curve.update()
        self.caption.setText(f'{SOURCES[col]} → {TARGETS[row].title()}')
        self.matrix.update()

    def _gain(self,value):
        if self._loading or self._value is None:return
        row,col=self.active;self._value[TARGETS[row]][col][0]=value/100
        self.changed(commit=not self.gain.isSliderDown());self.matrix.update()

    def _curve(self,value):
        if self._loading or self._value is None:return
        row,col=self.active;self._value[TARGETS[row]][col][1]=value;self.changed(False)


class RibbonCardsEditor(_ValueEditor):
    validator=staticmethod(admit_ribbons)

    def __init__(self,parent=None):
        super().__init__(parent);layout=QVBoxLayout(self);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.fields=[];self.swatches=[]
        for index in range(3):
            panel=QWidget();body=QVBoxLayout(panel);fields={};swatches={}
            band=StyledComboBox();band.addItems(['All','Bass','Mids','Highs']);body.addWidget(band);fields['band']=band
            band.currentTextChanged.connect(lambda value,i=index:self._field(i,'band',value))
            for key,label,low,high in (('height','Height',.1,2.),('width','Width',.1,2.),('rate','Wave Rate',.25,2.),('phase','Phase',-2*math.pi,2*math.pi),('light','Light',0.,4.)):
                row=QHBoxLayout();row.addWidget(QLabel(label));spin=QDoubleSpinBox();spin.setRange(low,high);spin.setDecimals(3);spin.setSingleStep(.05);row.addWidget(spin);body.addLayout(row);fields[key]=spin
                spin.valueChanged.connect(lambda value,i=index,k=key:self._field(i,k,value,False))
                spin.editingFinished.connect(lambda:self.changed())
            for key,title in (('quiet','Quiet'),('peak','Peak')):
                row=QHBoxLayout();row.addWidget(QLabel(title));chips=[]
                for side in range(2):
                    chip=ColorSwatchButton(title=f'{title} '+('Centre' if side==0 else 'Edge'),show_alpha=False)
                    chip.color_changed.connect(lambda colour,i=index,k=key,j=side:self._colour(i,k,j,colour))
                    chips.append(chip);row.addWidget(chip)
                body.addLayout(row);swatches[key]=chips
            self.tabs.addTab(panel,f'Ribbon {index+1}');self.fields.append(fields);self.swatches.append(swatches)

    def refresh(self):
        if self._value is None:return
        for index,card in enumerate(self._value):
            for key,widget in self.fields[index].items():
                widget.setCurrentText(card[key]) if key=='band' else widget.setValue(card[key])
            for key in ('quiet','peak'):
                for side,chip in enumerate(self.swatches[index][key]):chip.set_color(display_colour(card[key][side]))

    def _field(self,index,key,value,commit=True):
        if self._loading or self._value is None:return
        self._value[index][key]=value;self.changed(commit)

    def _colour(self,index,key,side,value):
        if self._loading or self._value is None:return
        self._value[index][key][side]=linear_colour(value);self.changed()


class _GradientCanvas(QWidget):
    selected=Signal(int)
    moved=Signal(float)
    committed=Signal()
    clicked=Signal()

    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.dragging=False;self.start=None;self.setMinimumSize(300,78)

    def paintEvent(self,event):
        if self.owner._value is None:return
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        nodes=self.owner.nodes();gradient=QLinearGradient(12,0,self.width()-12,0)
        for position,colour in nodes:gradient.setColorAt(position,display_colour(colour))
        p.fillRect(QRectF(12,12,self.width()-24,30),gradient)
        for index,(position,colour) in enumerate(nodes):
            p.setPen(QPen(self.palette().highlight().color() if index==self.owner.active else self.palette().text().color(),2))
            p.setBrush(display_colour(colour));p.drawEllipse(QPointF(12+position*(self.width()-24),42),7,7)

    def mousePressEvent(self,event):
        if self.owner._value is None:return
        x=max(0.,min(1.,(event.position().x()-12)/(self.width()-24)))
        index=min(range(len(self.owner.nodes())),key=lambda i:abs(self.owner.nodes()[i][0]-x))
        self.selected.emit(index);self.dragging=True;self.start=event.position()

    def mouseMoveEvent(self,event):
        if self.dragging and (event.position()-self.start).manhattanLength()>3:
            self.moved.emit(max(0.,min(1.,(event.position().x()-12)/(self.width()-24))))

    def mouseReleaseEvent(self,event):
        if not self.dragging:return
        self.dragging=False
        if (event.position()-self.start).manhattanLength()<=3:self.clicked.emit()
        else:self.committed.emit()


class GradientNodesEditor(_ValueEditor):
    validator=staticmethod(admit_palette)

    def __init__(self,parent=None):
        super().__init__(parent);self.active=0
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row)
        self.state=StyledComboBox();self.state.addItems(['Quiet','Peak']);row.addWidget(self.state)
        self.swatch=ColorSwatchButton(title='Node Colour',show_alpha=False);row.addWidget(self.swatch)
        from PySide6.QtWidgets import QPushButton
        self.add=QPushButton('Add Node');self.remove=QPushButton('Remove Node');row.addWidget(self.add);row.addWidget(self.remove)
        self.canvas=_GradientCanvas(self);layout.addWidget(self.canvas)
        self.state.currentIndexChanged.connect(lambda:self.select(0))
        self.canvas.selected.connect(self.select);self.canvas.moved.connect(self.move)
        self.canvas.committed.connect(lambda:self.changed());self.canvas.clicked.connect(self.swatch.click)
        self.swatch.color_changed.connect(self.colour)
        self.add.clicked.connect(self.add_node);self.remove.clicked.connect(self.remove_node)

    def key(self):return 'low' if self.state.currentIndex()==0 else 'high'
    def nodes(self):return self._value[self.key()]

    def select(self,index):
        self.active=index;self.refresh()

    def refresh(self):
        if self._value is None:return
        self.active=min(self.active,len(self.nodes())-1)
        self.swatch.set_color(display_colour(self.nodes()[self.active][1]))
        self.add.setEnabled(len({p for nodes in self._value.values() for p,_ in nodes})<6)
        self.remove.setEnabled(len(self.nodes())>1)
        self.canvas.update()

    def move(self,position):
        nodes=self.nodes();old=nodes[self.active][0]
        lo=nodes[self.active-1][0]+.002 if self.active else 0.
        hi=nodes[self.active+1][0]-.002 if self.active<len(nodes)-1 else 1.
        # Shared positions move together, retaining the six-position bound across quiet and peak.
        other=self._value['high' if self.key()=='low' else 'low']
        both=sorted({p for values in self._value.values() for p,_ in values})
        slot=both.index(old)
        lo=max(lo,both[slot-1]+.002 if slot else 0.)
        hi=min(hi,both[slot+1]-.002 if slot<len(both)-1 else 1.)
        new=max(lo,min(hi,position));nodes[self.active][0]=new
        for node in other:
            if node[0]==old:node[0]=new
        self.changed(False);self.canvas.update()

    def colour(self,value):
        if self._loading or self._value is None:return
        self.nodes()[self.active][1]=linear_colour(value);self.changed();self.canvas.update()

    def add_node(self):
        if self._value is None:return
        positions=sorted({p for nodes in self._value.values() for p,_ in nodes})
        if len(positions)>=6:return
        gaps=list(zip([0.]+positions,positions+[1.]))
        left,right=max(gaps,key=lambda pair:pair[1]-pair[0]);position=(left+right)/2
        if right-left<.004:return
        for key,nodes in self._value.items():
            nearest=min(nodes,key=lambda node:abs(node[0]-position))
            nodes.append([position,list(nearest[1])]);nodes.sort(key=lambda node:node[0])
        self.active=next(i for i,node in enumerate(self.nodes()) if node[0]==position)
        self.changed();self.refresh()

    def remove_node(self):
        if self._value is None or len(self.nodes())<=1:return
        del self.nodes()[self.active];self.active=0;self.changed();self.refresh()
