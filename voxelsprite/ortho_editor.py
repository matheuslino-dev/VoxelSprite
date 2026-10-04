"""Edição 2D de projeções ortográficas em pixels, sem dependência de OpenGL."""
from collections import deque
import numpy as np
from PySide6.QtCore import Qt,Signal,QPointF
from PySide6.QtGui import QImage,QPainter,QColor,QPen
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QSpinBox,
    QTabWidget,QScrollArea,QCheckBox,QDialogButtonBox,QColorDialog,QMessageBox)
from .exports import orthographic_views
from .dialogs import NAMES
from .document import Document
from .core import voxelize,fit_view

class PixelCanvas(__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget):
    """Canvas de pixels com ferramentas simples e histórico local por vista."""

    changed=Signal();picked=Signal(object)
    def __init__(self,array):
        super().__init__();self.array=array.copy();self.scale=8;self.tool='paint';self.color=np.array([255,70,160],dtype='uint8');self.size=1
        self.stroke=False;self.before=None;self.history=[];self.redos=[];self.last=None;self.update_size()
    def update_size(self):self.setFixedSize(self.array.shape[1]*self.scale,self.array.shape[0]*self.scale);self.update()
    def paintEvent(self,event):
        """Composita a transparência sobre quadriculado e desenha a grade de pixels."""
        h,w,_=self.array.shape;yy,xx=np.indices((h,w));bg=np.where(((xx//4+yy//4)%2)[...,None],65,43)
        a=self.array[:,:,3:4]/255;rgb=np.ascontiguousarray(self.array[:,:,:3]*a+bg*(1-a),dtype='uint8')
        image=QImage(rgb.data,w,h,w*3,QImage.Format.Format_RGB888).copy()
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False);p.drawImage(self.rect(),image)
        if self.scale>=8:
            p.setPen(QPen(QColor(0,0,0,45),1))
            for x in range(w+1):p.drawLine(x*self.scale,0,x*self.scale,h*self.scale)
            for y in range(h+1):p.drawLine(0,y*self.scale,w*self.scale,y*self.scale)
        p.end()
    def point(self,event):return int(event.position().x()//self.scale),int(event.position().y()//self.scale)
    def dab(self,x,y):
        """Aplica uma ação num pixel: amostrar, preencher, apagar ou pintar."""
        h,w,_=self.array.shape
        if not (0<=x<w and 0<=y<h):return
        if self.tool=='pick':self.picked.emit(self.array[y,x,:3].copy());return
        if self.tool=='fill':
            # Busca em largura limita o balde aos pixels vizinhos com a cor inicial.
            old=self.array[y,x].copy();new=np.array([*self.color,255],dtype='uint8')
            if np.array_equal(old,new):return
            q=deque([(x,y)]);seen={(x,y)}
            while q:
                u,v=q.popleft()
                if not np.array_equal(self.array[v,u],old):continue
                self.array[v,u]=new
                for a,b in [(u-1,v),(u+1,v),(u,v-1),(u,v+1)]:
                    if 0<=a<w and 0<=b<h and (a,b) not in seen:seen.add((a,b));q.append((a,b))
        else:
            start=-self.size//2+1 if self.size%2==0 else -(self.size//2)
            for u in range(x+start,x+start+self.size):
                for v in range(y+start,y+start+self.size):
                    if 0<=u<w and 0<=v<h:self.array[v,u]=[0,0,0,0] if self.tool=='erase' else [*self.color,255]
        self.update()
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        self.stroke=True;self.before=self.array.copy();self.last=self.point(event);self.dab(*self.last)
    def mouseMoveEvent(self,event):
        if not self.stroke or not event.buttons()&Qt.MouseButton.LeftButton:return
        current=self.point(event)
        if self.tool not in ('fill','pick'):
            a=np.array(self.last);b=np.array(current);n=int(max(abs(b-a)))+1
            for x,y in np.rint(np.linspace(a,b,n)).astype(int):self.dab(x,y)
        self.last=current
    def mouseReleaseEvent(self,event):
        if not self.stroke:return
        self.stroke=False
        if self.before is not None and not np.array_equal(self.before,self.array):
            self.history.append(self.before);self.history=self.history[-30:];self.redos.clear();self.changed.emit()
        self.before=None
    def undo(self):
        if self.history:self.redos.append(self.array.copy());self.array=self.history.pop();self.changed.emit();self.update()
    def redo(self):
        if self.redos:self.history.append(self.array.copy());self.array=self.redos.pop();self.changed.emit();self.update()

class OrthoEditor(QDialog):
    """Permite pintar seis projeções e reconstruir delas um novo documento 3D."""

    def __init__(self,doc,color,parent=None):
        super().__init__(parent);self.setWindowTitle('3D ORTHO · editar vistas em pixels');self.resize(840,680);self.result_document=None
        self.color=np.array(color,dtype='uint8');self.depth=doc.occupied.shape[2]
        if max(doc.occupied.shape)>128 or self.depth>64:
            raise ValueError('O editor de vistas aceita largura/altura até 128 e profundidade até 64. Reduza a grade antes de usar este modo.')
        layout=QVBoxLayout(self);note=QLabel('Pinte uma ou mais vistas. Desative as que não devem limitar o volume.\nAplicar reconstrói as silhuetas e pode preencher cavidades escondidas; salve o projeto 3D antes.');note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();self.tool=QComboBox();self.tool.addItems(['Pincel','Borracha','Balde','Conta-gotas']);row.addWidget(self.tool)
        self.brush=QSpinBox();self.brush.setRange(1,16);row.addWidget(QLabel('Tamanho'));row.addWidget(self.brush)
        self.zoom=QSpinBox();self.zoom.setRange(2,24);self.zoom.setValue(8);row.addWidget(QLabel('Zoom'));row.addWidget(self.zoom)
        self.color_button=QPushButton('COR');self.color_button.clicked.connect(self.choose_color);row.addWidget(self.color_button)
        undo=QPushButton('Desfazer');undo.clicked.connect(lambda:self.current().undo());row.addWidget(undo)
        redo=QPushButton('Refazer');redo.clicked.connect(lambda:self.current().redo());row.addWidget(redo);layout.addLayout(row)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1);self.canvases={};self.enabled={}
        views=orthographic_views(doc)
        for key,image in views.items():
            container=__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget();col=QVBoxLayout(container)
            active=QCheckBox('Usar esta vista na reconstrução');active.setChecked(bool(np.array(image)[:,:,3].any()));col.addWidget(active);self.enabled[key]=active
            canvas=PixelCanvas(np.array(image));canvas.color=self.color.copy();canvas.picked.connect(self.set_color);self.canvases[key]=canvas
            canvas.changed.connect(lambda k=key:self.enabled[k].setChecked(bool(self.canvases[k].array[:,:,3].any())))
            scroll=QScrollArea();scroll.setAlignment(Qt.AlignmentFlag.AlignCenter);scroll.setWidget(canvas);col.addWidget(scroll,1);self.tabs.addTab(container,NAMES[key])
        self.tool.currentIndexChanged.connect(self.controls_changed);self.brush.valueChanged.connect(self.controls_changed);self.zoom.valueChanged.connect(self.controls_changed)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Apply).setText('Reconstruir 3D');buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.set_color(self.color)
    def current(self):return list(self.canvases.values())[self.tabs.currentIndex()]
    def controls_changed(self,*args):
        """Propaga ferramenta, tamanho e zoom para todos os canvases."""
        for canvas in self.canvases.values():canvas.tool=['paint','erase','fill','pick'][self.tool.currentIndex()];canvas.size=self.brush.value();canvas.scale=self.zoom.value();canvas.update_size()
    def set_color(self,color):
        self.color=np.array(color,dtype='uint8');self.color_button.setStyleSheet(f'background:{QColor(*map(int,color)).name()};')
        for canvas in self.canvases.values():canvas.color=self.color.copy()
    def choose_color(self):
        c=QColorDialog.getColor(QColor(*map(int,self.color)),self,'Cor')
        if c.isValid():self.set_color(c.getRgb()[:3])
    def reconstruct(self):
        """Usa apenas vistas ativas para gerar um volume por interseção de silhuetas."""
        images={key:canvas.array.copy() for key,canvas in self.canvases.items() if self.enabled[key].isChecked() and canvas.array[:,:,3].any()}
        if not images:raise ValueError('Pinte ou ative pelo menos uma vista.')
        if 'front' in images:front=images.pop('front')
        elif 'back' in images:front=images['back'][:,::-1].copy()
        else:
            shape=self.canvases['front'].array.shape;front=np.full(shape,255,dtype='uint8');front[:,:,:3]=self.color
        mesh=voxelize(front,self.depth,0,128,images,True,'dominant')
        return Document.from_mesh(mesh,padding=0)
    def apply(self):
        """Reconstrói o modelo e fecha o diálogo; mostra erros sem perder as vistas."""
        try:self.result_document=self.reconstruct();self.accept()
        except Exception as exc:QMessageBox.warning(self,'Reconstrução',str(exc))
