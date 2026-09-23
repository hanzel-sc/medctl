"""DICOM to PNG format conversion.

Converts DICOM pixel data to PNG images suitable for visual inspection.
Applies Rescale Slope/Intercept and Window Center/Width when available.

WARNING: Converted images are purely visual derivatives.  They do NOT
retain medical metadata and must NOT be used as replacements for the
original DICOM data.

SECURITY: Never overwrites source files.  Requires explicit output path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from medctl.core.exceptions import (
    ConversionError,
    FileNotFoundError_,
    OutputPathError,
    UnsupportedFormatError,
)
from medctl.core.models import ConversionResult
from medctl.dicom.reader import is_dicom_file, read_dicom_file_with_pixels

logger = logging.getLogger(__name__)

# Supported output formats
SUPPORTED_FORMATS = {"png"}


def convert_dicom_to_png(
    input_path: str | Path,
    output_path: str | Path,
    window_center: float | None = None,
    window_width: float | None = None,
) -> ConversionResult:
    """Convert a single DICOM file or directory to PNG.

    Parameters
    ----------
    input_path : str | Path
        Path to a single DICOM file or a directory of DICOM files.
    output_path : str | Path
        Output file path (for single file) or directory (for batch).
    window_center : float | None
        Optional override for DICOM Window Center.
    window_width : float | None
        Optional override for DICOM Window Width.

    Returns
    -------
    ConversionResult
        Structured result of the conversion.
    """
    inp = Path(input_path)
    out = Path(output_path)

    if not inp.exists():
        raise FileNotFoundError_(str(inp))

    if inp.is_file():
        return _convert_single(inp, out, window_center, window_width)
    elif inp.is_dir():
        return _convert_directory(inp, out, window_center, window_width)
    else:
        raise ConversionError(f"Input path is neither a file nor directory: {inp}")


def _convert_single(
    input_file: Path,
    output_file: Path,
    window_center: float | None,
    window_width: float | None,
) -> ConversionResult:
    """Convert a single DICOM file to PNG."""
    if not is_dicom_file(input_file):
        raise ConversionError(f"Input is not a valid DICOM file: {input_file}")

    # Safety: don't overwrite the source
    if output_file.resolve() == input_file.resolve():
        raise OutputPathError(str(output_file), "Output path must differ from input")

    ds = read_dicom_file_with_pixels(input_file)
    if ds is None:
        raise ConversionError(f"Cannot read DICOM file: {input_file}")

    if not hasattr(ds, "pixel_array"):
        try:
            _ = ds.pixel_array
        except Exception:
            raise ConversionError(
                f"DICOM file has no pixel data or pixel data cannot be decoded: {input_file}"
            )

    try:
        pixels = ds.pixel_array.astype(np.float64)
    except Exception as exc:
        raise ConversionError(f"Cannot decode pixel data: {input_file} ({exc})") from exc

    # Apply Rescale Slope / Intercept if present
    slope = getattr(ds, "RescaleSlope", None)
    intercept = getattr(ds, "RescaleIntercept", None)
    if slope is not None or intercept is not None:
        s = float(slope) if slope is not None else 1.0
        i = float(intercept) if intercept is not None else 0.0
        pixels = pixels * s + i

    # Apply windowing
    wc = window_center
    ww = window_width

    if wc is None:
        wc_val = getattr(ds, "WindowCenter", None)
        if wc_val is not None:
            wc = float(wc_val) if not hasattr(wc_val, "__iter__") else float(wc_val[0])
    if ww is None:
        ww_val = getattr(ds, "WindowWidth", None)
        if ww_val is not None:
            ww = float(ww_val) if not hasattr(ww_val, "__iter__") else float(ww_val[0])

    if wc is not None and ww is not None and ww > 0:
        lower = wc - ww / 2.0
        upper = wc + ww / 2.0
        pixels = np.clip(pixels, lower, upper)

    # Normalise to 0–255
    pmin, pmax = float(np.min(pixels)), float(np.max(pixels))
    if pmax > pmin:
        pixels = (pixels - pmin) / (pmax - pmin) * 255.0
    else:
        pixels = np.zeros_like(pixels)

    pixels = pixels.astype(np.uint8)

    # Handle multi-frame (take first frame)
    if pixels.ndim == 3 and pixels.shape[0] > 1 and pixels.shape[2] not in (3, 4):
        pixels = pixels[0]

    # Create image
    if pixels.ndim == 2:
        img = Image.fromarray(pixels, mode="L")
    elif pixels.ndim == 3 and pixels.shape[2] == 3:
        img = Image.fromarray(pixels, mode="RGB")
    else:
        # Flatten to 2D if needed
        if pixels.ndim == 3:
            pixels = pixels[:, :, 0] if pixels.shape[2] == 1 else pixels.mean(axis=2).astype(np.uint8)
        img = Image.fromarray(pixels, mode="L")

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_file), format="PNG")

    return ConversionResult(
        input_path=str(input_file),
        output_path=str(output_file),
        output_format="png",
        success=True,
        message="Conversion successful. Note: PNG output is a visual derivative and does not contain medical metadata.",
        files_converted=1,
    )


def _convert_directory(
    input_dir: Path,
    output_dir: Path,
    window_center: float | None,
    window_width: float | None,
) -> ConversionResult:
    """Convert all DICOM files in a directory to PNG."""
    # Safety check
    try:
        if output_dir.resolve() == input_dir.resolve():
            raise OutputPathError(str(output_dir), "Output must differ from input")
    except ValueError:
        pass

    dicom_files = sorted(f for f in input_dir.rglob("*") if f.is_file() and is_dicom_file(f))

    if not dicom_files:
        return ConversionResult(
            input_path=str(input_dir),
            output_path=str(output_dir),
            output_format="png",
            success=False,
            message="No DICOM files found in directory.",
            files_converted=0,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    converted = 0
    errors: list[str] = []

    for file_path in dicom_files:
        relative = file_path.relative_to(input_dir)
        out_file = output_dir / relative.with_suffix(".png")

        try:
            _convert_single(file_path, out_file, window_center, window_width)
            converted += 1
        except (ConversionError, Exception) as exc:
            errors.append(f"{file_path.name}: {exc}")
            logger.warning("Conversion failed for %s: %s", file_path.name, exc)

    message = f"Converted {converted}/{len(dicom_files)} files."
    if errors:
        message += f" {len(errors)} errors occurred."

    return ConversionResult(
        input_path=str(input_dir),
        output_path=str(output_dir),
        output_format="png",
        success=converted > 0,
        message=message,
        files_converted=converted,
    )
