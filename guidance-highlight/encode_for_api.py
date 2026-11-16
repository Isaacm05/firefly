import cv2


def encode_for_api(image, max_width=1280, quality=80):
    """Downscale + JPEG-compress a copy of image for sending to the API."""
    height, width = image.shape[:2]
    if width > max_width:
        scale = max_width / width
        image = cv2.resize(image, (max_width, int(height * scale)))

    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Could not encode image")
    return encoded.tobytes()
