"""Janela principal: conecta os controles Qt ao documento, viewport e exportadores."""
from pathlib import Path
import math
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt,QThread,Signal,QTimer,QUrl
from PySide6.QtGui import QColor,QAction,QKeySequence,QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
    QFrame,QLabel,QPushButton,QSpinBox,QDoubleSpinBox,QSlider,QComboBox,QCheckBox,QColorDialog,
    QFileDialog,QMessageBox,QInputDialog,QDialog,QDialogButtonBox,QScrollArea,QProgressBar,QProgressDialog)
from .document import Document,build_from_images,save_project,load_project,MAX_VOXELS
from .viewport import Viewport
from .dialogs import ImportDialog,ExportDialog
from .exports import export_atlas_obj,export_orthographic,sprite_sheet,save_gif
from .style import STYLE,Banner,tool_icon
from .ortho_editor import OrthoEditor

ROOT=Path(__file__).resolve().parent.parent

class Worker(QThread):
    """Executa uma operação demorada fora da thread da interface."""

    completed=Signal(object);failed=Signal(str)
    def __init__(self,fn):super().__init__();self.fn=fn
    def run(self):
        """Emite o resultado ou a mensagem de erro para a janela principal."""
        try:self.completed.emit(self.fn())
        except Exception as exc:self.failed.emit(str(exc))

class MainWindow(QMainWindow):
    """Coordena a interface e encaminha ações para os módulos especializados."""

    def __init__(self):
        """Monta painéis, ferramentas, atalhos e conexões entre sinais e slots."""
        super().__init__();self.setWindowTitle('VoxelSprite Studio 2.0');self.resize(1440,900);self.setMinimumSize(1080,720);self.setStyleSheet(STYLE)
        self.doc=Document();self.project_path=None;self.dirty=False;self.worker=None;self.busy=False
        self.paths={};self.brush_color=np.array([239,76,155],dtype='uint8');self.last_anchor=None;self.stroke_seen=set();self.stroke_tool='paint'
        self.setAcceptDrops(True)
        root=QWidget();self.setCentralWidget(root);self.root_layout=QVBoxLayout(root);self.root_layout.setContentsMargins(0,0,0,0);self.root_layout.setSpacing(0)
        self.root_layout.addWidget(Banner());body=QHBoxLayout();body.setSpacing(0);self.root_layout.addLayout(body,1)
        self.left=QWidget();self.left.setObjectName('rail');self.left.setFixedWidth(84);tools=QVBoxLayout(self.left);tools.setContentsMargins(7,9,7,9);tools.setSpacing(6)
        body.addWidget(self.left)
        tools.addWidget(QLabel('TAMANHO'));self.brush_size=QSpinBox();self.brush_size.setRange(1,16);self.brush_size.setValue(1);tools.addWidget(self.brush_size)
        tools.addWidget(QLabel('OPAC. %'));self.opacity=QSpinBox();self.opacity.setRange(1,100);self.opacity.setValue(100);tools.addWidget(self.opacity)
        self.tool_buttons={}
        for key,label,shortcut in [('paint','Pintar','P'),('add','Adicionar voxel','V'),('erase','Apagar voxel','E'),('pick','Conta-gotas','I'),('select','Selecionar','M'),('fill','Balde','B'),('orbit','Navegar','H')]:
            button=QPushButton();button.setIcon(tool_icon(key));button.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(32,32));button.setFixedHeight(43);button.setCheckable(True);button.setToolTip(f'{label} ({shortcut})')
            button.clicked.connect(lambda checked=False,k=key:self.set_tool(k));tools.addWidget(button);self.tool_buttons[key]=button
            self.shortcut(shortcut,lambda k=key:self.set_tool(k))
        self.color_button=QPushButton();self.color_button.setFixedHeight(34);self.color_button.setToolTip('Escolher cor');self.color_button.clicked.connect(self.choose_color);tools.addWidget(self.color_button);self.update_color()
        self.palette_widget=QWidget();self.palette_layout=QGridLayout(self.palette_widget);self.palette_layout.setContentsMargins(0,0,0,0);self.palette_layout.setSpacing(2);tools.addWidget(self.palette_widget)
        tools.addStretch()
        self.undo_button=QPushButton('↶');self.undo_button.setToolTip('Desfazer · Ctrl+Z');self.undo_button.clicked.connect(self.undo)
        self.redo_button=QPushButton('↷');self.redo_button.setToolTip('Refazer · Ctrl+Y');self.redo_button.clicked.connect(self.redo)
        history=QHBoxLayout();history.setSpacing(2);history.addWidget(self.undo_button);history.addWidget(self.redo_button);tools.addLayout(history)
        center=QVBoxLayout();center.setSpacing(0);body.addLayout(center,1)
        self.viewport=Viewport();self.viewport.set_document(self.doc);center.addWidget(self.viewport,1)
        self.viewport.failed.connect(self.gl_error);self.viewport.stroke_started.connect(self.begin_stroke);self.viewport.hit.connect(self.edit_hit);self.viewport.stroke_finished.connect(self.end_stroke);self.viewport.selection_made.connect(self.select_rect);self.viewport.selection_transform.connect(self.drag_selection)
        self.refresh_timer=QTimer(self);self.refresh_timer.setSingleShot(True);self.refresh_timer.setInterval(40);self.refresh_timer.timeout.connect(self.refresh_mesh)
        # Camera rail along the bottom, as in the user's reference.
        bottom=QWidget();bottom.setObjectName('rail');bar=QHBoxLayout(bottom);bar.setContentsMargins(8,7,8,7);bar.setSpacing(4)
        for text,yaw in [('S',0),('SO',45),('O',90),('NO',135),('N',180),('NE',225),('L',270),('SE',315)]:
            b=QPushButton(text);b.setFixedWidth(34);b.setToolTip(f'Vista orbital {yaw}°');b.clicked.connect(lambda checked=False,y=yaw:self.set_camera(y,30));bar.addWidget(b)
        bar.addStretch()
        self.camera=QComboBox();self.camera.addItems(['ISOMÉTRICA','FRENTE','COSTAS','ESQUERDA','DIREITA','TOPO','BASE']);self.camera.currentIndexChanged.connect(self.camera_preset);bar.addWidget(self.camera)
        bg=QPushButton('BG');bg.setToolTip('Cor de fundo');bg.clicked.connect(self.choose_background);bar.addWidget(bg)
        center.addWidget(bottom)
        self.right_scroll=QScrollArea();self.right_scroll.setWidgetResizable(True);self.right_scroll.setFixedWidth(228);self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right=QWidget();right.setObjectName('rail');panel=QVBoxLayout(right);panel.setContentsMargins(12,12,12,10);panel.setSpacing(8);self.right_scroll.setWidget(right)
        right_outer=QWidget();right_outer.setFixedWidth(228);right_layout=QVBoxLayout(right_outer);right_layout.setContentsMargins(0,0,0,0);right_layout.setSpacing(0);right_layout.addWidget(self.right_scroll,1);body.addWidget(right_outer)
        self.add_button(panel,'EXEMPLOS',self.example_dialog)
        self.add_button(panel,'IMPORTAR VISTAS',self.import_dialog)
        self.add_button(panel,'3D ORTHO · EDITAR 2D',self.open_ortho)
        self.add_button(panel,'NOVO / LIMPAR',self.new_document,'danger')
        self.section(panel,'VISUALIZAÇÃO')
        self.snap=self.add_button(panel,'ENQUADRAR',lambda:self.viewport.reset_camera())
        row=QHBoxLayout();row.addWidget(QLabel('GRADE →'));self.grid_size=QComboBox();self.grid_size.addItems(['16','32','64','96','128']);self.grid_size.setCurrentText('32');row.addWidget(self.grid_size);panel.addLayout(row)
        self.add_button(panel,'APLICAR TAMANHO',self.resize_grid)
        self.grid=QCheckBox('Mostrar grade');self.grid.setChecked(True);self.grid.toggled.connect(self.update_view);panel.addWidget(self.grid)
        self.outline=QCheckBox('Contorno da silhueta');self.outline.toggled.connect(self.update_view);panel.addWidget(self.outline)
        self.add_button(panel,'COR DO CONTORNO',self.choose_outline)
        self.lighting=QCheckBox('Iluminação');self.lighting.setChecked(True);self.lighting.toggled.connect(self.update_view);panel.addWidget(self.lighting)
        self.ortho=QCheckBox('Câmera ortográfica');self.ortho.setChecked(True);self.ortho.toggled.connect(self.update_view);panel.addWidget(self.ortho)
        self.pixel=QComboBox();self.pixel.addItems(['PIXEL ART · 2×','PIXEL ART · 3×','3D · resolução total']);self.pixel.currentIndexChanged.connect(self.update_view);panel.addWidget(self.pixel)
        self.section(panel,'LUZ')
        self.light_yaw=QSlider(Qt.Orientation.Horizontal);self.light_yaw.setRange(-180,180);self.light_yaw.setValue(-22);self.light_yaw.valueChanged.connect(self.update_view);panel.addWidget(QLabel('Direção'));panel.addWidget(self.light_yaw)
        self.light_pitch=QSlider(Qt.Orientation.Horizontal);self.light_pitch.setRange(0,90);self.light_pitch.setValue(40);self.light_pitch.valueChanged.connect(self.update_view);panel.addWidget(QLabel('Elevação'));panel.addWidget(self.light_pitch)
        self.section(panel,'SELEÇÃO')
        self.selection_label=QLabel('0 voxels');panel.addWidget(self.selection_label)
        self.add_button(panel,'MOVER / COPIAR',self.move_dialog)
        self.add_button(panel,'APAGAR SELEÇÃO',self.delete_selection)
        self.add_button(panel,'SOLTAR SELEÇÃO',self.clear_selection)
        hint=QLabel('ESQ: ferramenta\nDIR: girar\nMEIO / Espaço: mover\nRODA: zoom\nAlt: capturar cor\nShift: linha / somar seleção\nCtrl: apagar ao pintar');hint.setObjectName('muted');hint.setWordWrap(True);panel.addWidget(hint)
        panel.addStretch()
        actions=QWidget();actions.setObjectName('rail');action_layout=QVBoxLayout(actions);action_layout.setContentsMargins(12,8,12,8);action_layout.setSpacing(5)
        self.add_button(action_layout,'EXPORTAR',self.export_dialog,'primary')
        self.add_button(action_layout,'SALVAR PROJETO',self.save)
        self.add_button(action_layout,'ABRIR PROJETO',self.load)
        right_layout.addWidget(actions)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setTextVisible(False);self.progress.hide();self.root_layout.addWidget(self.progress)
        self.stats=QLabel();self.statusBar().addPermanentWidget(self.stats)
        self.menu_setup();self.set_tool('paint');self.refresh_palette();self.update_status()
        self.statusBar().showMessage('Abra EXEMPLOS, importe vistas ou adicione voxels sobre a grade vazia.')
        for key,fn in [('Ctrl+Z',self.undo),('Ctrl+Y',self.redo),('Ctrl+Shift+Z',self.redo),('Ctrl+S',self.save),('Ctrl+O',self.load),('Ctrl+N',self.new_document),('Ctrl+E',self.export_dialog),('Delete',self.delete_selection),('Escape',self.clear_selection),('Ctrl+A',self.select_all)]:self.shortcut(key,fn)

    def shortcut(self,key,fn):
        action=QAction(self);action.setShortcut(QKeySequence(key));action.triggered.connect(fn);self.addAction(action)
    def menu_setup(self):
        file=self.menuBar().addMenu('Arquivo')
        for text,fn in [('Novo',self.new_document),('Importar vistas…',self.import_dialog),('Abrir projeto…',self.load),('Salvar',self.save),('Salvar como…',lambda:self.save(True)),('Exportar…',self.export_dialog)]:file.addAction(text,fn)
        edit=self.menuBar().addMenu('Editar')
        for text,fn in [('Desfazer',self.undo),('Refazer',self.redo),('Selecionar tudo',self.select_all),('Mover / copiar seleção…',self.move_dialog),('Soltar seleção',self.clear_selection)]:edit.addAction(text,fn)
        help=self.menuBar().addMenu('Ajuda');help.addAction('Guia em português',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT/'LEIA-ME.md'))))
        help.addAction('Sobre',lambda:QMessageBox.information(self,'VoxelSprite Studio','VoxelSprite Studio 2.0\nImplementação independente em Python.\nInterface inspirada na referência fornecida do PixZels.\nSem vínculo com o autor do PixZels.'))
    @staticmethod
    def section(layout,text):
        label=QLabel(text);label.setObjectName('section');layout.addWidget(label)
    @staticmethod
    def add_button(layout,text,fn,style=None):
        button=QPushButton(text);button.clicked.connect(fn)
        if style:button.setObjectName(style)
        layout.addWidget(button);return button
    def error(self,message):
        self.statusBar().showMessage('Não foi possível concluir a operação.');QMessageBox.warning(self,'VoxelSprite',str(message))
    def gl_error(self,message):self.statusBar().showMessage('OpenGL indisponível. '+str(message))
    def mark_dirty(self):self.dirty=True;self.setWindowTitle('VoxelSprite Studio 2.0 • alterações não salvas')
    def confirm_discard(self):
        if not self.dirty:return True
        answer=QMessageBox.question(self,'Alterações não salvas','Salvar seu projeto antes de continuar?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if answer==QMessageBox.StandardButton.Cancel:return False
        return self.save() if answer==QMessageBox.StandardButton.Save else True
    def install_document(self,doc,clean=False):
        self.refresh_timer.stop();self.doc=doc;self.viewport.set_document(doc);self.last_anchor=None;self.project_path=None
        self.dirty=not clean;self.setWindowTitle('VoxelSprite Studio 2.0'+(' • alterações não salvas' if self.dirty else ''))
        self.refresh_palette();self.update_status()
    def new_document(self):
        if self.busy or not self.confirm_discard():return
        side=int(self.grid_size.currentText());self.install_document(Document((side,side,side)),True);self.paths={};self.set_tool('add')
    def resize_grid(self):
        if self.busy:return
        try:
            doc=self.doc.resize(int(self.grid_size.currentText()));self.install_document(doc)
            self.statusBar().showMessage('Grade alterada. Histórico reiniciado; salve uma cópia para manter a versão anterior.')
        except Exception as exc:self.error(exc)
    def run_job(self,fn,handler,message):
        """Desativa controles enquanto uma tarefa de importação/exportação executa."""
        if self.busy:return
        self.busy=True;self.centralWidget().setEnabled(False);self.menuBar().setEnabled(False);self.progress.show();self.statusBar().showMessage(message)
        self.worker=Worker(fn);self.worker.completed.connect(handler);self.worker.failed.connect(self.error);self.worker.finished.connect(self.job_finished);self.worker.start()
    def job_finished(self):
        self.busy=False;self.centralWidget().setEnabled(True);self.menuBar().setEnabled(True);self.progress.hide();self.worker.deleteLater();self.worker=None
    def import_dialog(self):
        if self.busy:return
        dialog=ImportDialog(self,self.paths)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if not self.confirm_discard():return
        options=dialog.options();self.paths=dict(options['paths'])
        self.run_job(lambda:build_from_images(**options),self.install_document,'Reconstruindo o volume a partir das vistas…')
    def open_ortho(self):
        if self.busy:return
        try:
            dialog=OrthoEditor(self.doc,self.brush_color,self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                if not self.confirm_discard():return
                self.install_document(dialog.result_document);self.paths={}
        except Exception as exc:self.error(exc)

    def example_dialog(self):
        if self.busy:return
        choice,ok=QInputDialog.getItem(self,'Exemplos','Escolha um modelo',['Personagem · 4 vistas','Cogumelo · 1 vista','Árvore · 1 vista'],0,False)
        if not ok or not self.confirm_discard():return
        self.load_example(['Personagem · 4 vistas','Cogumelo · 1 vista','Árvore · 1 vista'].index(choice))
    def load_example(self,index=0):
        if index==0:paths={key:ROOT/'exemplos'/'personagem'/f'{key}.png' for key in ('front','back','left','right')}
        else:paths={'front':ROOT/'exemplos'/('cogumelo.png' if index==1 else 'arvore.png')}
        self.paths=paths;self.run_job(lambda:build_from_images(paths),self.install_document,'Abrindo exemplo…')
    def set_tool(self,key):
        if self.busy:return
        self.viewport.tool=key
        for name,button in self.tool_buttons.items():button.setChecked(key==name)
        self.viewport.update();self.statusBar().showMessage({'paint':'Pinte faces. Shift + clique: linha. Alt: capturar cor.','add':'Clique em uma face para adicionar volume ou no chão para começar.','erase':'Clique para apagar voxels.','pick':'Clique em uma face para capturar sua cor.','select':'Arraste um retângulo: seleciona voxels em todas as profundidades. Shift soma à seleção.','fill':'Preenche faces conectadas, coplanares e da mesma cor.','orbit':'Arraste para girar; botão do meio move a câmera.'}[key])
    def update_color(self):
        hexcolor=QColor(*map(int,self.brush_color)).name();self.color_button.setStyleSheet(f'background:{hexcolor};border:3px solid #77717c;');self.color_button.setToolTip(hexcolor)
    def set_color(self,color):self.brush_color=np.array(color,dtype='uint8');self.update_color()
    def choose_color(self):
        color=QColorDialog.getColor(QColor(*map(int,self.brush_color)),self,'Cor do pincel')
        if color.isValid():self.set_color(color.getRgb()[:3])
    def refresh_palette(self):
        while self.palette_layout.count():
            item=self.palette_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        mesh=self.viewport.mesh
        if mesh is not None and len(mesh.colors):
            colors,counts=np.unique(mesh.colors,axis=0,return_counts=True);colors=colors[np.argsort(-counts)[:12]]
        else:colors=np.array([[239,76,155],[83,217,189],[235,211,166],[73,85,144],[244,244,240],[30,30,35]])
        for i,color in enumerate(colors):
            button=QPushButton();button.setFixedSize(20,18);button.setStyleSheet(f'background:{QColor(*map(int,color)).name()};padding:0;border:1px solid #17171a;');button.clicked.connect(lambda checked=False,c=color.copy():self.set_color(c));self.palette_layout.addWidget(button,i//3,i%3)
    def begin_stroke(self):
        if self.busy:return
        self.doc.begin();self.stroke_seen=set();self.stroke_tool=self.viewport.tool
    def edit_hit(self,hit,modifiers):
        """Traduz um clique no viewport para ferramenta, modificadores e edição."""
        if self.busy:return
        point,face,ground=hit;tool=self.viewport.tool
        mods=Qt.KeyboardModifier(modifiers)
        if mods&Qt.KeyboardModifier.AltModifier:tool='pick'
        elif mods&Qt.KeyboardModifier.ControlModifier and tool=='paint':tool='erase'
        if tool=='pick':
            if not ground:self.set_color(self.doc.colors[point][face])
            return
        if tool=='orbit' or tool=='select':return
        tag=(point,face,tool)
        if tag in self.stroke_seen:return
        self.stroke_seen.add(tag)
        try:
            if ground:
                if tool=='add':self.doc.set_voxel(point,True,np.tile(self.brush_color,(6,1)))
                else:return
            elif tool=='fill':self.doc.fill(point,face,self.brush_color,self.opacity.value()/100)
            else:
                points=[point]
                if mods&Qt.KeyboardModifier.ShiftModifier and self.last_anchor and self.last_anchor[1]==face:
                    a=np.array(self.last_anchor[0]);b=np.array(point);count=int(np.max(abs(b-a)))+1
                    points=[tuple(p) for p in np.unique(np.rint(np.linspace(a,b,count)).astype(int),axis=0)]
                for p in points:self.doc.brush(p,face,self.brush_size.value(),tool,self.brush_color,self.opacity.value()/100)
            self.last_anchor=(point,face)
            if not self.refresh_timer.isActive():self.refresh_timer.start()
        except Exception as exc:self.doc.rollback();self.error(exc)
    def end_stroke(self):
        """Valida e confirma o traço inteiro como uma única operação de histórico."""
        self.refresh_timer.stop()
        try:
            if int(self.doc.occupied.sum())>MAX_VOXELS:raise ValueError('Limite de um milhão de voxels atingido.')
            self.doc.mesh() # Validate face budget before recording an edit.
            if self.doc.commit():self.mark_dirty()
        except Exception as exc:self.doc.rollback();self.error(exc)
        self.refresh_mesh()
    def refresh_mesh(self):
        try:self.viewport.set_document(self.doc,False);self.update_status()
        except Exception as exc:
            self.doc.rollback();self.viewport.set_document(self.doc,False);self.error(exc)
    def update_status(self):
        mesh=self.viewport.mesh;self.stats.setText((f'{int(self.doc.occupied.sum()):,} voxels | {len(mesh.quads) if mesh else 0:,} faces | '+ '×'.join(map(str,(self.doc.occupied.shape[1],self.doc.occupied.shape[0],self.doc.occupied.shape[2])))).replace(',','.'))
        self.selection_label.setText(f'{len(self.doc.selection)} voxels selecionados')
        self.undo_button.setEnabled(bool(self.doc.history));self.redo_button.setEnabled(bool(self.doc.redos))
    def undo(self):
        if not self.busy and self.doc.undo():self.mark_dirty();self.refresh_mesh()
    def redo(self):
        if not self.busy and self.doc.redo():self.mark_dirty();self.refresh_mesh()
    def select_rect(self,rect,append):
        """Seleciona voxels projetados dentro do retângulo desenhado pelo usuário."""
        coords=np.argwhere(self.doc.occupied)
        if len(coords):
            xy,good=self.viewport.project(self.doc.world_centers(coords));inside=good&(xy[:,0]>=rect.left())&(xy[:,0]<=rect.right())&(xy[:,1]>=rect.top())&(xy[:,1]<=rect.bottom())
            picked={tuple(map(int,p)) for p in coords[inside]}
        else:picked=set()
        if rect.width()<4 and rect.height()<4:
            hit=self.viewport.pick(rect.center());picked={hit[0]} if hit and not hit[2] else set()
        self.doc.selection=(self.doc.selection|picked) if append else picked;self.update_status();self.viewport.update()
    def select_all(self):
        if self.busy:return
        self.doc.selection={tuple(map(int,p)) for p in np.argwhere(self.doc.occupied)};self.update_status();self.viewport.update()
    def clear_selection(self):self.doc.selection.clear();self.update_status();self.viewport.update()
    def delete_selection(self):
        if self.busy:return
        try:
            if self.doc.delete_selection():self.mark_dirty();self.refresh_mesh()
        except Exception as exc:self.error(exc)
    def drag_selection(self,delta,copy):
        if self.busy:return
        try:
            if self.doc.transform_selection(delta,copy):self.mark_dirty();self.refresh_mesh()
        except Exception as exc:self.error(exc)

    def move_dialog(self):
        if self.busy:return
        if not self.doc.selection:self.statusBar().showMessage('Selecione voxels primeiro com a ferramenta Selecionar.');return
        dialog=QDialog(self);dialog.setWindowTitle('Mover / copiar seleção');layout=QVBoxLayout(dialog);values=[]
        for text in ['X · direita','Y · cima','Z · frente']:
            layout.addWidget(QLabel(text));spin=QSpinBox();spin.setRange(-128,128);layout.addWidget(spin);values.append(spin)
        copy=QCheckBox('Criar uma cópia');layout.addWidget(copy)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            x,y,z=[v.value() for v in values]
            try:
                if self.doc.transform_selection((-y,x,z),copy.isChecked()):self.mark_dirty();self.refresh_mesh()
            except Exception as exc:self.error(exc)
    def update_view(self,*args):
        if not hasattr(self,'light_pitch'):return
        self.viewport.grid_visible=self.grid.isChecked();self.viewport.outline=self.outline.isChecked();self.viewport.lighting=self.lighting.isChecked();self.viewport.orthographic=self.ortho.isChecked();self.viewport.pixel_scale=[2,3,1][self.pixel.currentIndex()]
        y,p=math.radians(self.light_yaw.value()),math.radians(self.light_pitch.value());self.viewport.light=(math.cos(p)*math.sin(y),math.sin(p),math.cos(p)*math.cos(y));self.viewport.update()
    def choose_background(self):
        c=QColorDialog.getColor(QColor.fromRgbF(*self.viewport.background),self,'Cor de fundo')
        if c.isValid():self.viewport.background=c.getRgbF()[:3];self.viewport.update()
    def choose_outline(self):
        c=QColorDialog.getColor(QColor.fromRgbF(*self.viewport.outline_color),self,'Cor do contorno')
        if c.isValid():self.viewport.outline_color=c.getRgbF()[:3];self.viewport.update()
    def set_camera(self,yaw,pitch):self.viewport.yaw=float(yaw);self.viewport.pitch=float(pitch);self.viewport.update()
    def camera_preset(self,index):self.set_camera(*[(45,35.264),(0,0),(180,0),(-90,0),(90,0),(0,90),(0,-90)][index])
    def settings(self):
        return {'lighting':self.lighting.isChecked(),'outline':self.outline.isChecked(),'background':list(self.viewport.background),'outline_color':list(self.viewport.outline_color),'light_yaw':self.light_yaw.value(),'light_pitch':self.light_pitch.value(),'brush_color':self.brush_color.tolist()}
    def save(self,save_as=False):
        """Salva o documento e as opções visuais no arquivo JSON do projeto."""
        if self.busy:return False
        path=self.project_path
        if save_as or path is None:
            path,_=QFileDialog.getSaveFileName(self,'Salvar projeto',str(path or 'meu_modelo.vsprite.json'),'Projeto VoxelSprite (*.json)')
            if not path:return False
            path=Path(path).with_suffix('.json')
        try:
            save_project(self.doc,path,self.settings());self.project_path=Path(path);self.dirty=False;self.setWindowTitle(f'VoxelSprite Studio 2.0 • {self.project_path.name}');self.statusBar().showMessage('Projeto salvo com todas as cores por face.');return True
        except Exception as exc:self.error(exc);return False
    def load(self):
        """Carrega um projeto validado e restaura opções visuais compatíveis."""
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,'Abrir projeto','','Projeto VoxelSprite (*.json)')
        if not path or not self.confirm_discard():return
        try:
            doc,settings=load_project(path);doc.mesh();self.install_document(doc,True);self.paths={};self.project_path=Path(path)
            self.lighting.setChecked(bool(settings.get('lighting',True)));self.outline.setChecked(bool(settings.get('outline',False)))
            for key in ('background','outline_color'):
                value=settings.get(key)
                if isinstance(value,list) and len(value)==3 and all(isinstance(v,(int,float)) and 0<=v<=1 for v in value):setattr(self.viewport,key,tuple(value))
            for key,slider in [('light_yaw',self.light_yaw),('light_pitch',self.light_pitch)]:
                value=settings.get(key)
                if isinstance(value,int):slider.setValue(value)
            c=settings.get('brush_color')
            if isinstance(c,list) and len(c)==3 and all(isinstance(v,int) and 0<=v<=255 for v in c):self.set_color(c)
            self.update_view();self.setWindowTitle(f'VoxelSprite Studio 2.0 • {Path(path).name}')
        except Exception as exc:self.error(exc)
    def export_dialog(self):
        """Escolhe um destino e encaminha o documento ao exportador apropriado."""
        if self.busy:return
        if not self.doc.occupied.any():self.error('Crie ou importe um modelo primeiro.');return
        dialog=ExportDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        kind=dialog.kind.currentIndex()
        if kind==5:
            path=QFileDialog.getExistingDirectory(self,'Pasta para as seis vistas')
            if not path:return
            folder=Path(path)/'vistas_voxelsprite'
            if folder.exists() and QMessageBox.question(self,'Substituir vistas?','A pasta vistas_voxelsprite já existe. Substituir os PNGs correspondentes?')!=QMessageBox.StandardButton.Yes:return
            self.run_job(lambda:export_orthographic(self.doc,folder),lambda p:self.statusBar().showMessage(f'Vistas exportadas: {p}'),'Exportando vistas…');return
        extension='obj' if kind==0 else 'gif' if kind==4 else 'png'
        default='$personagem.png' if kind==6 else 'modelo.'+extension
        path,_=QFileDialog.getSaveFileName(self,'Exportar',default,f'Arquivo (*.{extension})')
        if not path:return
        path=Path(path).with_suffix('.'+extension)
        if kind==0:
            mesh=self.viewport.mesh
            self.run_job(lambda:export_atlas_obj(mesh,path),lambda files:self.statusBar().showMessage('OBJ, MTL e atlas PNG exportados. Mantenha os três juntos.'),'Exportando modelo…');return
        try:self.export_sprites(kind,path,int(dialog.size.currentText()),dialog.pitch.value(),dialog.frames.value(),dialog.duration.value())
        except Exception as exc:self.error(exc)
    def export_sprites(self,kind,path,size,pitch,frames=16,duration=100):
        """Renderiza ângulos da câmera e monta PNG, folha, GIF ou preset RPG Maker."""
        if kind==1:
            self.viewport.render_sprite(size).save(path);self.statusBar().showMessage(f'PNG exportado: {path}');return
        count=8 if kind==2 else 16 if kind==3 else 4 if kind==6 else frames
        progress=QProgressDialog('Renderizando sprites…','Cancelar',0,count,self);progress.setWindowModality(Qt.WindowModality.ApplicationModal);progress.setMinimumDuration(0)
        self.busy=True;images=[]
        try:
            for i in range(count):
                progress.setValue(i)
                if progress.wasCanceled():return
                yaw=[0,90,270,180][i] if kind==6 else i*360/count
                images.append(self.viewport.render_sprite(size,yaw,pitch))
            if kind==4:save_gif(images,path,duration)
            elif kind==6:
                sheet=Image.new('RGBA',(size*3,size*4))
                for y,frame in enumerate(images):
                    for x in range(3):sheet.paste(frame,(x*size,y*size))
                sheet.save(path)
            else:sprite_sheet(images,8).save(path)
            progress.setValue(count);self.statusBar().showMessage(f'Exportado: {path}')
        finally:progress.close();self.busy=False
    def dragEnterEvent(self,event):
        if not self.busy and event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.paths={'front':urls[0].toLocalFile()};self.import_dialog()
    def closeEvent(self,event):
        if self.busy:event.ignore();return
        if not self.confirm_discard():event.ignore();return
        self.refresh_timer.stop();self.viewport.cleanup();event.accept()
