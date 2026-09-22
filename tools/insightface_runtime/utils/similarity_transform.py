"""Small NumPy similarity transform used by the headless InsightFace adapter.
Implements the least-squares Umeyama transform. Avoids loading the full scientific
image-processing stack into a realtime player for a single 3x3 matrix operation.
"""
import numpy as np
class SimilarityTransform:
 def __init__(self,matrix=None,scale=1.,rotation=0.,translation=(0.,0.)):
  if matrix is not None:self.params=np.asarray(matrix,dtype=np.float64).copy()
  else:
   c,s=np.cos(rotation)*scale,np.sin(rotation)*scale
   self.params=np.array([[c,-s,translation[0]],[s,c,translation[1]],[0.,0.,1.]])
 def estimate(self,src,dst):
  src=np.asarray(src,np.float64);dst=np.asarray(dst,np.float64)
  if src.shape!=dst.shape or src.ndim!=2 or src.shape[1]!=2 or len(src)<2:return False
  a,b=src.mean(0),dst.mean(0);x,y=src-a,dst-b
  variance=np.sum(x*x)/len(x)
  if variance<1e-12 or not np.isfinite(x).all() or not np.isfinite(y).all():return False
  u,d,vt=np.linalg.svd(y.T@x/len(x))
  sign=np.array([1.,1. if np.linalg.det(u)*np.linalg.det(vt)>0 else -1.])
  rotation=(u*sign)@vt;scale=float(d@sign)/variance
  self.params=np.eye(3);self.params[:2,:2]=rotation*scale;self.params[:2,2]=b-self.params[:2,:2]@a
  return True
 def __add__(self,other):return SimilarityTransform(matrix=other.params@self.params)
 def __call__(self,coords):
  points=np.asarray(coords,np.float64)
  return points@self.params[:2,:2].T+self.params[:2,2]
