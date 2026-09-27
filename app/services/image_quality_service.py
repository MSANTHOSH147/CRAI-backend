from pathlib import Path
from typing import Union

from PIL import Image, ImageStat


# ============================================================
# CRAI IMAGE QUALITY SERVICE
# ============================================================
#
# Purpose:
#   Determine whether a field image is suitable for
#   visual AI inference.
#
# This service DOES NOT diagnose crop disease.
#
# Pipeline:
#
#   Image
#      ↓
#   Resolution
#      ↓
#   Brightness
#      ↓
#   Contrast
#      ↓
#   Sharpness
#      ↓
#   Quality decision
#
# Possible results:
#
#   GOOD
#   ACCEPT_WITH_CAUTION
#   RETAKE_REQUIRED
#
# ============================================================


# ============================================================
# QUALITY THRESHOLDS
# ============================================================

MIN_WIDTH = 160
MIN_HEIGHT = 160

MIN_BRIGHTNESS = 35.0
MAX_BRIGHTNESS = 225.0

MIN_CONTRAST = 20.0
MIN_SHARPNESS = 35.0


# ============================================================
# INTERNAL HELPERS
# ============================================================


def _variance_of_laplacian(
    image: Image.Image,
) -> float:
    """
    Lightweight sharpness estimate.

    Higher value generally indicates stronger
    local edge/detail information.

    This implementation intentionally uses only
    Pillow and does not require OpenCV.
    """

    gray = image.convert("L")

    width, height = gray.size

    if width < 3 or height < 3:
        return 0.0

    pixels = list(
        gray.getdata()
    )

    rows = [
        pixels[
            y * width:
            (y + 1) * width
        ]
        for y in range(height)
    ]

    values = []

    for y in range(
        1,
        height - 1,
    ):

        for x in range(
            1,
            width - 1,
        ):

            laplacian = (
                rows[y - 1][x]
                + rows[y + 1][x]
                + rows[y][x - 1]
                + rows[y][x + 1]
                - 4 * rows[y][x]
            )

            values.append(
                float(laplacian)
            )

    if not values:
        return 0.0

    mean = (
        sum(values)
        / len(values)
    )

    variance = (
        sum(
            (value - mean) ** 2
            for value in values
        )
        / len(values)
    )

    return float(
        variance
    )


def _load_image(
    image_or_path: Union[
        Image.Image,
        str,
        Path,
    ],
) -> Image.Image:
    """
    Load an image from either:

        PIL.Image.Image

    or:

        file path

    The returned image is detached from the
    source file so the caller can safely close
    the original file.
    """

    if isinstance(
        image_or_path,
        Image.Image,
    ):

        return image_or_path.convert(
            "RGB"
        )

    image_path = Path(
        image_or_path
    )

    if not image_path.exists():

        raise FileNotFoundError(
            f"Image file not found: {image_path}"
        )

    with Image.open(
        image_path
    ) as image:

        return image.convert(
            "RGB"
        ).copy()


# ============================================================
# MAIN IMAGE QUALITY EVALUATION
# ============================================================


def evaluate_image_quality(
    image_or_path: Union[
        Image.Image,
        str,
        Path,
    ],
) -> dict:
    """
    Evaluate whether an image is suitable for
    CRAI visual inference.

    This function does NOT diagnose disease.

    It evaluates:

        - resolution
        - brightness
        - contrast
        - sharpness

    Returns:

        GOOD
        ACCEPT_WITH_CAUTION
        RETAKE_REQUIRED
    """

    image = _load_image(
        image_or_path
    )

    # ========================================================
    # IMAGE DIMENSIONS
    # ========================================================

    width, height = image.size

    # ========================================================
    # GRAYSCALE STATISTICS
    # ========================================================

    gray = image.convert(
        "L"
    )

    statistics = ImageStat.Stat(
        gray
    )

    brightness = float(
        statistics.mean[0]
    )

    contrast = float(
        statistics.stddev[0]
    )

    # ========================================================
    # SHARPNESS
    # ========================================================

    sharpness = (
        _variance_of_laplacian(
            image
        )
    )

    # ========================================================
    # QUALITY CHECKS
    # ========================================================

    checks = {

        "resolution": (
            width >= MIN_WIDTH
            and
            height >= MIN_HEIGHT
        ),

        "brightness": (
            MIN_BRIGHTNESS
            <= brightness
            <= MAX_BRIGHTNESS
        ),

        "contrast": (
            contrast
            >= MIN_CONTRAST
        ),

        "sharpness": (
            sharpness
            >= MIN_SHARPNESS
        ),
    }

    # ========================================================
    # FAILED CHECKS
    # ========================================================

    failed_checks = [
        name
        for name, passed
        in checks.items()
        if not passed
    ]

    # ========================================================
    # QUALITY SCORE
    # ========================================================

    quality_score = (
        sum(checks.values())
        /
        len(checks)
        *
        100.0
    )

    # ========================================================
    # QUALITY STATUS
    # ========================================================

    if not failed_checks:

        status = "GOOD"

    elif quality_score >= 50.0:

        status = (
            "ACCEPT_WITH_CAUTION"
        )

    else:

        status = (
            "RETAKE_REQUIRED"
        )

    # ========================================================
    # HUMAN / AUTONOMOUS GUIDANCE
    # ========================================================

    messages = []

    # --------------------------------------------------------
    # Resolution
    # --------------------------------------------------------

    if not checks[
        "resolution"
    ]:

        messages.append(
            "Move closer to the leaf and "
            "capture a higher-resolution image."
        )

    # --------------------------------------------------------
    # Brightness
    # --------------------------------------------------------

    if not checks[
        "brightness"
    ]:

        if brightness < MIN_BRIGHTNESS:

            messages.append(
                "Increase lighting and avoid "
                "very dark images."
            )

        else:

            messages.append(
                "Avoid overexposed lighting "
                "and direct glare."
            )

    # --------------------------------------------------------
    # Contrast
    # --------------------------------------------------------

    if not checks[
        "contrast"
    ]:

        messages.append(
            "Capture the leaf against a "
            "clearer background."
        )

    # --------------------------------------------------------
    # Sharpness
    # --------------------------------------------------------

    if not checks[
        "sharpness"
    ]:

        messages.append(
            "Hold the phone steady and "
            "retake a sharper image."
        )

    # ========================================================
    # FALLBACK MESSAGE
    # ========================================================

    if not messages:

        messages.append(
            "Image quality is suitable "
            "for visual analysis."
        )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "status":
            status,

        "quality_score":
            round(
                quality_score,
                2,
            ),

        "width":
            width,

        "height":
            height,

        "brightness":
            round(
                brightness,
                2,
            ),

        "contrast":
            round(
                contrast,
                2,
            ),

        "sharpness":
            round(
                sharpness,
                2,
            ),

        "checks":
            checks,

        "failed_checks":
            failed_checks,

        "messages":
            messages,

    }


# ============================================================
# BACKWARD / ROUTE-FRIENDLY ALIAS
# ============================================================


def assess_image_quality(
    image_or_path: Union[
        Image.Image,
        str,
        Path,
    ],
) -> dict:
    """
    Public route-friendly wrapper.

    Allows the API layer to call:

        assess_image_quality(image_path)

    while keeping the core implementation in:

        evaluate_image_quality()
    """

    return evaluate_image_quality(
        image_or_path
    )