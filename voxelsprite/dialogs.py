from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap,QImage
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFileDialog,
    QSpinBox,QDoubleSpinBox,QComboBox,QCheckBox,QDialogButtonBox,QMessageBox,QGroupBox)
from .core import read_sprite

NAMES={'front':'Frente','back':'Costas','left':'Esquerda','right':'Direita','top':'Topo','bottom':'Base'}

def thumbnail(path,size=80):
    a,_=read_sprite(path,128);h,w,_=a.shape;yy,xx=np.indices((h,w));bg=np.where(((xx//4+yy//4)%2)[...,None],65,45)
    alpha=a[:,:,3:4]/255
    rgb=np.ascontiguousarray(a[:,:,:3]*alpha+bg*(1-alpha),dtype='uint8')
    return QPixmap.fromImage(QImage(rgb.data,w,h,w*3,QImage.Format.Format_RGB888).copy()).scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)

class ImportDialog(QDialog):
    def __init__(self,parent=None,paths=None):
        super().__init__(parent);self.setWindowTitle('Importar vistas ortográficas');self.resize(620,600)
        self.paths=dict(paths or {});self.thumbs={};self.labels={}
        layout=QVBoxLayout(self)
        help=QLabel('Use até seis PNGs separados. Todas as vistas são opcionais; carregue ao menos uma.\nAlinhe as telas: mesma escala, cabeça e pés na mesma altura.');help.setWordWrap(True);layout.addWidget(help)
        grid=QGridLayout();layout.addLayout(grid)
        for i,(key,name) in enumerate(NAMES.items()):
            box=QGroupBox(name);col=QVBoxLayout(box)
            thumb=QLabel('SEM IMAGEM');thumb.setFixedHeight(82);thumb.setAlignment(Qt.AlignmentFlag.AlignCenter);col.addWidget(thumb);self.thumbs[key]=thumb
            label=QLabel('Matemática');label.setMaximumWidth(166);col.addWidget(label);self.labels[key]=label
            row=QHBoxLayout();add=QPushButton('Abrir');clear=QPushButton('×');clear.setFixedWidth(30)
            add.clicked.connect(lambda checked=False,k=key:self.choose(k));clear.clicked.connect(lambda checked=False,k=key:self.remove(k))
            row.addWidget(add);row.addWidget(clear);col.addLayout(row);grid.addWidget(box,i//3,i%3)
        form=QGridLayout();layout.addLayout(form)
        self.resolution=QComboBox();self.resolution.addItems(['32','48','64','96','128']);self.resolution.setCurrentText('64')
        self.depth=QSpinBox();self.depth.setRange(1,64);self.depth.setValue(16)
        self.roundness=QDoubleSpinBox();self.roundness.setRange(0,1);self.roundness.setSingleStep(.1);self.roundness.setValue(.6)
        self.alpha=QSpinBox();self.alpha.setRange(1,255);self.alpha.setValue(128)
        for i,(label,control) in enumerate([('Resolução máxima',self.resolution),('Profundidade',self.depth),('Arredondamento*',self.roundness),('Corte alfa',self.alpha)]):
            form.addWidget(QLabel(label),i//2,i%2*2);form.addWidget(control,i//2,i%2*2+1)
        self.mirror=QCheckBox('Espelhar cores da lateral ausente');self.mirror.setChecked(True);layout.addWidget(self.mirror)
        self.fallback=QComboBox();self.fallback.addItems(['Vistas ausentes: cores dominantes','Vistas ausentes: repetir a frente']);layout.addWidget(self.fallback)
        note=QLabel('* Arredondamento só sem lateral, topo ou base. Vistas fornecidas recortam o volume.\nTopo: frente na parte inferior da imagem. Base: frente na parte superior.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Gerar modelo');buttons.accepted.connect(self.accept_checked);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.refresh()
    def choose(self,key):
        p,_=QFileDialog.getOpenFileName(self,'Abrir '+NAMES[key],'','Imagens (*.png *.webp *.bmp *.jpg *.jpeg)')
        if p:
            try:read_sprite(p,128);self.paths[key]=p;self.refresh()
            except Exception as exc:QMessageBox.warning(self,'Imagem inválida',str(exc))
    def remove(self,key):self.paths.pop(key,None);self.refresh()
    def refresh(self):
        for key in NAMES:
            p=self.paths.get(key)
            if p:self.thumbs[key].setPixmap(thumbnail(p));self.labels[key].setText(Path(p).name);self.labels[key].setToolTip(str(p))
            else:self.thumbs[key].clear();self.thumbs[key].setText('SEM IMAGEM');self.labels[key].setText('Matemática')
        self.roundness.setEnabled(not bool({'left','right','top','bottom'}&self.paths.keys()))
    def accept_checked(self):
        if not self.paths:QMessageBox.warning(self,'Importar','Carregue pelo menos uma vista.');return
        self.accept()
    def options(self):
        return dict(paths=self.paths,resolution=int(self.resolution.currentText()),depth=self.depth.value(),roundness=self.roundness.value(),alpha=self.alpha.value(),mirror=self.mirror.isChecked(),fallback='dominant' if self.fallback.currentIndex()==0 else 'front')

class ExportDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Exportar');layout=QVBoxLayout(self);self.resize(410,340)
        self.kind=QComboBox();self.kind.addItems(['OBJ + MTL + atlas PNG','PNG · ângulo atual (reenquadrado)','Spritesheet · 8 direções','Spritesheet · 16 direções','GIF · rotação 360°','6 vistas ortográficas PNG','RPG Maker · personagem estático'])
        layout.addWidget(QLabel('Formato'));layout.addWidget(self.kind)
        self.size=QComboBox();self.size.addItems(['64','128','256','512']);self.size.setCurrentText('128');layout.addWidget(QLabel('Tamanho de cada quadro (px)'));layout.addWidget(self.size)
        self.pitch=QDoubleSpinBox();self.pitch.setRange(0,89);self.pitch.setValue(30);layout.addWidget(QLabel('Elevação das direções / GIF (graus)'));layout.addWidget(self.pitch)
        self.frames=QSpinBox();self.frames.setRange(8,64);self.frames.setValue(16);layout.addWidget(QLabel('Quadros do GIF'));layout.addWidget(self.frames)
        self.duration=QSpinBox();self.duration.setRange(20,1000);self.duration.setValue(100);layout.addWidget(QLabel('Duração por quadro do GIF (ms)'));layout.addWidget(self.duration)
        note=QLabel('PNG usa transparência. Spritesheets: ordem horária, começando pela frente.\nRPG Maker: 3×4, poses repetidas; não cria animação de caminhada.');note.setWordWrap(True);layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self.update_fields);self.update_fields()
    def update_fields(self):
        i=self.kind.currentIndex();self.size.setEnabled(i not in (0,5));self.pitch.setEnabled(i in (2,3,4,6));self.frames.setEnabled(i==4);self.duration.setEnabled(i==4)
