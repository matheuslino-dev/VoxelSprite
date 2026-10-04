import unittest
import tempfile
from pathlib import Path
import numpy as np
from voxelsprite.core import voxelize,export_obj


def solid(h,w,color):
    image=np.full((h,w,4),255,dtype='uint8');image[:,:,:3]=color
    return image


def face_colors(mesh,normal):
    return mesh.colors[np.all(mesh.normals==normal,axis=1)]

class MultiViewTests(unittest.TestCase):
    def test_colors_go_to_their_own_faces(self):
        front=solid(3,4,[255,0,0])
        views={'back':solid(3,4,[0,255,0]),'left':solid(3,2,[0,0,255]),'right':solid(3,2,[255,255,0])}
        m=voxelize(front,2,0,views=views)
        for normal,color in [((0,0,1),[255,0,0]),((0,0,-1),[0,255,0]),((-1,0,0),[0,0,255]),((1,0,0),[255,255,0])]:
            self.assertTrue(np.all(face_colors(m,normal)==color))

    def test_back_camera_horizontal_orientation(self):
        front=solid(1,3,[200,200,200]);back=front.copy()
        back[0,:,:3]=[[255,0,0],[0,255,0],[0,0,255]]
        m=voxelize(front,1,0,views={'back':back})
        select=m.normals[:,2]==-1
        centers=m.quads[select].mean(axis=1)
        np.testing.assert_array_equal(m.colors[select][np.argsort(centers[:,0])],[[0,0,255],[0,255,0],[255,0,0]])

    def test_side_camera_horizontal_orientation(self):
        front=solid(1,2,[200,200,200]);side=solid(1,3,[0,0,0])
        side[0,:,:3]=[[255,0,0],[0,255,0],[0,0,255]]
        m=voxelize(front,3,views={'left':side,'right':side})
        for sign,expected in [(-1,[[255,0,0],[0,255,0],[0,0,255]]),(1,[[0,0,255],[0,255,0],[255,0,0]])]:
            selected=m.normals[:,0]==sign
            centers=m.quads[selected].mean(axis=1)
            np.testing.assert_array_equal(m.colors[selected][np.argsort(centers[:,2])],expected)

    def test_masks_intersect_and_carve_geometry(self):
        front=solid(3,4,[255,0,0]);side=solid(3,5,[0,255,0]);side[:,:,3]=0
        side[:,1:4,3]=255;side[1,2,3]=0
        m=voxelize(front,5,views={'left':side})
        self.assertEqual(m.voxel_count,4*8)
        # Todas as faces se apoiam em voxels pertencentes às duas silhuetas.
        centers=m.quads.mean(axis=1)-m.normals*.5
        ys=np.rint(3/2-.5-centers[:,1]).astype(int)
        zs=np.rint(centers[:,2]+5/2-.5).astype(int)
        self.assertTrue(np.all(side[ys,zs,3]==255))

    def test_back_mask_uses_reversed_x(self):
        front=solid(2,3,[255,0,0]);back=solid(2,3,[0,255,0]);back[:,0,3]=0
        m=voxelize(front,2,0,views={'back':back})
        self.assertEqual(m.voxel_count,8)
        self.assertEqual(m.quads[:,:,0].max(),.5)

    def test_back_without_sides_retains_mathematical_rounding(self):
        front=solid(9,9,[255,0,0]);back=solid(9,9,[0,255,0])
        rounded=voxelize(front,10,1,views={'back':back})
        flat=voxelize(front,10,0,views={'back':back})
        self.assertLess(rounded.voxel_count,flat.voxel_count)
        self.assertTrue(np.all(face_colors(rounded,(0,0,-1))==[0,255,0]))

    def test_side_replaces_rounding(self):
        f=solid(3,4,[1,2,3]);v={'right':solid(3,5,[4,5,6])}
        self.assertEqual(voxelize(f,5,0,views=v).voxel_count,60)
        self.assertEqual(voxelize(f,5,1,views=v).voxel_count,60)

    def test_missing_side_mirror_is_optional(self):
        f=solid(2,3,[255,0,0]);v={'left':solid(2,4,[0,255,0])}
        mirrored=voxelize(f,4,views=v)
        fallback=voxelize(f,4,views=v,mirror_missing_side=False)
        self.assertTrue(np.all(face_colors(mirrored,(1,0,0))==[0,255,0]))
        self.assertTrue(np.all(face_colors(fallback,(1,0,0))==[255,0,0]))

    def test_dominant_fallback_does_not_repeat_small_face_details(self):
        f=solid(2,5,[230,180,100]);f[0,2,:3]=[10,10,10]
        m=voxelize(f,1,0,fallback='dominant')
        self.assertTrue(np.all(face_colors(m,(0,0,-1))==[230,180,100]))
        self.assertTrue(np.any(np.all(face_colors(m,(0,0,1))==[10,10,10],axis=1)))

    def test_empty_or_incompatible_views_report_error(self):
        front=solid(2,2,[1,2,3]);side=solid(2,2,[4,5,6]);side[:,:,3]=0
        with self.assertRaisesRegex(ValueError,'pixels visíveis'):voxelize(front,views={'left':side})
        side[0,:,3]=255;front[0,:,3]=0
        with self.assertRaisesRegex(ValueError,'volume em comum'):voxelize(front,views={'left':side})

    def test_multiple_colors_survive_obj_export(self):
        m=voxelize(solid(2,2,[255,0,0]),2,0,views={'back':solid(2,2,[0,255,0]),'left':solid(2,2,[0,0,255])})
        with tempfile.TemporaryDirectory() as temp:
            obj,mtl=export_obj(m,Path(temp)/'views.obj')
            text=mtl.read_text()
            for color in ['1.000000 0.000000 0.000000','0.000000 1.000000 0.000000','0.000000 0.000000 1.000000']:
                self.assertIn('Kd '+color,text)

if __name__=='__main__':unittest.main()
