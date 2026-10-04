import math
import numpy as np
import moderngl
from PIL import Image

VERTEX='''#version 330
in vec3 in_position; in vec3 in_normal; in vec3 in_color;
uniform mat4 mvp;
out vec3 normal; out vec3 color;
void main(){gl_Position=mvp*vec4(in_position,1);normal=in_normal;color=in_color;}
'''
FRAGMENT='''#version 330
in vec3 normal; in vec3 color;
uniform bool lighting; uniform vec3 light_direction;
out vec4 frag;
void main(){float shade=lighting ? .45+.55*max(dot(normalize(normal),normalize(light_direction)),0.) : 1.;frag=vec4(color*shade,1);}
'''
BLIT_VERTEX='''#version 330
in vec2 pos;out vec2 uv;
void main(){gl_Position=vec4(pos,0,1);uv=pos*.5+.5;}
'''
BLIT_FRAGMENT='''#version 330
in vec2 uv;uniform sampler2D frame;uniform vec3 background;
uniform bool outline;uniform vec3 outline_color;out vec4 frag;
void main(){vec4 c=texture(frame,uv);vec2 p=1./vec2(textureSize(frame,0));
float a=max(max(texture(frame,uv+vec2(p.x,0)).a,texture(frame,uv-vec2(p.x,0)).a),max(texture(frame,uv+vec2(0,p.y)).a,texture(frame,uv-vec2(0,p.y)).a));
if(outline && c.a<.5 && a>.5)c=vec4(outline_color,1);
frag=vec4(mix(background,c.rgb,c.a),1);}
'''

def camera_matrix(yaw,pitch,distance,target,aspect,radius,orthographic=False):
    y,p=math.radians(yaw),math.radians(pitch)
    eye=np.array(target)+distance*np.array([math.cos(p)*math.sin(y),math.sin(p),math.cos(p)*math.cos(y)])
    forward=np.array(target)-eye;forward/=np.linalg.norm(forward)
    ref=[0,0,-1] if pitch>89 else [0,0,1] if pitch<-89 else [0,1,0]
    right=np.cross(forward,ref);right/=np.linalg.norm(right);up=np.cross(right,forward)
    view=np.eye(4);view[:3,:3]=[right,up,-forward];view[:3,3]=-view[:3,:3]@eye
    near,far=max(radius*.001,.001),max(distance+radius*8,100)
    projection=np.zeros((4,4))
    if orthographic:
        half=distance*math.tan(math.radians(20))
        projection[0,0]=1/(half*aspect);projection[1,1]=1/half
        projection[2,2]=-2/(far-near);projection[2,3]=-(far+near)/(far-near);projection[3,3]=1
    else:
        f=1/math.tan(math.radians(20));projection[0,0]=f/aspect;projection[1,1]=f
        projection[2,2]=(far+near)/(near-far);projection[2,3]=2*far*near/(near-far);projection[3,2]=-1
    return (projection@view).astype('f4')

class Scene:
    def __init__(self,ctx):
        self.ctx=ctx;self.program=ctx.program(vertex_shader=VERTEX,fragment_shader=FRAGMENT)
        self.vbo=self.vao=None
        self.blit=ctx.program(vertex_shader=BLIT_VERTEX,fragment_shader=BLIT_FRAGMENT)
        self.quad=ctx.buffer(np.array([-1,-1,1,-1,-1,1,1,1],dtype='f4').tobytes())
        self.blit_vao=ctx.vertex_array(self.blit,[(self.quad,'2f','pos')])
        self.grid_vbo=self.grid_vao=None
    def upload(self,mesh):
        for r in (self.vao,self.vbo):
            if r is not None:r.release()
        self.vao=self.vbo=None
        if mesh is not None and len(mesh.quads):
            self.vbo=self.ctx.buffer(mesh.vertex_data().tobytes())
            self.vao=self.ctx.vertex_array(self.program,[(self.vbo,'3f 3f 3f','in_position','in_normal','in_color')])
    def grid(self,shape):
        for r in (self.grid_vao,self.grid_vbo):
            if r is not None:r.release()
        h,w,d=shape;ys=-h/2;vertices=[]
        step=max(1,max(w,d)//32)
        for x in range(0,w+1,step):
            color=[.22,.22,.24] if x!=w//2 else [.48,.15,.27]
            for z in (-d/2,d/2):vertices.append([x-w/2,ys,z,0,1,0,*color])
        for z in range(0,d+1,step):
            color=[.22,.22,.24] if z!=d//2 else [.12,.36,.4]
            for x in (-w/2,w/2):vertices.append([x,ys,z-d/2,0,1,0,*color])
        # Bounding box edges.
        for a in range(3):
            other=[i for i in range(3) if i!=a];dims=[w,h,d]
            for v in (-1,1):
                for t in (-1,1):
                    for end in (-1,1):
                        p=[0.,0.,0.];p[a]=end*dims[a]/2;p[other[0]]=v*dims[other[0]]/2;p[other[1]]=t*dims[other[1]]/2
                        vertices.append([*p,0,1,0,.18,.18,.21])
        self.grid_vbo=self.ctx.buffer(np.array(vertices,dtype='f4').tobytes())
        self.grid_vao=self.ctx.vertex_array(self.program,[(self.grid_vbo,'3f 3f 3f','in_position','in_normal','in_color')])
    def draw(self,fbo,mvp,lighting=True,light=(-.4,.8,1),grid=False):
        fbo.use();self.ctx.viewport=(0,0,*fbo.size)
        # QPainter usa o mesmo contexto; restaure os estados que ele altera.
        self.ctx.scissor=None;self.ctx.enable_only(moderngl.DEPTH_TEST|moderngl.CULL_FACE)
        fbo.color_mask=(True,True,True,True);fbo.depth_mask=True
        self.ctx.front_face='ccw';self.ctx.cull_face='back'
        fbo.clear(0,0,0,0,depth=1)
        self.program['mvp'].write(mvp.T.copy().tobytes());self.program['light_direction'].value=light
        if grid and self.grid_vao:
            self.program['lighting'].value=False;self.grid_vao.render(moderngl.LINES)
        if self.vao:
            self.program['lighting'].value=lighting;self.vao.render(moderngl.TRIANGLES)
    def frame(self,mvp,size,lighting=True,light=(-.4,.8,1)):
        tex=self.ctx.texture((size,size),4);depth=self.ctx.depth_renderbuffer((size,size));fbo=self.ctx.framebuffer([tex],depth)
        try:
            self.draw(fbo,mvp,lighting,light)
            return Image.frombytes('RGBA',(size,size),fbo.read(components=4,alignment=1)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        finally:fbo.release();depth.release();tex.release()
    def release(self):
        for r in (self.vao,self.vbo,self.grid_vao,self.grid_vbo,self.program,self.blit_vao,self.quad,self.blit):
            if r is not None:r.release()
