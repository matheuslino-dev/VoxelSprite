# Guia de leitura do código

Este guia explica como as partes do VoxelSprite Studio se conectam e onde
encontrar a lógica de cada recurso. Os comentários e docstrings adicionados ao
código também descrevem as responsabilidades das classes e os algoritmos menos
óbvios. A documentação não altera o comportamento do aplicativo.

## Visão geral

O programa separa interface, dados, geometria e renderização:

1. `main.py` configura o OpenGL e inicia o loop de eventos do Qt.
2. `voxelsprite/ui.py` monta a janela e encaminha cliques e comandos.
3. `voxelsprite/document.py` guarda os voxels, cores, seleção e histórico.
4. `voxelsprite/core.py` converte imagens em voxels e voxels em faces de malha.
5. `voxelsprite/viewport.py` trata mouse/teclado e apresenta o modelo 3D.
6. `voxelsprite/scene.py` envia buffers e shaders para o OpenGL.
7. `voxelsprite/exports.py` e `voxelsprite/core.py` salvam os formatos de saída.

Assim, a interface não precisa conhecer os detalhes de como uma face é
construída; ela pede ao documento uma malha e a envia ao viewport.

## Como os dados representam o modelo

Um `Document` contém duas matrizes NumPy principais:

- `occupied[y, x, z]`: `True` quando há um voxel nessa célula.
- `colors[y, x, z, face, rgb]`: cor independente para cada uma das seis faces.

Os índices da matriz não são os mesmos eixos do mundo. A linha `y` cresce para
baixo na imagem, mas o eixo Y do mundo cresce para cima. A coluna `x` vira o
eixo X do mundo e `z` é a profundidade. `world_centers` e `coords_from_world`
fazem a conversão entre esses sistemas.

`core.FACES` é a tabela que mantém coerentes os deslocamentos entre células, as
normais do mundo e os quatro cantos de cada face. A mesma ordem de faces é usada
para armazenar cores, selecionar superfícies e gerar geometria.

## Arquivos da aplicação

### Inicialização e interface

- [`main.py`](main.py): ponto de entrada. Define OpenGL 3.3 antes de importar a
  janela, cria `QApplication`, instancia `MainWindow` e inicia o loop Qt. Se a
  inicialização falhar, grava o traceback em `erro_voxelsprite.log`.
- [`voxelsprite/ui.py`](voxelsprite/ui.py): coordena o aplicativo. `MainWindow`
  cria menus, botões, painéis, atalhos e sinais; executa as ferramentas sobre o
  documento; salva e abre projetos; encaminha importações e exportações.
  `edit_hit` é o ponto que transforma o resultado do picking em pintar,
  adicionar, apagar, preencher ou capturar cor. `end_stroke` valida e confirma
  todo um traço como uma única ação de histórico.
  `Worker` executa tarefas demoradas fora da thread gráfica e envia o resultado
  de volta por sinais do Qt.
- [`voxelsprite/dialogs.py`](voxelsprite/dialogs.py): diálogos para escolher as
  vistas de entrada e os formatos de saída. Converte opções visuais em valores
  que o motor pode usar.
- [`voxelsprite/style.py`](voxelsprite/style.py): folha de estilo Qt, banner e
  padrões pixelados que são convertidos em ícones.

### Imagens e geometria 3D

- [`voxelsprite/core.py`](voxelsprite/core.py): motor geométrico sem dependência
  da interface. `read_sprite` normaliza imagens como RGBA;
  `silhouette_distance` mede a distância dos pixels opacos ao exterior;
  `voxelize` combina as silhuetas das vistas, determina a ocupação e a cor das
  faces; `surface_mesh` só cria faces sem um voxel vizinho; `export_obj` grava
  a geometria OBJ e materiais MTL. A classe `Mesh` mantém esses resultados e
  converte quads em triângulos para o OpenGL.
- [`voxelsprite/document.py`](voxelsprite/document.py): estado editável do
  modelo. `set_voxel` registra o estado anterior; `begin`, `commit` e
  `rollback` agrupam alterações; `undo` e `redo` aplicam os deltas guardados.
  `brush` edita uma área quadrada de faces e `fill` percorre faces conectadas
  com a mesma orientação e cor. A seleção pode ser movida, copiada ou apagada.
  `save_project` e `load_project` serializam e validam JSON.
  `build_from_images` carrega qualquer conjunto não vazio de vistas e conduz a
  reconstrução até criar um `Document`.
- [`voxelsprite/picking.py`](voxelsprite/picking.py): converte um raio em uma
  célula atingida. A primeira etapa encontra o trecho do raio dentro da grade;
  depois o algoritmo DDA avança pela fronteira de célula mais próxima até
  atingir um voxel. Isso evita testar cada face da malha.
- [`voxelsprite/exports.py`](voxelsprite/exports.py): gera projeções
  ortográficas, imagens com contorno, folhas de sprites, GIFs e exportação OBJ
  com atlas de cores. As vistas ortográficas usam a cor armazenada na face
  voltada para cada câmera.

### Desenho e edição das vistas

- [`voxelsprite/viewport.py`](voxelsprite/viewport.py): widget OpenGL
  interativo. Calcula raios a partir do cursor, chama o picking, atualiza a
  câmera e encaminha os gestos ao editor. A prévia pode ser renderizada em
  resolução menor e ampliada por vizinho mais próximo para obter o visual pixel
  art. `render_sprite` usa a mesma cena para renderizações exportáveis.
- [`voxelsprite/scene.py`](voxelsprite/scene.py): recursos de baixo nível do
  OpenGL. `camera_matrix` combina câmera e projeção; `Scene` envia a malha,
  desenha grade e iluminação, cria quadros fora da janela e libera os recursos
  gráficos. As strings `VERTEX`, `FRAGMENT` e `BLIT_*` são programas GLSL
  executados pela placa de vídeo.
- [`voxelsprite/ortho_editor.py`](voxelsprite/ortho_editor.py): editor de
  pixels das seis vistas. `PixelCanvas` implementa pincel, borracha, balde,
  conta-gotas e histórico local. `OrthoEditor.reconstruct` usa as vistas
  habilitadas para criar um novo volume; a reconstrução pode preencher detalhes
  que não aparecem em nenhuma silhueta.
- [`voxelsprite/__init__.py`](voxelsprite/__init__.py): identificação e versão
  do pacote Python.
- [`iniciar_windows.bat`](iniciar_windows.bat): localiza uma versão compatível
  do Python, cria/reutiliza `.venv`, instala `requirements.txt` na primeira
  execução e inicia `main.py`.

## Caminho de uma edição com o mouse

1. O evento de mouse em `Viewport` cria um raio a partir da câmera.
2. `raycast` percorre a grade e retorna coordenadas do voxel, face atingida e
   indicador de chão vazio.
3. O sinal `hit` entrega o resultado e os modificadores de teclado a
   `MainWindow.edit_hit`.
4. A ferramenta chama `Document.brush`, `fill` ou `set_voxel`.
5. `Document.commit` guarda somente os valores que realmente mudaram.
6. `refresh_mesh` pede uma nova malha ao documento e marca o viewport para
   enviá-la ao OpenGL.

Um traço inteiro começa em `begin_stroke` e termina em `end_stroke`, para que
desfazer reverta o traço todo, em vez de apenas o último pixel.

## Caminho de importação e exportação

Na importação, `ImportDialog` recolhe arquivos e opções; `Worker` chama
`build_from_images`; o motor normaliza as imagens, cruza as máscaras alfa e
constrói faces; `Document.from_mesh` converte o resultado para dados editáveis.

Na exportação de sprites, a janela pede ao `Viewport` quadros em vários ângulos.
`sprite_sheet` os organiza em uma grade ou `save_gif` os converte para uma
paleta comum. A exportação ortográfica percorre diretamente a ocupação e as
cores do documento. OBJ usa os quads e cores da malha para gravar geometria,
materiais ou atlas.

Os projetos `.json` são diferentes das exportações: guardam coordenadas dos
voxels, seis cores por voxel e configurações visuais para continuar editando
depois.

## O que os testes ensinam

Os testes são executáveis de forma independente da janela:

- [`tests/test_core.py`](tests/test_core.py): voxel único e suas seis faces;
  ausência de faces internas em caixas; buracos transparentes; corte alfa;
  simetria do arredondamento; direção e cor das imagens; redimensionamento
  pixelado; materiais e índices válidos no OBJ.
- [`tests/test_editor.py`](tests/test_editor.py): conversão entre malha e
  documento; pintura com opacidade; adicionar, apagar, desfazer e rollback;
  balde restrito à superfície conectada; mover/copiar e colisões; salvar,
  carregar e validar projetos; picking nas seis direções; vistas de topo/base;
  importação sem frente; exportação de atlas, GIF e spritesheet; redimensionar
  sem cortar voxels.
- [`tests/test_multiview.py`](tests/test_multiview.py): cor correta para cada
  câmera; inversão horizontal das costas e laterais; interseção das máscaras;
  arredondamento quando não há lateral; espelhamento opcional de lateral;
  preenchimento de cor dominante; mensagens para vistas vazias/incompatíveis;
  preservação das cores no OBJ.

Execute a suíte na raiz do projeto:

```shell
.venv\Scripts\python -m unittest discover -s tests -v
```

## Sugestão de ordem para estudar

1. Leia `main.py` e `voxelsprite/ui.py` para entender o ciclo da aplicação.
2. Estude `Document` e os testes de `test_editor.py` para acompanhar os dados.
3. Leia `FACES`, `surface_mesh` e `voxelize` em `core.py` junto com
   `test_core.py` e `test_multiview.py`.
4. Acompanhe `raycast` e o fluxo de clique entre `viewport.py` e `ui.py`.
5. Por fim, veja `scene.py` para a renderização e `exports.py` para os formatos
   gerados.
