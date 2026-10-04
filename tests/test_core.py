"""Testes do motor: imagens de entrada, voxelização, malha e arquivo OBJ."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from voxelsprite.core import voxelize, read_sprite, export_obj

class CoreTests(unittest.TestCase):
    """Verifica resultados geométricos e de exportação sem abrir a interface."""

    def sprite(self,h,w):
        """Cria uma imagem RGBA opaca para ser usada como entrada de teste."""
        a = np.full((h,w,4),255,dtype='uint8')
        a[:,:,:3] = [22,120,220]
        return a

    def test_one_voxel_has_six_outward_faces(self):
        mesh = voxelize(self.sprite(1,1),1,0)
        self.assertEqual(mesh.voxel_count,1)
        self.assertEqual(len(mesh.quads),6)
        cross = np.cross(mesh.quads[:,1]-mesh.quads[:,0],mesh.quads[:,2]-mesh.quads[:,0])
        np.testing.assert_array_equal(cross,mesh.normals)
        np.testing.assert_allclose(mesh.quads.min(axis=(0,1)),[-.5,-.5,-.5])
        np.testing.assert_allclose(mesh.quads.max(axis=(0,1)),[.5,.5,.5])

    def test_solid_box_has_no_internal_faces(self):
        mesh = voxelize(self.sprite(3,4),5,0)
        self.assertEqual(mesh.voxel_count,60)
        self.assertEqual(len(mesh.quads),2*(3*4+3*5+4*5))
        self.assertEqual(mesh.vertex_data().shape,(len(mesh.quads)*6,9))

    def test_transparent_hole_stays_open(self):
        a = self.sprite(3,3); a[1,1,3] = 0
        mesh = voxelize(a,2,0)
        self.assertEqual(mesh.voxel_count,16)
        self.assertEqual(len(mesh.quads),48)

    def test_alpha_cutoff(self):
        a=self.sprite(1,2);a[0,0,3]=127
        self.assertEqual(voxelize(a,1,0,128).voxel_count,1)
        self.assertEqual(voxelize(a,1,0,127).voxel_count,2)
        a[:,:,3]=0
        with self.assertRaises(ValueError): voxelize(a)

    def test_rounding_symmetric_and_less_volume(self):
        a=self.sprite(9,9)
        for d in [1,2,9,10]:
            mesh=voxelize(a,d,1)
            self.assertLessEqual(mesh.voxel_count,9*9*d)
            self.assertAlmostEqual(float(mesh.quads[:,:,2].min()),-float(mesh.quads[:,:,2].max()))
        self.assertLess(voxelize(a,10,1).voxel_count,voxelize(a,10,0).voxel_count)

    def test_image_orientation_and_color(self):
        a=self.sprite(2,1);a[0,0,:3]=[255,0,0];a[1,0,:3]=[0,0,255]
        mesh=voxelize(a,1,0)
        front=mesh.normals[:,2]==1
        centers=mesh.quads[front].mean(axis=1)
        colors=mesh.colors[front]
        np.testing.assert_array_equal(colors[centers[:,1]>0],[[255,0,0]])

    def test_resize_preserves_palette_and_aspect(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'sprite.png'
            a=self.sprite(16,32);a[:,::2,:3]=[255,0,0]
            Image.fromarray(a).save(p)
            resized,original=read_sprite(p,16)
            self.assertEqual(resized.shape,(8,16,4))
            self.assertEqual(original,(32,16))
            self.assertTrue(set(map(tuple,resized[:,:,:3].reshape(-1,3))) <= {(255,0,0),(22,120,220)})

    def test_obj_materials_and_valid_indices(self):
        a=self.sprite(1,2);a[0,0,:3]=[255,0,0]
        mesh=voxelize(a,2,0)
        with tempfile.TemporaryDirectory() as temp:
            obj,mtl=export_obj(mesh,Path(temp)/'meu cogumelo colorido.obj')
            lines=obj.read_text().splitlines()
            verts=[l for l in lines if l.startswith('v ')]
            norms=[l for l in lines if l.startswith('vn ')]
            faces=[l for l in lines if l.startswith('f ')]
            self.assertEqual(len(verts),len(mesh.quads)*4)
            self.assertEqual(len(faces),len(mesh.quads))
            self.assertIn('mtllib '+mtl.name,lines)
            materials={l.split()[1] for l in mtl.read_text().splitlines() if l.startswith('newmtl ')}
            self.assertEqual(len(materials),2)
            for line in lines:
                if line.startswith('usemtl '): self.assertIn(line.split()[1],materials)
            for f in faces:
                for item in f.split()[1:]:
                    v,n=map(int,item.split('//'))
                    self.assertTrue(1<=v<=len(verts));self.assertTrue(1<=n<=len(norms))
            self.assertFalse(list(Path(temp).glob('*.tmp')))

if __name__=='__main__': unittest.main()
