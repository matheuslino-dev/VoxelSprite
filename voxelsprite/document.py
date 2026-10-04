"""Volume editável, seis cores por voxel, histórico por deltas e JSON portátil."""
from collections import deque
import json
import os
from pathlib import Path
import tempfile
import numpy as np
from .core import FACES, surface_mesh, voxelize, read_sprite

NORMALS = [tuple(f[1]) for f in FACES]
STEPS = [np.array(f[0],dtype=int) for f in FACES]
MAX_SIDE = 144
MAX_VOXELS = 1_000_000

class Document:
    """Estado editável do modelo: voxels, cores por face, seleção e histórico.

    ``occupied[y, x, z]`` indica se uma célula contém um voxel. As cores ficam
    em ``colors[y, x, z, face, rgb]``; ``face`` segue a ordem de ``FACES`` em
    :mod:`voxelsprite.core`.
    """

    def __init__(self,shape=(32,32,32)):
        if len(shape)!=3 or any(not 1<=int(n)<=MAX_SIDE for n in shape):
            raise ValueError('Grade inválida; cada dimensão deve estar entre 1 e 144.')
        self.occupied=np.zeros(tuple(map(int,shape)),dtype=bool)
        self.colors=np.zeros((*self.occupied.shape,6,3),dtype='uint8')
        self.history=[];self.redos=[];self.pending=None
        self.selection=set()
        self.revision=0

    @classmethod
    def from_mesh(cls,mesh,padding=4):
        """Converte uma malha importada para a grade editável e centraliza-a."""
        if mesh.voxel_count>MAX_VOXELS:raise ValueError("Modelo acima de um milhão de voxels. Reduza a resolução ou a profundidade.")
        shape=np.array(mesh.occupied.shape)
        pads=np.minimum(padding,(MAX_SIDE-shape)//2)
        obj=cls(shape+2*pads)
        sl=tuple(slice(int(p),int(p+n)) for p,n in zip(pads,shape))
        obj.occupied[sl]=mesh.occupied
        base=mesh.base_rgb[:,:,None,None,:]
        obj.colors[sl]=np.broadcast_to(base,(*shape,6,3))
        centers=mesh.quads.mean(axis=1)-mesh.normals*.5
        h,w,d=shape
        coords=np.rint(np.column_stack((h/2-.5-centers[:,1],centers[:,0]+w/2-.5,centers[:,2]+d/2-.5))).astype(int)
        coords+=pads
        for face,normal in enumerate(NORMALS):
            pick=np.all(mesh.normals==normal,axis=1)
            ys,xs,zs=coords[pick].T
            obj.colors[ys,xs,zs,face]=mesh.colors[pick]
        return obj

    def inside(self,p):
        """Retorna se as coordenadas inteiras estão dentro da grade."""
        return all(0<=int(v)<n for v,n in zip(p,self.occupied.shape))

    def exists(self,p):
        """Retorna se existe um voxel em uma coordenada interna da grade."""
        return self.inside(p) and bool(self.occupied[tuple(p)])

    def begin(self):
        """Inicia uma transação de edição, guardando o estado antes da primeira alteração."""
        if self.pending is None:self.pending={}

    def set_voxel(self,p,exists,colors=None):
        """Registra o valor anterior e altera ocupação e, opcionalmente, as seis cores."""
        p=tuple(map(int,p))
        if not self.inside(p):return False
        if self.pending is None:self.begin()
        if p not in self.pending:self.pending[p]=(bool(self.occupied[p]),self.colors[p].copy())
        self.occupied[p]=exists
        if colors is not None:self.colors[p]=colors
        return True

    def commit(self):
        """Fecha a transação e guarda apenas as diferenças reais para desfazer/refazer."""
        if self.pending is None:return False
        diff={}
        for p,(old,oldc) in self.pending.items():
            new=bool(self.occupied[p]);newc=self.colors[p].copy()
            if old!=new or not np.array_equal(oldc,newc):diff[p]=((old,oldc),(new,newc))
        self.pending=None
        if not diff:return False
        self.history.append(diff);self.redos.clear()
        # Limit total changed-voxel entries, not only the number of operations.
        while len(self.history)>1 and (len(self.history)>80 or sum(map(len,self.history))>150_000):self.history.pop(0)
        self.revision+=1
        self.selection={p for p in self.selection if self.exists(p)}
        return True

    def rollback(self):
        """Descarta a transação atual e restaura cada voxel ao estado inicial."""
        if self.pending:
            for p,(exists,colors) in self.pending.items():self.occupied[p]=exists;self.colors[p]=colors
        self.pending=None

    def undo(self):
        """Aplica o estado anterior da última transação e guarda-a para refazer."""
        if not self.history:return False
        diff=self.history.pop()
        for p,(before,after) in diff.items():self.occupied[p]=before[0];self.colors[p]=before[1]
        self.redos.append(diff);self.selection.clear();self.revision+=1;return True

    def redo(self):
        """Reaplica a última transação desfeita."""
        if not self.redos:return False
        diff=self.redos.pop()
        for p,(before,after) in diff.items():self.occupied[p]=after[0];self.colors[p]=after[1]
        self.history.append(diff);self.selection.clear();self.revision+=1;return True

    def mesh(self):
        """Calcula a malha externa atual, lendo a cor correspondente a cada normal."""
        return surface_mesh(self.occupied,self.colors[:,:,:,0,:].max(axis=2),
                            lambda n,ys,xs,zs:self.colors[ys,xs,zs,NORMALS.index(n)])

    def brush(self,point,face,size,tool,color,opacity=1.0,limit_selection=True):
        """Pincel quadrado no plano da face atingida; pintar não atravessa o volume."""
        point=np.array(point,dtype=int);step=STEPS[face]
        axes=[a for a in range(3) if not step[a]]
        start=-(size//2)
        for u in range(start,start+size):
            for v in range(start,start+size):
                p=point.copy();p[axes[0]]+=u;p[axes[1]]+=v
                t=tuple(p)
                if limit_selection and self.selection and t not in self.selection:continue
                if tool=='add':
                    q=p+step
                    if self.exists(p) and not self.exists(q):self.set_voxel(q,True,np.tile(color,(6,1)))
                elif self.exists(p):
                    if tool=='erase':self.set_voxel(p,False)
                    elif tool=='paint' and not self.exists(p+step):
                        c=self.colors[t].copy();c[face]=np.rint(c[face]*(1-opacity)+np.array(color)*opacity)
                        self.set_voxel(p,True,c)

    def fill(self,point,face,color,opacity=1.):
        """Balde: região conectada de faces externas da mesma orientação e cor."""
        point=tuple(point)
        if not self.exists(point):return
        original=self.colors[point][face].copy()
        new=np.rint(original*(1-opacity)+np.array(color)*opacity).astype('uint8')
        if np.array_equal(original,new):return
        queue=deque([point]);seen={point};normal=STEPS[face]
        tangent=[s for s in STEPS if np.dot(s,normal)==0]
        while queue:
            p=queue.popleft()
            if self.selection and p not in self.selection:continue
            if not self.exists(p) or self.exists(np.array(p)+normal):continue
            if not np.array_equal(self.colors[p][face],original):continue
            c=self.colors[p].copy();c[face]=new;self.set_voxel(p,True,c)
            for step in tangent:
                q=tuple(np.array(p)+step)
                if q not in seen and self.inside(q):seen.add(q);queue.append(q)

    def transform_selection(self,delta,copy=False):
        """Move ou copia a seleção após validar limites, colisões e limites do modelo."""
        if not self.selection:return False
        delta=np.array(delta,dtype=int)
        pairs=[(p,tuple(np.array(p)+delta)) for p in self.selection if self.exists(p)]
        if any(not self.inside(q) for _,q in pairs):raise ValueError('A seleção sairia da grade. Aumente a grade antes de mover.')
        if any(self.exists(q) and q not in self.selection for _,q in pairs):raise ValueError('O destino já contém voxels. Escolha um espaço vazio.')
        values=[(q,self.colors[p].copy()) for p,q in pairs]
        self.begin()
        if not copy:
            for p,q in pairs:self.set_voxel(p,False)
        for q,c in values:self.set_voxel(q,True,c)
        try:
            if int(self.occupied.sum())>MAX_VOXELS:raise ValueError('Limite de um milhão de voxels atingido.')
            self.mesh()
        except Exception:
            self.rollback();raise
        changed=self.commit();self.selection={q for q,_ in values};return changed

    def delete_selection(self):
        """Apaga a seleção como uma única transação reversível."""
        self.begin()
        for p in self.selection:self.set_voxel(p,False)
        try:self.mesh()
        except Exception:
            self.rollback();raise
        changed=self.commit();self.selection.clear();return changed

    def world_centers(self,coords):
        """Converte coordenadas da matriz (linha, coluna, profundidade) para XYZ."""
        h,w,d=self.occupied.shape
        arr=np.asarray(coords)
        return np.column_stack((arr[:,1]+.5-w/2,h/2-arr[:,0]-.5,arr[:,2]+.5-d/2))

    def coords_from_world(self,points):
        """Converte pontos XYZ do mundo para índices inteiros da grade."""
        h,w,d=self.occupied.shape
        p=np.asarray(points)
        return np.floor(np.column_stack((h/2-p[:,1],p[:,0]+w/2,p[:,2]+d/2))).astype(int)

    def resize(self,side):
        """Cria um documento cúbico maior/menor, centralizando voxels sem cortá-los."""
        if not 8<=side<=128:raise ValueError('A grade precisa ter 8–128 células por eixo.')
        old=np.array(self.occupied.shape);new=np.array([side]*3);shift=(new-old)//2
        coords=np.argwhere(self.occupied);target=coords+shift
        if len(coords) and (np.any(target<0) or np.any(target>=new)):raise ValueError('Essa grade cortaria voxels existentes. Escolha uma grade maior.')
        doc=Document(new)
        if len(coords):
            a=tuple(coords.T);b=tuple(target.T);doc.occupied[b]=True;doc.colors[b]=self.colors[a]
        return doc


def save_project(document,path,settings=None):
    """Salva só os voxels ocupados, suas seis cores e opções da interface em JSON."""
    coords=np.argwhere(document.occupied)
    data={'format':'voxelsprite','version':2,'shape':list(document.occupied.shape),
          'voxels':coords.tolist(),'face_colors':document.colors[tuple(coords.T)].reshape(-1,18).tolist(),
          'settings':settings or {}}
    path=Path(path)
    fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,separators=(',',':'),ensure_ascii=False)
        Path(tmp).replace(path)
    finally:Path(tmp).unlink(missing_ok=True)


def load_project(path):
    """Lê e valida um projeto JSON antes de preencher as matrizes do documento."""
    path=Path(path)
    if path.stat().st_size>100*1024*1024:raise ValueError('Projeto maior que 100 MB.')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('format')!='voxelsprite' or data.get('version')!=2:raise ValueError('Use um projeto JSON do VoxelSprite Studio 2.0.')
    shape=data.get('shape')
    if not isinstance(shape,list) or len(shape)!=3 or any(type(n)!=int or not 1<=n<=MAX_SIDE for n in shape):raise ValueError('Dimensões inválidas.')
    points=data.get('voxels',[]);colors=data.get('face_colors',[])
    if len(points)>MAX_VOXELS or len(colors)!=len(points):raise ValueError('Volume inválido ou grande demais.')
    obj=Document(shape)
    if points:
        p=np.asarray(points);c=np.asarray(colors)
        if p.shape!=(len(points),3) or p.dtype.kind not in 'iu' or np.any(p<0) or np.any(p>=np.array(shape)):raise ValueError('Coordenadas inválidas.')
        if c.shape!=(len(points),18) or c.dtype.kind not in 'iu' or np.any(c<0) or np.any(c>255):raise ValueError('Cores inválidas.')
        if len(np.unique(p,axis=0))!=len(p):raise ValueError('Voxels duplicados no projeto.')
        obj.occupied[tuple(p.T)]=True;obj.colors[tuple(p.T)]=c.reshape(-1,6,3).astype('uint8')
    settings=data.get('settings',{})
    return obj,settings if isinstance(settings,dict) else {}


def build_from_images(paths,resolution=64,depth=16,roundness=.6,alpha=128,mirror=True,fallback='dominant'):
    """Aceita qualquer subconjunto não vazio das seis vistas."""
    images={key:read_sprite(path,resolution)[0] for key,path in paths.items() if path}
    if not images:raise ValueError('Carregue pelo menos uma imagem.')
    if 'front' in images:front=images.pop('front')
    elif 'back' in images:front=images['back'][:,::-1].copy()
    elif 'left' in images or 'right' in images:
        side=images.get('left',images.get('right'));h=side.shape[0];w=min(depth,resolution)
        front=np.zeros((h,w,4),dtype='uint8')
        for y in range(h):
            row=side[y][side[y,:,3]>=alpha]
            if len(row):front[y,:,:3]=row[0,:3];front[y,:,3]=255
        roundness=0
    else:
        top=images.get('top',images.get('bottom'));w=top.shape[1];h=min(depth,resolution)
        front=np.full((h,w,4),255,dtype='uint8');front[:,:,:3]=top[:,:,:3].mean(axis=0).astype('uint8')[None,:,:]
        roundness=0
    mesh=voxelize(front,depth,roundness,alpha,images,mirror,fallback)
    return Document.from_mesh(mesh)
