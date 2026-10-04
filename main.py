"""Ponto de entrada: configura o contexto OpenGL e inicia a aplicação Qt."""
import sys
from pathlib import Path

def main():
    """Prepara OpenGL 3.3, cria a janela principal e executa o loop de eventos."""
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
