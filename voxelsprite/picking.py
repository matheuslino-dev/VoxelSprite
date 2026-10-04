"""Encontra o primeiro voxel atingido por um raio usando travessia DDA da grade."""
import numpy as np
from .document import STEPS

def raycast(doc,origin,direction):
    """Percorre as células cruzadas pelo raio e devolve voxel, face e estado.

    Primeiro limita o raio ao paralelepípedo da grade. Depois avança de uma
    fronteira de célula à próxima (DDA), sem testar cada quad da malha.
    """
    h,w,d=doc.occupied.shape
    o=np.array([h/2-origin[1],origin[0]+w/2,origin[2]+d/2],dtype=float)
    v=np.array([-direction[1],direction[0],direction[2]],dtype=float)
    shape=np.array([h,w,d]);low=np.full(3,-np.inf);high=np.full(3,np.inf)
    # Interseção do raio com cada um dos três intervalos da grade ("slabs").
    for a in range(3):
        if abs(v[a])<1e-12:
            if not 0<=o[a]<shape[a]:return None
        else:
            t0=(0-o[a])/v[a];t1=(shape[a]-o[a])/v[a]
            low[a]=min(t0,t1);high[a]=max(t0,t1)
    enter=max(float(low.max()),0.);leave=float(high.min())
    if leave<enter:return None
    step=np.sign(v).astype(int)
    axis=int(np.argmax(low))
    face=int(next(i for i,s in enumerate(STEPS) if s[axis]==-step[axis])) if step[axis] else 4
    p=np.floor(o+v*(enter+1e-6)).astype(int);p=np.clip(p,0,shape-1)
    delta=np.full(3,np.inf);boundary=np.full(3,np.inf)
    for a in range(3):
        if step[a]:
            delta[a]=abs(1/v[a]);edge=p[a]+(1 if step[a]>0 else 0);boundary[a]=(edge-o[a])/v[a]
    # A cada passo, atravessa a fronteira mais próxima e atualiza a face atingida.
    for _ in range(int(shape.sum())+3):
        if np.any(p<0) or np.any(p>=shape):return None
        if doc.occupied[tuple(p)]:return tuple(map(int,p)),face,False
        axis=int(np.argmin(boundary))
        if boundary[axis]>leave+1e-6:return None
        p[axis]+=step[axis];boundary[axis]+=delta[axis]
        face=next(i for i,s in enumerate(STEPS) if s[axis]==-step[axis])
    return None
