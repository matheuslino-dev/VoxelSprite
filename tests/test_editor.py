import tempfile
import json
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from voxelsprite.core import voxelize
from voxelsprite.document import Document,save_project,load_project,build_from_images
from voxelsprite.picking import raycast
from voxelsprite.exports import orthographic_views,export_atlas_obj,save_gif,sprite_sheet,export_orthographic

class EditorTests(unittest.TestCase):
    def document(self):
        a=np.full((3,4,4),255,dtype='uint8');a[:,:,:3]=[90,120,180]
        return Document.from_mesh(voxelize(a,2,0),padding=2)
    def test_mesh_to_document_preserves_geometry_and_face_colors(self):
        a=np.full((3,4,4),255,dtype='uint8');a[:,:,:3]=[255,0,0];back=a.copy();back[:,:,:3]=[0,255,0]
        m=voxelize(a,2,0,views={'back':back});doc=Document.from_mesh(m);rebuilt=doc.mesh()
        np.testing.assert_array_equal(m.quads,rebuilt.quads);np.testing.assert_array_equal(m.colors,rebuilt.colors)
        self.assertEqual(m.voxel_count,rebuilt.voxel_count)
    def test_face_paint_opacity_undo_redo(self):
        doc=self.document();p=(2,2,3);old=doc.colors[p].copy()
        doc.begin();doc.brush(p,4,1,'paint',[250,0,0],.5);doc.commit()
        np.testing.assert_array_equal(doc.colors[p][4],np.rint(old[4]*.5+np.array([250,0,0])*.5))
        np.testing.assert_array_equal(doc.colors[p][:4],old[:4])
        doc.undo();np.testing.assert_array_equal(doc.colors[p],old);doc.redo();self.assertFalse(np.array_equal(doc.colors[p],old))
    def test_add_erase_and_rollback(self):
        doc=self.document();p=(2,2,3);n=doc.occupied.sum()
        doc.begin();doc.brush(p,4,1,'add',[1,2,3]);doc.commit();self.assertEqual(doc.occupied.sum(),n+1)
        doc.begin();doc.brush((2,2,4),4,1,'erase',[0,0,0]);doc.rollback();self.assertEqual(doc.occupied.sum(),n+1)
        doc.undo();self.assertEqual(doc.occupied.sum(),n)
    def test_fill_connected_surface_not_other_sides(self):
        doc=self.document();old=doc.colors.copy();doc.begin();doc.fill((2,2,3),4,[255,0,255]);doc.commit()
        self.assertEqual(np.count_nonzero(np.all(doc.colors[:,:,:,4,:]==[255,0,255],axis=-1)),12)
        np.testing.assert_array_equal(doc.colors[:,:,:,:4],old[:,:,:,:4])
    def test_selection_copy_move_and_collisions(self):
        doc=self.document();doc.selection={(2,2,3)};n=doc.occupied.sum()
        with self.assertRaises(ValueError):doc.transform_selection((0,1,0))
        doc.transform_selection((0,0,1),True);self.assertEqual(doc.occupied.sum(),n+1);self.assertIn((2,2,4),doc.selection)
        doc.transform_selection((0,0,1));self.assertFalse(doc.exists((2,2,4)));self.assertTrue(doc.exists((2,2,5)))
        doc.undo();self.assertTrue(doc.exists((2,2,4)));self.assertFalse(doc.exists((2,2,5)))
    def test_save_load_roundtrip_and_validation(self):
        doc=self.document();doc.colors[2,2,2]=np.arange(18).reshape(6,3)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'modelo.json';save_project(doc,p,{'outline':True});other,settings=load_project(p)
            np.testing.assert_array_equal(other.occupied,doc.occupied)
            np.testing.assert_array_equal(other.colors[other.occupied],doc.colors[doc.occupied]);self.assertTrue(settings['outline'])
            data=json.loads(p.read_text());data['voxels'][0]=[-1,0,0];p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):load_project(p)
    def test_raycast_six_directions(self):
        doc=Document((3,3,3));doc.set_voxel((1,1,1),True,np.ones((6,3))*100);doc.commit()
        for origin,direction,face in [([0,0,10],[0,0,-1],4),([0,0,-10],[0,0,1],5),([10,0,0],[-1,0,0],0),([-10,0,0],[1,0,0],1),([0,10,0],[0,-1,0],2),([0,-10,0],[0,1,0],3)]:
            hit=raycast(doc,np.array(origin),np.array(direction));self.assertEqual(hit,((1,1,1),face,False))
        self.assertIsNone(raycast(doc,np.array([10,10,10]),np.array([0,0,-1])))
    def test_top_bottom_masks_and_orientation(self):
        front=np.full((3,4,4),255,dtype='uint8');front[:,:,:3]=[255,0,0]
        top=np.full((2,4,4),255,dtype='uint8');top[0,:,:3]=[0,255,0];top[1,:,:3]=[0,0,255]
        bottom=top[::-1].copy()
        mesh=voxelize(front,2,views={'top':top,'bottom':bottom})
        doc=Document.from_mesh(mesh,padding=0);views=orthographic_views(doc)
        np.testing.assert_array_equal(np.array(views['top']),top);np.testing.assert_array_equal(np.array(views['bottom']),bottom)
        top[0,0,3]=0;mesh=voxelize(front,2,views={'top':top});self.assertEqual(mesh.voxel_count,21)
    def test_orthographic_six_colors(self):
        doc=Document((1,1,1));colors=np.array([[255,0,0],[0,255,0],[0,0,255],[255,255,0],[255,0,255],[0,255,255]])
        doc.set_voxel((0,0,0),True,colors);doc.commit();views=orthographic_views(doc)
        for key,index in [('front',4),('back',5),('left',1),('right',0),('top',2),('bottom',3)]:
            np.testing.assert_array_equal(np.array(views[key])[0,0,:3],colors[index])
    def test_import_without_front(self):
        with tempfile.TemporaryDirectory() as temp:
            a=np.full((8,6,4),255,dtype='uint8');a[:,:,:3]=[70,80,90];p=Path(temp)/'view.png';Image.fromarray(a).save(p)
            for key in ('back','left','right','top','bottom'):
                doc=build_from_images({key:p},depth=6);self.assertGreater(doc.occupied.sum(),0)
    def test_atlas_and_gif_and_sheet(self):
        doc=self.document()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);obj,mtl,atlas=export_atlas_obj(doc.mesh(),p/'modelo.obj')
            self.assertTrue(atlas.exists());self.assertIn('map_Kd '+atlas.name,mtl.read_text());self.assertIn('vt ',obj.read_text())
            frames=[]
            for x in [0,1,2]:
                a=Image.new('RGBA',(8,8));a.putpixel((x,3),(250,40,100,255));frames.append(a)
            save_gif(frames,p/'test.gif');gif=Image.open(p/'test.gif');self.assertEqual(gif.n_frames,3);self.assertEqual(gif.convert('RGBA').getpixel((7,7))[3],0);gif.close()
            sheet=sprite_sheet(frames,2);self.assertEqual(sheet.size,(16,16))
            export_orthographic(doc,p/'views');self.assertEqual(len(list((p/'views').glob('*.png'))),7)
    def test_resize_keeps_voxels_and_rejects_crop(self):
        doc=self.document();n=doc.occupied.sum();new=doc.resize(16);self.assertEqual(new.occupied.sum(),n)
        doc=Document((16,16,16));doc.set_voxel((0,0,0),True,np.zeros((6,3)));doc.commit()
        with self.assertRaises(ValueError):doc.resize(8)

if __name__=='__main__':unittest.main()
