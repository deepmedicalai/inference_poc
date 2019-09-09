import io
import numpy as np
import math
from PIL import Image

import pydicom.uid
import pydicom.encaps
from pydicom.pixel_data_handlers.util import dtype_corrected_for_endianness
from pydicom.pixel_data_handlers.util import convert_color_space

import pydicom.pixel_data_handlers.numpy_handler as np_handler  # noqa
import pydicom.pixel_data_handlers.rle_handler as rle_handler  # noqa
import pydicom.pixel_data_handlers.pillow_handler as pillow_handler  # noqa
import pydicom.pixel_data_handlers.jpeg_ls_handler as jpegls_handler  # noqa
import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler  # noqa

PillowSupportedTransferSyntaxes = [
    pydicom.uid.JPEGBaseline,
    pydicom.uid.JPEGLossless,
    pydicom.uid.JPEGExtended,
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEG2000TransferSyntaxes = [
    pydicom.uid.JPEG2000Lossless,
]
PillowJPEGTransferSyntaxes = [
    pydicom.uid.JPEGBaseline,
    pydicom.uid.JPEGExtended,
]

def extract_frames(ds, step=1, range=0):
    # Find all possible handlers that support the transfer syntax
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    possible_handlers = [hh for hh in pydicom.config.pixel_data_handlers if hh.supports_transfer_syntax(transfer_syntax)]

    # No handlers support the transfer syntax
    if not possible_handlers:
        raise NotImplementedError("Unable to decode pixel data with a transfer syntax UID of '{0}' ({1}) as there are no pixel data handlers "
            "available that support it."
            .format(ds.file_meta.TransferSyntaxUID, ds.file_meta.TransferSyntaxUID.name)
        )

    # Handlers that both support the transfer syntax and have their dependencies met
    available_handlers = [hh for hh in possible_handlers if hh.is_available()]

    # There are handlers that support the transfer syntax but none of them can be used as missing dependencies
    if not available_handlers:
        # For each of the possible handlers we want to find which dependencies are missing
        msg = ( "The following handlers are available to decode the pixel data however they are missing required dependencies: ")
        pkg_msg = []
        for hh in possible_handlers:
            hh_deps = hh.DEPENDENCIES
            # Missing packages
            missing = [dd for dd in hh_deps if have_package(dd) is None]
            # Package names
            names = [hh_deps[name][1] for name in missing]
            pkg_msg.append("{} (req. {})".format(hh.HANDLER_NAME, ', '.join(names)))

        raise RuntimeError(msg + ', '.join(pkg_msg))

    last_exception = None
    for handler in available_handlers:
        try:
            if handler == pillow_handler:
                arr = pillow_convert_pixeldata(ds, step, range)
            else:
                # Use the handler to get a 1D numpy array of the pixel data
                arr = handler.get_pixeldata(ds)

            _pixel_array = reshape_pixel_array(ds, arr, step=step, range=range)

            # Some handler/transfer syntax combinations may need to convert the color space from YCbCr to RGB
            if handler.needs_to_convert_to_RGB(ds):
                _pixel_array = convert_color_space(ds._pixel_array, 'YBR_FULL', 'RGB')

            return _pixel_array
        except Exception as exc:
            last_exception = exc

# only for multiframe files
def pillow_convert_pixeldata(dicom_dataset, step=1, range=0):
    transfer_syntax = dicom_dataset.file_meta.TransferSyntaxUID

    if dicom_dataset.PixelRepresentation == 0:
        format_str = 'uint{}'.format(dicom_dataset.BitsAllocated)
    elif dicom_dataset.PixelRepresentation == 1:
        format_str = 'int{}'.format(dicom_dataset.BitsAllocated)
    else:
        format_str = 'bad_pixel_representation'
    try:
        numpy_format = np.dtype(format_str)
    except TypeError:
        msg = ("Data type not understood by NumPy: format='{}', PixelRepresentation={}, BitsAllocated={}".format(format_str,dicom_dataset.PixelRepresentation,dicom_dataset.BitsAllocated))     
        raise TypeError(msg)

    numpy_format = dtype_corrected_for_endianness(dicom_dataset.is_little_endian, numpy_format)

    # decompress here
    if transfer_syntax in PillowJPEGTransferSyntaxes:
        if dicom_dataset.BitsAllocated > 8:
            raise NotImplementedError("JPEG Lossy only supported if Bits Allocated = 8")
        generic_jpeg_file_header = b''
        frame_start_from = 0
    elif transfer_syntax in PillowJPEG2000TransferSyntaxes:
        generic_jpeg_file_header = b''
        frame_start_from = 0
    else:
        generic_jpeg_file_header = b''
        frame_start_from = 0
    try:
        UncompressedPixelData = bytearray()
        CompressedPixelDataSeq = pydicom.encaps.decode_data_sequence(dicom_dataset.PixelData)
        for frame in CompressedPixelDataSeq[:range:step]:
            data = generic_jpeg_file_header + frame[frame_start_from:]
            fio = io.BytesIO(data)
            try:
                decompressed_image = Image.open(fio)
            except IOError as e:
                raise NotImplementedError(e.strerror)
            UncompressedPixelData.extend(decompressed_image.tobytes())        
    except Exception:
        raise

    pixel_array = np.frombuffer(UncompressedPixelData, numpy_format)
    
    if (transfer_syntax in PillowJPEG2000TransferSyntaxes and dicom_dataset.BitsStored == 16):
        # WHY IS THIS EVEN NECESSARY??
        pixel_array &= 0x7FFF
    return pixel_array

def reshape_pixel_array(ds, arr, step=1, range=0):
    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    nr_samples = ds.SamplesPerPixel

    # Valid values for Planar Configuration are dependent on transfer syntax
    if nr_samples > 1:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        if transfer_syntax in ['1.2.840.10008.1.2.4.50',
                               '1.2.840.10008.1.2.4.57',
                               '1.2.840.10008.1.2.4.70',
                               '1.2.840.10008.1.2.4.90',
                               '1.2.840.10008.1.2.4.91']:
            planar_configuration = 0
        elif transfer_syntax in ['1.2.840.10008.1.2.4.80',
                                 '1.2.840.10008.1.2.4.81',
                                 '1.2.840.10008.1.2.5']:
            planar_configuration = 1
        else:
            planar_configuration = ds.PlanarConfiguration

        if planar_configuration not in [0, 1]:
            raise ValueError(
                "Unable to reshape the pixel array as a value of {} for "
                "(0028,0006) 'Planar Configuration' is invalid."
                .format(planar_configuration)
            )

    if nr_frames > 1:
        if range != nr_frames:
            nr_frames = range  
        nr_frames = math.ceil(nr_frames / step)
        # Multi-frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(nr_frames, ds.Rows, ds.Columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(nr_frames, ds.Rows, ds.Columns, nr_samples)
            else:
                arr = arr.reshape(nr_frames, nr_samples, ds.Rows, ds.Columns)
                arr = arr.transpose(0, 2, 3, 1)

    return arr