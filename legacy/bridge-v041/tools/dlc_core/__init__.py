# Derived from hacksider/Deep-Live-Cam, AGPL-3.0-or-later.
# Revision d759e31b11d9432afdfddce698c0f7c9a715e086.
# Selected upstream functions are unchanged; GUI imports and device selection are host-owned.
from typing import Any, Tuple, Optional
import cv2, numpy as np, threading, onnxruntime
Frame=np.ndarray
Face=Any
_HAS_TORCH_CUDA=False
_paste_cache={'soft_alpha':None,'alpha_size':0}
THREAD_SEMAPHORE=threading.Semaphore()
def run_inference(session,input_name,input_tensor):
    return session.run(None,{input_name:input_tensor})[0]
def _get_soft_alpha(size: int) -> np.ndarray:
    """Feathered alpha template in aligned-face space, cached.

    The legacy paste-back eroded and Gaussian-blurred the warped mask in
    output coordinates with kernels scaled to the output face size, which
    made the per-frame cost quartic in face linear size. Doing the same
    erode+blur once in aligned space and then warping the *soft* mask
    per-frame gives a visually equivalent feather at O(crop_area) cost —
    the feather radius scales naturally with the affine transform.
    """
    if _paste_cache['alpha_size'] != size:
        # Elliptical (not square) template — matches the gumroad edition's
        # _create_elliptical_mask. A full/eroded square leaves the aligned
        # crop's corners near-opaque, so the swapped square's straight edges
        # show as a visible box on the face. An ellipse (axes 0.44*size) zeroes
        # the corners and the heavy blur feathers smoothly into the original.
        center = (size // 2, size // 2)
        axes = (int(size * 0.44), int(size * 0.44))
        mask = np.zeros((size, size), dtype=np.uint8)
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (31, 31), 12)
        _paste_cache['soft_alpha'] = mask  # uint8 [0, 255] — blended via cv2 SIMD ops
        _paste_cache['alpha_size'] = size
    return _paste_cache['soft_alpha']

def _fast_paste_back(target_img: Frame, bgr_fake: np.ndarray, aimg: np.ndarray, M: np.ndarray) -> Frame:
    """Paste bgr_fake back onto target_img via the inverse affine of M.

    Restricts work to the face bbox in output coordinates and warps a
    precomputed feathered alpha template per-frame instead of running a
    size-scaled erode+blur on the warped mask. Cost is O(crop_area) regardless
    of how much of the frame the face occupies.
    """
    h, w = target_img.shape[:2]
    face_h, face_w = aimg.shape[:2]
    # inswapper's aligned-face space is square (128x128). _get_soft_alpha
    # caches a single NxN template keyed by N, so fail loudly if that ever
    # stops being true rather than silently mis-warping the alpha mask.
    assert face_h == face_w, f"Expected square aligned face, got {face_h}x{face_w}"
    IM = cv2.invertAffineTransform(M)

    # Bbox in output coords from the affine corners of the aligned-face square.
    corners = np.array(
        [[0, 0], [face_w, 0], [face_w, face_h], [0, face_h]], dtype=np.float32
    )
    transformed = (IM[:, :2] @ corners.T).T + IM[:, 2]
    x1 = int(np.floor(transformed[:, 0].min()))
    x2 = int(np.ceil(transformed[:, 0].max()))
    y1 = int(np.floor(transformed[:, 1].min()))
    y2 = int(np.ceil(transformed[:, 1].max()))
    if x1 >= x2 or y1 >= y2:
        return target_img

    # Small interpolation margin only — the feather is baked into the template.
    pad = 2
    y1p, y2p = max(0, y1 - pad), min(h, y2 + pad + 1)
    x1p, x2p = max(0, x1 - pad), min(w, x2 + pad + 1)

    IM_crop = IM.copy()
    IM_crop[0, 2] -= x1p
    IM_crop[1, 2] -= y1p
    crop_w, crop_h = x2p - x1p, y2p - y1p

    soft_alpha = _get_soft_alpha(face_h)
    bgr_fake_crop = cv2.warpAffine(bgr_fake, IM_crop, (crop_w, crop_h), borderMode=cv2.BORDER_REPLICATE)
    alpha_crop = cv2.warpAffine(soft_alpha, IM_crop, (crop_w, crop_h), borderValue=0)

    target_crop = target_img[y1p:y2p, x1p:x2p]

    if _HAS_TORCH_CUDA:
        # Scale alpha to [0, 1] on device — cheaper to upload uint8 than float.
        mask_t = torch.from_numpy(alpha_crop).cuda().float().mul_(1.0 / 255.0).unsqueeze(2)
        fake_t = torch.from_numpy(bgr_fake_crop).float().cuda()
        tgt_t = torch.from_numpy(target_crop).float().cuda()
        blended = (mask_t * fake_t + (1.0 - mask_t) * tgt_t).to(torch.uint8).cpu().numpy()
        target_img[y1p:y2p, x1p:x2p] = blended
    else:
        # Fused uint8 blend via cv2 SIMD — no float32 round-trip.
        # Measured ~7-8× faster than the old numpy float32 path on a 1000×1000 crop.
        alpha_3c = cv2.merge([alpha_crop, alpha_crop, alpha_crop])
        inv_alpha = 255 - alpha_3c
        a_fake = cv2.multiply(bgr_fake_crop, alpha_3c, scale=1.0 / 255.0)
        a_tgt = cv2.multiply(target_crop, inv_alpha, scale=1.0 / 255.0)
        target_img[y1p:y2p, x1p:x2p] = cv2.add(a_fake, a_tgt)

    return target_img

def apply_color_transfer(source, target):
    """
    Apply color transfer using LAB color space. Handles potential division by zero and ensures output is uint8.
    """
    # Input validation
    if source is None or target is None or source.size == 0 or target.size == 0:
        # print("Warning: Invalid input to apply_color_transfer.")
        return source # Return original source if invalid input

    # Ensure images are 3-channel BGR uint8
    if len(source.shape) != 3 or source.shape[2] != 3 or source.dtype != np.uint8:
        # print("Warning: Source image for color transfer is not uint8 BGR.")
        # Attempt conversion if possible, otherwise return original
        try:
            if len(source.shape) == 2: # Grayscale
                source = cv2.cvtColor(source, cv2.COLOR_GRAY2BGR)
            source = np.clip(source, 0, 255).astype(np.uint8)
            if len(source.shape) != 3 or source.shape[2] != 3:
                raise ValueError("Conversion failed")
        except Exception:
            return source
    if len(target.shape) != 3 or target.shape[2] != 3 or target.dtype != np.uint8:
        # print("Warning: Target image for color transfer is not uint8 BGR.")
        try:
            if len(target.shape) == 2: # Grayscale
                target = cv2.cvtColor(target, cv2.COLOR_GRAY2BGR)
            target = np.clip(target, 0, 255).astype(np.uint8)
            if len(target.shape) != 3 or target.shape[2] != 3:
                raise ValueError("Conversion failed")
        except Exception:
             return source # Return original source if target invalid

    result_bgr = source # Default to original source in case of errors

    try:
        # Convert to float32 [0, 1] range for LAB conversion
        source_float = source.astype(np.float32) / 255.0
        target_float = target.astype(np.float32) / 255.0

        source_lab = cv2.cvtColor(source_float, cv2.COLOR_BGR2LAB)
        target_lab = cv2.cvtColor(target_float, cv2.COLOR_BGR2LAB)

        # Compute statistics
        source_mean, source_std = cv2.meanStdDev(source_lab)
        target_mean, target_std = cv2.meanStdDev(target_lab)

        # Reshape for broadcasting
        source_mean = source_mean.reshape((1, 1, 3))
        source_std = source_std.reshape((1, 1, 3))
        target_mean = target_mean.reshape((1, 1, 3))
        target_std = target_std.reshape((1, 1, 3))

        # Avoid division by zero or very small std deviations (add epsilon)
        epsilon = 1e-6
        source_std = np.maximum(source_std, epsilon)
        # target_std = np.maximum(target_std, epsilon) # Target std can be small

        # Perform color transfer in LAB space
        result_lab = (source_lab - source_mean) * (target_std / source_std) + target_mean

        # --- No explicit clipping needed in LAB space typically ---
        # Clipping is handled implicitly by the conversion back to BGR and then to uint8

        # Convert back to BGR float [0, 1]
        result_bgr_float = cv2.cvtColor(result_lab, cv2.COLOR_LAB2BGR)

        # Clip final BGR values to [0, 1] range before scaling to [0, 255]
        result_bgr_float = np.clip(result_bgr_float, 0.0, 1.0)

        # Convert back to uint8 [0, 255]
        result_bgr = (result_bgr_float * 255.0).astype("uint8")

    except cv2.error as e:
         # print(f"OpenCV error during color transfer: {e}. Returning original source.") # Optional debug
         return source # Return original source if conversion fails
    except Exception as e:
         # print(f"Unexpected color transfer error: {e}. Returning original source.") # Optional debug
         # import traceback
         # traceback.print_exc()
         return source

    return result_bgr
def preprocess_face(face_img: np.ndarray, input_size: int) -> np.ndarray:
    """Resize, normalize, and convert a BGR face crop to ONNX input blob.

    GPEN-BFR expects [1, 3, H, W] float32 in RGB, normalized to [-1, 1].
    """
    resized = cv2.resize(face_img, (input_size, input_size), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0 * 2.0 - 1.0
    blob = np.transpose(blob, (2, 0, 1))[np.newaxis, ...]
    return blob

def postprocess_face(output: np.ndarray) -> np.ndarray:
    """Convert ONNX output [1, 3, H, W] float32 back to BGR uint8 image."""
    img = output[0].transpose(1, 2, 0)
    img = ((img + 1.0) / 2.0 * 255.0)
    img = np.clip(img, 0, 255).astype(np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img

def _get_face_affine(face: Any, input_size: int):
    """Compute affine transform to align a face to GPEN input space.

    Returns (M, inv_M) — forward and inverse affine matrices.
    """
    template = np.array([
        [0.31556875, 0.4615741],
        [0.68262291, 0.4615741],
        [0.50009375, 0.6405054],
        [0.34947187, 0.8246919],
        [0.65343645, 0.8246919],
    ], dtype=np.float32) * input_size

    landmarks = None
    if hasattr(face, "kps") and face.kps is not None:
        landmarks = face.kps.astype(np.float32)
    elif hasattr(face, "landmark_2d_106") and face.landmark_2d_106 is not None:
        lm106 = face.landmark_2d_106
        landmarks = np.array([
            lm106[38],  # left eye
            lm106[88],  # right eye
            lm106[86],  # nose tip
            lm106[52],  # left mouth
            lm106[61],  # right mouth
        ], dtype=np.float32)

    if landmarks is None or len(landmarks) < 5:
        return None, None

    M = cv2.estimateAffinePartial2D(landmarks, template, method=cv2.LMEDS)[0]
    if M is None:
        return None, None
    inv_M = cv2.invertAffineTransform(M)
    return M, inv_M

def enhance_face_onnx(
    frame: np.ndarray,
    face: Any,
    session: onnxruntime.InferenceSession,
    input_size: int,
) -> np.ndarray:
    """Enhance a single face in the frame using an ONNX face restoration model."""
    M, inv_M = _get_face_affine(face, input_size)
    if M is None:
        return frame

    face_crop = cv2.warpAffine(
        frame, M, (input_size, input_size),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )

    blob = preprocess_face(face_crop, input_size)
    with THREAD_SEMAPHORE:
        input_name = session.get_inputs()[0].name
        output = run_inference(session, input_name, blob)
    enhanced = postprocess_face(output)

    # Create mask for blending (feathered edges)
    mask = np.ones((input_size, input_size), dtype=np.float32)
    border = max(1, input_size // 16)
    mask[:border, :] = np.linspace(0, 1, border)[:, np.newaxis]
    mask[-border:, :] = np.linspace(1, 0, border)[:, np.newaxis]
    mask[:, :border] = np.minimum(mask[:, :border], np.linspace(0, 1, border)[np.newaxis, :])
    mask[:, -border:] = np.minimum(mask[:, -border:], np.linspace(1, 0, border)[np.newaxis, :])

    h, w = frame.shape[:2]
    warped_enhanced = cv2.warpAffine(
        enhanced, inv_M, (w, h),
        flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0),
    )
    warped_mask = cv2.warpAffine(
        mask, inv_M, (w, h),
        flags=cv2.INTER_LINEAR, borderValue=0,
    )

    mask_3ch = warped_mask[:, :, np.newaxis]
    result = (warped_enhanced.astype(np.float32) * mask_3ch +
              frame.astype(np.float32) * (1.0 - mask_3ch))
    return np.clip(result, 0, 255).astype(np.uint8)
