"""Colab-specific patches for functions."""

__all__ = ['cv2_im', 'cv_im']

import cv2
from IPython import display
import PIL

class cv2_im:
    def show(a):
        """A replacement for cv2.imshow() for use in Jupyter notebooks.

        Args:
          a: np.ndarray. shape (N, M) or (N, M, 1) is an NxM grayscale image. For
            example, a shape of (N, M, 3) is an NxM BGR color image, and a shape of
            (N, M, 4) is an NxM BGRA color image.
          t: str. The title of the image.
        """
        a = a.clip(0, 255).astype('uint8')
        # cv2 stores colors as BGR; convert to RGB
        if a.ndim == 3:
            if a.shape[2] == 4:
                a = cv2.cvtColor(a, cv2.COLOR_BGRA2RGBA)
            else:
                a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
        display.display(PIL.Image.fromarray(a))

    def title(t):
        if t is not None:
          print(t)

cv_im = cv2_im
