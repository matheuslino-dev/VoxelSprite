"""Viewport editável com OpenGL, projeção pixelada e picking de voxels."""
import math
import numpy as np
import moderngl
from PIL import Image
from PySide6.QtCore import Qt,Signal,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QPen,QPolygonF
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from .scene import Scene,camera_matrix
from .picking import raycast
from .core import FACES
from .exports import outline_image

class Viewport(QOpenGLWidget):
    failed=Signal(str)
    stroke_started=Signal()
    stroke_finished=Signal()
    hit=Signal(object,int)
    selection_made=Signal(object,bool)
    camera_changed=Signal()
    selection_transform=Signal(object,bool)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.ctx=self.scene=None;self.mesh=None;self.doc=None;self.dirty=False;self.error=''
        self.yaw=35.;self.pitch=25.;self.distance=80.;self.radius=20.;self.target=np.zeros(3)
        self.orthographic=True;self.lighting=True;self.light=(-.4,.8,1.)
        self.grid_visible=True;self.outline=False;self.outline_color=(.04,.04,.05);self.background=(.035,.035,.04)
        self.pixel_scale=2;self.tool='paint';self.last=None;self.hover=None;self.space=False
        self.drag_select=None;self.select_end=None;self.stroke=False;self.shift_select=False;self.drag_transform=None;self.transform_delta=np.zeros(3,dtype=int)
        self.render_texture=self.render_depth=self.render_fbo=None
        self.setMinimumSize(320,300);self.setMouseTracking(True);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def initializeGL(self):
        try:
            self.ctx=moderngl.create_context(require=330);self.scene=Scene(self.ctx)
            self.context().aboutToBeDestroyed.connect(self.cleanup)
            self.dirty=True
        except Exception as exc:
            self.error=f'Não foi possível iniciar OpenGL 3.3. Atualize o driver de vídeo.\n{exc}';self.failed.emit(self.error)

    def set_document(self,doc,reset=True):
        self.doc=doc;self.mesh=doc.mesh() if doc else None;self.dirty=True
        if reset:self.hover=None
        if reset:self.reset_camera()
        else:self.update()

    def set_mesh(self,mesh):
        self.mesh=mesh;self.dirty=True;self.reset_camera()

    def reset_camera(self,front=False):
        self.yaw,self.pitch=(0.,0.) if front else (35.,25.)
        self.target=np.zeros(3)
        if self.mesh is not None and len(self.mesh.quads):
            points=self.mesh.quads.reshape(-1,3);lo,hi=points.min(axis=0),points.max(axis=0)
            self.target=(lo+hi)/2;self.radius=max(float(np.linalg.norm(hi-lo)/2),1.)
        elif self.doc is not None:self.radius=max(self.doc.occupied.shape)*.7
        aspect=self.width()/max(self.height(),1)
        self.distance=self.radius*3.8/max(min(aspect,1.),.3)
        self.camera_changed.emit();self.update()

    def matrix(self,aspect=None):
        return camera_matrix(self.yaw,self.pitch,self.distance,self.target,aspect or self.width()/max(self.height(),1),self.radius,self.orthographic)

    def _upload(self):
        if self.dirty:
            self.scene.upload(self.mesh)
            self.scene.grid(self.doc.occupied.shape if self.doc else (32,32,32))
            self.dirty=False

    def paintGL(self):
        if self.error or not self.ctx:return
        try:
            self._upload()
            scale=self.devicePixelRatioF();w=max(1,int(self.width()*scale));h=max(1,int(self.height()*scale))
            size=(max(1,w//self.pixel_scale),max(1,h//self.pixel_scale))
            if self.render_fbo is None or self.render_fbo.size!=size:
                self.release_target()
                self.render_texture=self.ctx.texture(size,4);self.render_texture.filter=(moderngl.NEAREST,moderngl.NEAREST)
                self.render_texture.repeat_x=False;self.render_texture.repeat_y=False
                self.render_depth=self.ctx.depth_renderbuffer(size)
                self.render_fbo=self.ctx.framebuffer([self.render_texture],self.render_depth)
            self.scene.draw(self.render_fbo,self.matrix(),self.lighting,self.light,self.grid_visible)
            fbo=self.ctx.detect_framebuffer(self.defaultFramebufferObject());fbo.use();self.ctx.viewport=(0,0,w,h)
            self.ctx.enable_only(0);self.ctx.scissor=None;fbo.color_mask=(True,True,True,True)
            self.render_texture.use(0)
            self.scene.blit['frame'].value=0;self.scene.blit['background'].value=self.background
            self.scene.blit['outline'].value=self.outline;self.scene.blit['outline_color'].value=self.outline_color
            self.scene.blit_vao.render(moderngl.TRIANGLE_STRIP)
        except Exception as exc:self.error=str(exc);self.failed.emit(self.error)

    def project(self,points):
        p=np.column_stack((points,np.ones(len(points))))@self.matrix().T
        good=p[:,3]>0
        xy=p[:,:2]/np.where(abs(p[:,3:4])<1e-12,1e-12,p[:,3:4])
        return np.column_stack(((xy[:,0]+1)*self.width()/2,(1-xy[:,1])*self.height()/2)),good

    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self)
        if self.error:
            painter.fillRect(self.rect(),QColor('#111114'));painter.setPen(QColor('#efb4be'))
            painter.drawText(self.rect().adjusted(30,30,-30,-30),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,self.error)
        else:
            if self.hover and self.doc and self.tool!='orbit':
                p,face,ground=self.hover
                center=self.doc.world_centers([p])[0]
                corners=np.array(FACES[face][2])-.5+center
                xy,good=self.project(corners)
                if np.all(good):
                    painter.setPen(QPen(QColor('#ff43bd'),2));painter.setBrush(QColor(255,40,175,35))
                    painter.drawPolygon(QPolygonF([QPointF(*point) for point in xy]))
            if self.doc and self.doc.selection:
                points=self.doc.world_centers(list(self.doc.selection))
                if self.drag_transform is not None:
                    dy,dx,dz=self.transform_delta;points=points+np.array([dx,-dy,dz])
                lo=points.min(axis=0)-.5;hi=points.max(axis=0)+.5
                corners=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
                xy,good=self.project(corners)
                painter.setPen(QPen(QColor('#55ead3'),1,Qt.PenStyle.DashLine));painter.setBrush(Qt.BrushStyle.NoBrush)
                if np.all(good):painter.drawRect(QRectF(QPointF(*xy.min(axis=0)),QPointF(*xy.max(axis=0))))
            if self.drag_select is not None:
                painter.setPen(QPen(QColor('#55ead3'),1,Qt.PenStyle.DashLine));painter.setBrush(QColor(60,230,190,30))
                painter.drawRect(QRectF(self.drag_select,self.select_end or self.drag_select).normalized())
            painter.setPen(QColor('#6d6d78'))
            painter.drawText(18,26,'PINTAR / MODELAR' if self.tool!='orbit' else 'NAVEGAR')
            painter.drawText(18,self.height()-16,'ORTOGRÁFICA' if self.orthographic else 'PERSPECTIVA')
        painter.end()

    def ray(self,pos):
        inv=np.linalg.inv(self.matrix());x=2*pos.x()/self.width()-1;y=1-2*pos.y()/self.height()
        a=inv@np.array([x,y,-1,1]);b=inv@np.array([x,y,1,1]);a=a[:3]/a[3];b=b[:3]/b[3]
        v=b-a;v/=np.linalg.norm(v);return a,v

    def pick(self,pos):
        if not self.doc:return None
        origin,direction=self.ray(pos);hit=raycast(self.doc,origin,direction)
        if hit:return hit
        # Plano do chão permite criar o primeiro voxel em uma grade vazia.
        floor=-self.doc.occupied.shape[0]/2
        if abs(direction[1])>1e-8:
            t=(floor-origin[1])/direction[1]
            if t>=0:
                point=origin+t*direction;point[1]+=1e-4
                coord=tuple(self.doc.coords_from_world([point])[0])
                if self.doc.inside(coord):return coord,2,True
        return None

    def mousePressEvent(self,event):
        self.setFocus();self.last=event.position()
        if event.button()==Qt.MouseButton.LeftButton and not self.space and self.tool!='orbit':
            if self.tool=='select':
                hit=self.pick(event.position())
                if hit and hit[0] in self.doc.selection and event.modifiers()&(Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.ControlModifier):
                    self.drag_transform=(self.doc.world_centers([hit[0]])[0],self.ray(event.position())[1],self.ray(event.position()),bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier))
                    self.transform_delta=np.zeros(3,dtype=int)
                else:
                    self.drag_select=event.position();self.select_end=event.position();self.shift_select=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
            else:
                self.stroke=True;self.stroke_started.emit();self.hover=self.pick(event.position())
                if self.hover:self.hit.emit(self.hover,int(event.modifiers().value))
        self.update()

    def mouseMoveEvent(self,event):
        delta=event.position()-self.last if self.last else QPointF()
        self.last=event.position()
        if event.buttons()&Qt.MouseButton.MiddleButton or (self.space and event.buttons()&Qt.MouseButton.LeftButton):
            y,p=math.radians(self.yaw),math.radians(self.pitch)
            right=np.array([math.cos(y),0,-math.sin(y)]);up=np.array([-math.sin(p)*math.sin(y),math.cos(p),-math.sin(p)*math.cos(y)])
            self.target+=(-right*delta.x()+up*delta.y())*self.distance/max(self.height(),1)*.75
            self.camera_changed.emit()
        elif event.buttons()&Qt.MouseButton.RightButton or (self.tool=='orbit' and event.buttons()&Qt.MouseButton.LeftButton):
            self.yaw+=delta.x()*.5;self.pitch=max(-89.9,min(89.9,self.pitch+delta.y()*.5));self.camera_changed.emit()
        elif self.drag_transform is not None:
            anchor,normal,start,copy=self.drag_transform
            origin,direction=self.ray(event.position());o0,v0=start
            if abs(np.dot(direction,normal))>1e-8:
                now=origin+direction*np.dot(anchor-origin,normal)/np.dot(direction,normal)
                initial=o0+v0*np.dot(anchor-o0,normal)/np.dot(v0,normal)
                dx,dy,dz=np.rint(now-initial).astype(int);self.transform_delta=np.array([-dy,dx,dz])
        elif self.drag_select is not None:self.select_end=event.position()
        else:
            self.hover=self.pick(event.position())
            if self.stroke and event.buttons()&Qt.MouseButton.LeftButton and self.hover:self.hit.emit(self.hover,int(event.modifiers().value))
        self.update()

    def mouseReleaseEvent(self,event):
        if self.drag_transform is not None and event.button()==Qt.MouseButton.LeftButton:
            if np.any(self.transform_delta):self.selection_transform.emit(tuple(map(int,self.transform_delta)),self.drag_transform[3])
            self.drag_transform=None;self.transform_delta=np.zeros(3,dtype=int)
        if self.drag_select is not None and event.button()==Qt.MouseButton.LeftButton:
            rect=QRectF(self.drag_select,event.position()).normalized();self.selection_made.emit(rect,self.shift_select)
            self.drag_select=None;self.select_end=None
        if self.stroke and event.button()==Qt.MouseButton.LeftButton:self.stroke=False;self.stroke_finished.emit()
        self.update()

    def wheelEvent(self,event):
        self.distance*=math.exp(-event.angleDelta().y()/120*.12);self.distance=max(self.radius*.15,min(self.radius*30,self.distance))
        self.camera_changed.emit();self.update()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Space:self.space=True;event.accept()
        else:super().keyPressEvent(event)
    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_Space:self.space=False;event.accept()
        else:super().keyReleaseEvent(event)
    def focusOutEvent(self,event):
        self.space=False
        if self.stroke:self.stroke=False;self.stroke_finished.emit()
        super().focusOutEvent(event)

    def render_sprite(self,size=256,yaw=None,pitch=None,fit=True):
        if not self.ctx or self.error:raise ValueError('A exportação de sprites precisa da visualização OpenGL funcionando.')
        self.makeCurrent();self._upload()
        try:
            target=self.target;distance=self.distance
            if fit:
                if self.mesh is None or not len(self.mesh.quads):raise ValueError('Modelo vazio.')
                pts=self.mesh.quads.reshape(-1,3);lo,hi=pts.min(axis=0),pts.max(axis=0)
                target=(lo+hi)/2;radius=max(float(np.linalg.norm(hi-lo)/2),1.);distance=radius*3.1
            matrix=camera_matrix(self.yaw if yaw is None else yaw,self.pitch if pitch is None else pitch,distance,target,1,self.radius,True)
            im=self.scene.frame(matrix,size,self.lighting,self.light)
            if self.outline:im=outline_image(im,tuple(int(c*255) for c in self.outline_color))
            return im
        finally:self.doneCurrent();self.update()

    def release_target(self):
        for r in (self.render_fbo,self.render_depth,self.render_texture):
            if r is not None:r.release()
        self.render_fbo=self.render_depth=self.render_texture=None

    def cleanup(self):
        if self.ctx is None:return
        self.makeCurrent();self.release_target()
        if self.scene:self.scene.release()
        self.scene=None;self.ctx=None;self.doneCurrent()
