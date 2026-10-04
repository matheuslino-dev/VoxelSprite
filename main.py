import sys
from pathlib import Path

def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QSurfaceFormat
    fmt = QSurfaceFormat()
    fmt.setVersion(3,3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    from voxelsprite.ui import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('VoxelSprite')
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        import traceback
        log = Path(__file__).with_name('erro_voxelsprite.log')
        log.write_text(traceback.format_exc(),encoding='utf-8')
        print(f'Erro ao abrir o aplicativo. Detalhes em: {log}')
        traceback.print_exc()
        sys.exit(1)
