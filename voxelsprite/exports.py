"""Exportações de vistas ortográficas, atlas RGB, spritesheets e GIF."""
from pathlib import Path
import hashlib
import math
import numpy as np
from PIL import Image,ImageFilter

VIEW_KEYS=('front','back','left','right','top','bottom')


def orthographic_views(doc):
    """Projeções exatas da primeira face visível; cores sem iluminação."""
    h,w,d=doc.occupied.shape
    result={}
    for key,shape in [('front',(h,w)),('back',(h,w)),('left',(h,d)),('right',(h,d)),('top',(d,w)),('bottom',(d,w))]:
        out=np.zeros((*shape,4),dtype='uint8')
        if key in ('front','back'):
            order=range(d-1,-1,-1) if key=='front' else range(d)
            for z in order:
                mask=doc.occupied[:,:,z] & (out[:,:,3]==0)
                out[mask,:3]=doc.colors[:,:,z,4 if key=='front' else 5][mask];out[mask,3]=255
            if key=='back':out=out[:,::-1]
        elif key in ('left','right'):
            order=range(w) if key=='left' else range(w-1,-1,-1)
            for x in order:
                mask=doc.occupied[:,x,:] & (out[:,:,3]==0)
                out[mask,:3]=doc.colors[:,x,:,1 if key=='left' else 0][mask];out[mask,3]=255
            if key=='right':out=out[:,::-1]
        else:
            order=range(h) if key=='top' else range(h-1,-1,-1)
            for y in order:
                mask=doc.occupied[y].T & (out[:,:,3]==0)
                out[mask,:3]=doc.colors[y,:,:,2 if key=='top' else 3].transpose(1,0,2)[mask];out[mask,3]=255
            if key=='bottom':out=out[::-1]
        result[key]=Image.fromarray(out)
    return result


def export_orthographic(doc,folder):
    """Grava seis projeções PNG e uma folha de referência lado a lado."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    views=orthographic_views(doc)
    for key,img in views.items():img.save(folder/f'{key}.png')
    cell=max(max(im.size) for im in views.values())
    sheet=Image.new('RGBA',(cell*6,cell))
    for i,key in enumerate(VIEW_KEYS):sheet.paste(views[key],(i*cell,0))
    sheet.save(folder/'six_views.png')
    return folder


def outline_image(image,color=(15,15,20),width=1):
    """Cria um contorno expandindo a máscara alfa e compondo-a atrás da imagem."""
    alpha=image.getchannel('A');expanded=alpha.filter(ImageFilter.MaxFilter(2*width+1))
    layer=Image.new('RGBA',image.size,(*color,0));layer.putalpha(expanded)
    return Image.alpha_composite(layer,image)


def sprite_sheet(frames,columns=8):
    """Organiza quadros RGBA em uma grade com número de colunas configurável."""
    if not frames:raise ValueError('Nenhum quadro para exportar.')
    w,h=frames[0].size;columns=min(columns,len(frames));rows=math.ceil(len(frames)/columns)
    sheet=Image.new('RGBA',(w*columns,h*rows))
    for i,frame in enumerate(frames):sheet.paste(frame,(i%columns*w,i//columns*h))
    return sheet


def save_gif(frames,path,duration=100):
    """Converte quadros para uma paleta comum e reserva um índice para transparência."""
    # Paleta global de 255 cores + índice 255 reservado à transparência.
    overview=sprite_sheet(frames).convert('RGB')
    palette=overview.quantize(colors=255)
    palette_data=palette.getpalette();palette_data[765:768]=palette_data[:3];palette.putpalette(palette_data)
    converted=[]
    for im in frames:
        p=im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)
        data=np.array(p);data[data==255]=0;data[np.array(im.getchannel('A'))<128]=255
        p=Image.fromarray(data,mode='P');p.putpalette(palette.getpalette());p.info['transparency']=255
        converted.append(p)
    converted[0].save(path,save_all=True,append_images=converted[1:],duration=duration,loop=0,transparency=255,disposal=2,optimize=False)


def export_atlas_obj(mesh,path):
    """Um material e uma célula de atlas por cor, com UV no centro da célula."""
    if not len(mesh.quads):raise ValueError('Modelo vazio.')
    path=Path(path).with_suffix('.obj')
    tag=hashlib.sha256(path.name.encode()).hexdigest()[:10]
    mtl=path.with_name(f'material_{tag}.mtl');texture=path.with_name(f'atlas_{tag}.png')
    # A mesma cor reutiliza a mesma célula do atlas e o mesmo índice de UV.
    colors,indices=np.unique(mesh.colors,axis=0,return_inverse=True)
    n=math.ceil(math.sqrt(len(colors)));tile=4
    pixels=np.zeros((n*tile,n*tile,3),dtype='uint8')
    for i,c in enumerate(colors):pixels[(i//n)*tile:(i//n+1)*tile,(i%n)*tile:(i%n+1)*tile]=c
    Image.fromarray(pixels).save(texture)
    mtl.write_text(f'newmtl palette\nKd 1 1 1\nKa 0 0 0\nKs 0 0 0\nd 1\nillum 1\nmap_Kd {texture.name}\n',encoding='utf-8')
    with path.open('w',encoding='utf-8',newline='\n') as f:
        f.write(f'# VoxelSprite Studio 2.0\nmtllib {mtl.name}\no Model\n')
        for v in mesh.quads.reshape(-1,3):f.write(f'v {v[0]:g} {v[1]:g} {v[2]:g}\n')
        for i in range(len(colors)):f.write(f'vt {(i%n+.5)/n:.8f} {1-(i//n+.5)/n:.8f}\n')
        for normal in mesh.normals:f.write(f'vn {normal[0]:g} {normal[1]:g} {normal[2]:g}\n')
        f.write('usemtl palette\n')
        for i,c in enumerate(indices):
            f.write('f '+' '.join(f'{i*4+j+1}/{c+1}/{i+1}' for j in range(4))+'\n')
    return path,mtl,texture
