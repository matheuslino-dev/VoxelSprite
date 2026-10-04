"""Tema Qt, banner ilustrado e ícones pixelados usados pela interface."""
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QPainter,QColor,QFont,QIcon,QPixmap,QPen
from PySide6.QtWidgets import QWidget

STYLE='''
QWidget { background: #2c2c2e; color: #dedce1; font-family: 'Consolas','DejaVu Sans Mono'; font-size: 11px; }
QMainWindow { background: #1b1b1d; }
QMenuBar,QMenu { background:#242426; } QMenu::item:selected { background:#773766; }
QFrame#rail,QWidget#rail { background:#303032; border:1px solid #47474b; }
QPushButton,QToolButton { background:#3c3c3f; border:2px solid #19191c; border-top-color:#626267; border-left-color:#55555b; padding:7px 6px; }
QPushButton:hover,QToolButton:hover { background:#505057; }
QPushButton:checked,QToolButton:checked { border:3px solid #fa35b4; background:#494049; color:#fff; }
QPushButton:disabled { color:#77747c; background:#303034; }
QPushButton#primary { background:#ad267d; color:white; border-color:#ec40b0; }
QPushButton#danger { background:#94343e; border-color:#dc5260; color:#fff; }
QLabel#muted { color:#9996a3; } QLabel#section { color:#c6c1ce; font-weight:bold; }
QSpinBox,QDoubleSpinBox,QComboBox { background:#1e1e21; border:1px solid #56515e; padding:4px; min-height:18px; }
QGroupBox { border:1px solid #505055; margin-top:12px; padding:10px; }
QGroupBox::title { subcontrol-origin:margin; color:#ff71cf; }
QCheckBox { spacing:6px; }
QSlider::groove:horizontal { height:4px; background:#17171a; }
QSlider::handle:horizontal { background:#ff54c6; width:12px; margin:-4px 0; }
QProgressBar { background:#202023; border:0; max-height:6px; } QProgressBar::chunk { background:#fa35b4; }
QScrollBar:vertical { background:#242426; width:8px; } QScrollBar::handle:vertical { background:#66616e; min-height:24px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QStatusBar { background:#222225; color:#aea8b7; }
'''

class Banner(QWidget):
    """Desenha o cabeçalho original do aplicativo com formas do próprio Qt."""

    def __init__(self):super().__init__();self.setFixedHeight(55)
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#293f47'))
        # Original pixel skyline, drawn in Qt (no borrowed logos or artwork).
        for i in range(0,self.width(),16):
            h=8+((i*17//16)%29);p.fillRect(i,55-h,15,h,QColor('#33535a'))
            if i%48==0:p.fillRect(i+3,55-h+4,4,4,QColor('#467477'))
        p.fillRect(0,0,290,55,QColor('#292a31'))
        f=QFont('Consolas',19,QFont.Weight.Bold);p.setFont(f);p.setPen(QColor('#f9edf7'));p.drawText(18,34,'VOXEL')
        p.setPen(QColor('#ff43bd'));p.drawText(110,34,'SPRITE')
        p.setFont(QFont('Consolas',9));p.setPen(QColor('#bdcbd0'));p.drawText(300,31,'STUDIO 2.0   /   PIXEL ART → 3D')
        p.drawText(self.rect().adjusted(0,0,-16,0),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,'PYTHON EDITION')
        p.end()

PATTERNS={
'paint':['0000000110','0000001111','0000011110','0000111100','0001111000','0011110000','0111100000','0111000000','1110000000','1000000000'],
'add':['0001100000','0011110000','0111111000','1110011100','1110011100','0111111000','0011110000','0001100010','0000000111','0000000010'],
'erase':['0000111000','0001111100','0011111110','0111111111','1111111110','1111111100','0111111000','0011110000','0001100000','0000000000'],
'pick':['0000001100','0000011110','0000111111','0000011110','0000111100','0001111000','0011110000','0111100000','1111000000','0110000000'],
'select':['1110110111','1000000001','1000000001','0000000000','1000000001','1000000001','0000000000','1000000001','1000000001','1110110111'],
'fill':['0001110000','0010011000','0100001100','1100000110','1110000011','0111000110','0011101100','0001111001','0000110001','0000000011'],
'orbit':['0001111000','0110000110','1100000011','1001110001','1001010001','1001110001','1100000011','0110000110','0011111000','0000000000']}

def tool_icon(name):
    """Converte o padrão textual de cada ferramenta em um ícone de pixels."""
    pix=QPixmap(32,32);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#e5dfe9'))
    for y,row in enumerate(PATTERNS[name]):
        for x,char in enumerate(row):
            if char=='1':p.drawRect(x*2+6,y*2+6,2,2)
    p.end();return QIcon(pix)
