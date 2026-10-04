# Validação — Studio 2.0

Ambiente executado: Python 3.12 em Linux, PySide6 6.8.3 e ModernGL 5.12.0; Qt/Xvfb e OpenGL Mesa llvmpipe. Não foi executado em Windows nem macOS; o BAT foi revisado, não executado em cmd.exe.

## 31 testes automatizados

Os 19 testes anteriores continuam aprovados: malha externa, transparência, silhuetas, arredondamento, orientação e cores das vistas, exportação OBJ e fallbacks.

Doze testes do editor verificam:

- Conversão da malha em volume editável sem alterar geometria/cores externas.
- Pintura por face, opacidade, undo/redo.
- Adição, remoção e rollback.
- Balde restrito à superfície conectada da mesma cor/orientação.
- Seleção: cópia, movimento e recusa de colisões.
- Roundtrip de projeto JSON e recusa de coordenadas inválidas.
- Raycast nas seis direções e raios que não atingem a grade.
- Máscaras e orientação de topo/base.
- Exportação ortográfica das seis cores de um voxel.
- Importação sem frente, usando cada uma das outras vistas isoladamente.
- Atlas OBJ, GIF com transparência, folha de sprites e arquivos ortográficos.
- Redimensionamento que preserva voxels e rejeita cortes.

## Fluxo gráfico real

A janela foi aberta em display virtual e testada com eventos de mouse Qt:

1. Criar o primeiro voxel clicando no chão de uma grade vazia.
2. Desfazer/refazer a criação.
3. Pintar uma face por picking real, desfazer/refazer e conferir sua cor.
4. Adicionar e apagar voxels pelo mouse.
5. Capturar a cor com conta-gotas.
6. Selecionar por clique, apagar seleção e desfazer.
7. Importar o exemplo de quatro vistas.
8. Salvar e reabrir o projeto pela interface, comparando volume e cores.
9. Renderizar PNG com fundo transparente.
10. Exportar folhas de 8 e 16 direções, GIF de 8 quadros, grade RPG Maker e OBJ/MTL/atlas.
11. Redimensionar a janela para 1080×720.
12. Copiar uma seleção com Ctrl + arraste e desfazer.
13. Abrir o editor 2D, pintar por clique, desfazer/refazer localmente e reconstruir o volume.
14. Encerrar sem erros.

A integração QPainter/ModernGL precisou de restauração explícita de estados OpenGL para evitar artefatos após exportação; o fluxo foi repetido com a correção. As capturas incluídas são do aplicativo real.

## Limites da verificação

Não foram executados: Windows/cmd.exe, Blender, Godot, RPG Maker ou importação/exportação com o PixZels. Não foi feito benchmark amplo, teste prolongado de uso, comparação pixel a pixel com o PixZels nem teste de todos os drivers e tamanhos possíveis.

Esta é uma implementação nova e funcional das ferramentas descritas no guia, não uma certificação de equivalência ao produto usado como referência.
