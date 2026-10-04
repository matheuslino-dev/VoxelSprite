"""Motor 3D independente da interface: imagens -> voxels -> malhas -> OBJ/MTL.

Este módulo concentra as operações geométricas e não depende do Qt. Assim, a
reconstrução pode ser testada e reutilizada separadamente da interface gráfica.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import tempfile
import numpy as np
from PIL import Image

MAX_FACES = 400_000

@dataclass
class Mesh:
    """Malha de quads externos e os dados de voxel que deram origem a ela.

    Cada quad tem quatro vértices em coordenadas do mundo, normal por face e
    cor RGB. ``occupied`` e ``base_rgb`` são mantidos para reconstruir o
    documento editável depois da importação de imagens.
    """
    quads: np.ndarray       # (faces, 4, xyz), CCW, eixo Y para cima
    normals: np.ndarray     # (faces, xyz)
    colors: np.ndarray      # (faces, rgb), uint8
    voxel_count: int
    size: tuple
    occupied: object = None
    base_rgb: object = None

    def vertex_data(self):
        """Converte cada quad em dois triângulos no formato esperado pelo OpenGL."""
        order = [0, 1, 2, 0, 2, 3]
        positions = self.quads[:, order].reshape(-1, 3)
        normals = np.repeat(self.normals, 6, axis=0)
        colors = np.repeat(self.colors.astype('f4') / 255, 6, axis=0)
        return np.ascontiguousarray(np.concatenate((positions, normals, colors), axis=1), dtype='f4')


def read_sprite(path, max_size=96):
    """Preserva proporção e pixels; reduz imagens grandes por vizinho mais próximo."""
    with Image.open(path) as src:
        if src.width * src.height > 16_000_000:
            raise ValueError('Imagem muito grande. Use uma imagem de até 16 milhões de pixels.')
        original = src.size
        image = src.convert('RGBA')
        image.thumbnail((max_size, max_size), Image.Resampling.NEAREST)
    return np.array(image), original


def silhouette_distance(mask):
    """Calcula distância Manhattan ao exterior por duas passagens pela imagem.

    A primeira passagem propaga distâncias de cima/esquerda para baixo/direita;
    a segunda completa o resultado no sentido contrário. Pixels transparentes,
    inclusive buracos internos, começam com distância zero.
    """
    h, w = mask.shape
    d = np.pad(np.where(mask, h + w + 1, 0).astype('i4'), 1)
    for y in range(1, h + 1):
        for x in range(1, w + 1):
            if d[y, x]:
                d[y, x] = min(d[y, x], d[y-1, x]+1, d[y, x-1]+1)
    for y in range(h, 0, -1):
        for x in range(w, 0, -1):
            if d[y, x]:
                d[y, x] = min(d[y, x], d[y+1, x]+1, d[y, x+1]+1)
    return d[1:-1, 1:-1]


def fit_view(rgba, width, height):
    """Mapeia uma tela inteira à grade comum; sem recortar a transparência."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('Cada vista precisa ser uma imagem RGBA.')
    return np.array(Image.fromarray(rgba).resize((width,height), Image.Resampling.NEAREST))


def dominant_rows(rgba, mask):
    """Cor mais frequente por linha, evitando copiar olhos/boca para as costas."""
    colors = np.zeros((*mask.shape,3),dtype='uint8')
    for y in range(mask.shape[0]):
        visible = rgba[y,mask[y],:3]
        if len(visible):
            palette, counts = np.unique(visible,axis=0,return_counts=True)
            colors[y] = palette[np.argmax(counts)]
    return colors


def voxelize(rgba, depth=12, roundness=0.6, alpha_threshold=128,
             views=None, mirror_missing_side=True, fallback='front'):
    """Interseção de silhuetas ortográficas; cor escolhida pela normal da face.

    Frente olha de +Z; costas de -Z; direita de +X; esquerda de -X.
    Cada PNG representa o objeto visto de fora, com o topo para cima.
    Vistas laterais controlam a forma em Z e substituem o arredondamento.
    Sem laterais, usa a extrusão arredondada original.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4 or not 1 <= depth <= 64:
        raise ValueError('Imagem RGBA ou profundidade inválida (1–64).')
    if not 0 <= roundness <= 1 or not 1 <= alpha_threshold <= 255:
        raise ValueError('Arredondamento ou corte alfa inválido.')
    if fallback not in ('front','dominant'):
        raise ValueError('Modo de cores ausentes inválido.')
    h, w, _ = rgba.shape
    if max(h, w) > 128:
        raise ValueError('O motor aceita sprites de até 128 × 128 pixels.')
    supplied = dict(views or {})
    if set(supplied)-{'back','left','right','top','bottom'}:
        raise ValueError('Vistas aceitas: back, left, right, top e bottom.')
    projected = {}
    front_mask = rgba[:,:,3] >= alpha_threshold
    if not front_mask.any():
        raise ValueError('Nenhum pixel visível na frente. Diminua o corte alfa ou escolha outra imagem.')
    mask = front_mask.copy()
    for key, image in supplied.items():
        view = fit_view(image,w,depth) if key in ('top','bottom') else fit_view(image,w if key=='back' else depth,h)
        if not (view[:,:,3]>=alpha_threshold).any():
            names={'back':'costas','left':'lateral esquerda','right':'lateral direita','top':'topo','bottom':'base'}
            raise ValueError(f'A vista {names[key]} não tem pixels visíveis. Diminua o corte alfa ou remova essa vista.')
        # Converter a coordenada horizontal da câmera para o eixo do mundo.
        projected[key] = view[:,::-1] if key in ('back','right') else view[::-1] if key=='bottom' else view
    if 'back' in projected:
        mask &= projected['back'][:,:,3] >= alpha_threshold
    if not mask.any():
        raise ValueError('Frente e costas não se sobrepõem. Confira o alinhamento das telas e a orientação das costas.')
    sides = [projected[k] for k in ('left','right') if k in projected]
    if sides or 'top' in projected or 'bottom' in projected:
        occupied = np.broadcast_to(mask[:,:,None],(h,w,depth)).copy()
        for side in sides:
            occupied &= (side[:,:,3]>=alpha_threshold)[:,None,:]
    else:
        distance = silhouette_distance(mask).astype('f4')
        profile = np.sqrt(distance / distance.max())
        thickness = np.maximum(1,np.rint(depth*((1-roundness)+roundness*profile)).astype(int))
        thickness = np.minimum(depth,thickness+((depth-thickness)%2))
        start = (depth-thickness)//2
        z = np.arange(depth)[None,None,:]
        occupied = mask[:,:,None] & (z>=start[:,:,None]) & (z<(start+thickness)[:,:,None])
    for key in ('top','bottom'):
        if key in projected:
            occupied &= (projected[key][:,:,3]>=alpha_threshold).T[None,:,:]
    if not occupied.any():
        raise ValueError('As silhuetas não formam um volume em comum. Alinhe pés, cabeça e centro nas imagens.')
    # Uma única lateral informa a geometria dos dois lados. A cópia espelhada
    # de suas cores no lado oposto é opcional e só vale para a vista ausente.
    if mirror_missing_side:
        if 'left' in projected and 'right' not in projected: projected['right']=projected['left']
        if 'right' in projected and 'left' not in projected: projected['left']=projected['right']
    base = dominant_rows(rgba,front_mask) if fallback=='dominant' else rgba[:,:,:3]
    def face_colors(normal, ys, xs, zs):
        if normal == (0,0,1): return rgba[ys,xs,:3]
        if normal == (0,0,-1) and 'back' in projected: return projected['back'][ys,xs,:3]
        if normal == (1,0,0) and 'right' in projected: return projected['right'][ys,zs,:3]
        if normal == (-1,0,0) and 'left' in projected: return projected['left'][ys,zs,:3]
        if normal == (0,1,0) and 'top' in projected: return projected['top'][zs,xs,:3]
        if normal == (0,-1,0) and 'bottom' in projected: return projected['bottom'][zs,xs,:3]
        return base[ys,xs]
    return surface_mesh(occupied,rgba[:,:,:3],face_colors)


# Deslocamentos na matriz (y imagem, x, z), normal no mundo e cantos CCW.
FACES = [
    ((0,1,0), (1,0,0), [(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),
    ((0,-1,0), (-1,0,0), [(0,0,1),(0,1,1),(0,1,0),(0,0,0)]),
    ((-1,0,0), (0,1,0), [(0,1,1),(1,1,1),(1,1,0),(0,1,0)]),
    ((1,0,0), (0,-1,0), [(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),
    ((0,0,1), (0,0,1), [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]),
    ((0,0,-1), (0,0,-1), [(1,0,0),(0,0,0),(0,1,0),(1,1,0)]),
]


def surface_mesh(occupied, rgb, color_sampler=None):
    """Gera somente as faces expostas da grade tridimensional.

    Para cada uma das seis orientações, compara a ocupação com a célula vizinha.
    Uma face é criada quando o voxel existe e o vizinho naquela direção está
    vazio ou fora do volume.
    """
    h, w, d = occupied.shape
    padded = np.pad(occupied, 1)
    batches = []
    count = 0
    for (dy, dx, dz), normal, corners in FACES:
        # O padding de um voxel torna as bordas equivalentes a vizinhos vazios.
        neighbor = padded[1+dy:1+dy+h, 1+dx:1+dx+w, 1+dz:1+dz+d]
        ys, xs, zs = np.nonzero(occupied & ~neighbor)
        count += len(ys)
        if count > MAX_FACES:
            raise ValueError('Modelo muito complexo. Reduza a resolução ou a profundidade.')
        base = np.column_stack((xs-w/2, h-1-ys-h/2, zs-d/2)).astype('f4')
        quads = base[:, None, :] + np.array(corners, dtype='f4')
        batches.append((quads, np.tile(np.array(normal, dtype='f4'), (len(ys),1)), color_sampler(normal,ys,xs,zs) if color_sampler else rgb[ys,xs]))
    return Mesh(*(np.concatenate([b[i] for b in batches]) for i in range(3)),
                int(occupied.sum()), (w,h,d), occupied.copy(), rgb.copy())


def export_obj(mesh, path):
    """Exporta faces externas e materiais RGB. Substituição atômica por arquivo."""
    path = Path(path).with_suffix('.obj')
    if not len(mesh.quads):
        raise ValueError('Não há faces para exportar.')
    # Um nome simples evita problemas de leitores OBJ com espaços em mtllib.
    import hashlib
    suffix = hashlib.sha256(path.name.encode('utf-8')).hexdigest()[:10]
    mtl = path.with_name(f'materiais_{suffix}.mtl')
    colors, indices = np.unique(mesh.colors, axis=0, return_inverse=True)
    temporary = []
    try:
        for target in (mtl, path):
            fd, name = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
            temporary.append((Path(name), target))
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
                if target == mtl:
                    for i, color in enumerate(colors):
                        r,g,b = color.astype(float) / 255
                        out.write(f'newmtl cor_{i}\nKd {r:.6f} {g:.6f} {b:.6f}\nKa 0 0 0\nKs 0 0 0\nd 1\nillum 1\n\n')
                else:
                    out.write(f'# VoxelSprite 1.1 | Y up | 1 unit = 1 voxel\nmtllib {mtl.name}\no VoxelSprite\n')
                    for v in mesh.quads.reshape(-1,3):
                        out.write(f'v {v[0]:.6g} {v[1]:.6g} {v[2]:.6g}\n')
                    for n in mesh.normals:
                        out.write(f'vn {n[0]:.0f} {n[1]:.0f} {n[2]:.0f}\n')
                    last = -1
                    for i, material in enumerate(indices):
                        if material != last:
                            out.write(f'usemtl cor_{material}\n')
                            last = material
                        a = i*4+1
                        out.write(f'f {a}//{i+1} {a+1}//{i+1} {a+2}//{i+1} {a+3}//{i+1}\n')
        for tmp, target in temporary:
            tmp.replace(target)
    finally:
        for tmp, _ in temporary:
            tmp.unlink(missing_ok=True)
    return path, mtl
