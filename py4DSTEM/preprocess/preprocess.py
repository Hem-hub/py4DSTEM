# Preprocessing functions
#
# These functions generally accept DataCube objects as arguments, and return a new, modified
# DataCube.
# Most of these functions are also included as DataCube class methods.  Thus
#       datacube = preprocess_function(datacube, *args)
# will be identical to
#       datacube.preprocess_function(*args)

import warnings
import numpy as np
from py4DSTEM.preprocess.utils import bin2D, get_shifted_ar
from emdfile import tqdmnd
from scipy.ndimage import median_filter

### Editing datacube shape ###


def set_scan_shape(datacube, R_Nx, R_Ny):
    """
    Reshape the data given the real space scan shape.
    """
    try:
        # reshape
        datacube.data = datacube.data.reshape(
            datacube.R_N, datacube.Q_Nx, datacube.Q_Ny
        ).reshape(R_Nx, R_Ny, datacube.Q_Nx, datacube.Q_Ny)

        # set dim vectors
        Rpixsize = datacube.calibration.get_R_pixel_size()
        Rpixunits = datacube.calibration.get_R_pixel_units()
        datacube.set_dim(
            0,
            [0,Rpixsize],
            units = Rpixunits)
        datacube.set_dim(
            1,
            [0,Rpixsize],
            units = Rpixunits)

        # return
        return datacube

    except ValueError:
        print(
            "Can't reshape {} scan positions into a {}x{} array.".format(
                datacube.R_N, R_Nx, R_Ny
            )
        )
        return datacube
    except AttributeError:
        print(f"Can't reshape {datacube.data.__class__.__name__} datacube.")
        return datacube


def swap_RQ(datacube):
    """
    Swaps real and reciprocal space coordinates, so that if

        >>> datacube.data.shape
        (Rx,Ry,Qx,Qy)

    Then

        >>> swap_RQ(datacube).data.shape
        (Qx,Qy,Rx,Ry)
    """
    # swap
    datacube.data = np.transpose(datacube.data, axes=(2, 3, 0, 1))

    # set dim vectors
    Rpixsize = datacube.calibration.get_R_pixel_size()
    Rpixunits = datacube.calibration.get_R_pixel_units()
    Qpixsize = datacube.calibration.get_Q_pixel_size()
    Qpixunits = datacube.calibration.get_Q_pixel_units()
    datacube.set_dim(
        0,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Rx'
    )
    datacube.set_dim(
        1,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Ry'
    )
    datacube.set_dim(
        2,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qx'
    )
    datacube.set_dim(
        3,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qy'
    )

    # return
    return datacube


def swap_Rxy(datacube):
    """
    Swaps real space x and y coordinates, so that if

        >>> datacube.data.shape
        (Ry,Rx,Qx,Qy)

    Then

        >>> swap_Rxy(datacube).data.shape
        (Rx,Ry,Qx,Qy)
    """
    # swap
    datacube.data = np.moveaxis(datacube.data, 1, 0)

    # set dim vectors
    Rpixsize = datacube.calibration.get_R_pixel_size()
    Rpixunits = datacube.calibration.get_R_pixel_units()
    datacube.set_dim(
        0,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Rx'
    )
    datacube.set_dim(
        1,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Ry'
    )

    # return
    return datacube


def swap_Qxy(datacube):
    """
    Swaps reciprocal space x and y coordinates, so that if

        >>> datacube.data.shape
        (Rx,Ry,Qy,Qx)

    Then

        >>> swap_Qxy(datacube).data.shape
        (Rx,Ry,Qx,Qy)
    """
    datacube.data = np.moveaxis(datacube.data, 3, 2)
    return datacube


### Cropping and binning ###


def crop_data_diffraction(datacube, crop_Qx_min, crop_Qx_max, crop_Qy_min, crop_Qy_max):
    # crop
    datacube.data = datacube.data[
        :, :, crop_Qx_min:crop_Qx_max, crop_Qy_min:crop_Qy_max
    ]

    # set dim vectors
    Qpixsize = datacube.calibration.get_Q_pixel_size()
    Qpixunits = datacube.calibration.get_Q_pixel_units()
    datacube.set_dim(
        2,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qx'
    )
    datacube.set_dim(
        3,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qy'
    )

    # return
    return datacube


def crop_data_real(datacube, crop_Rx_min, crop_Rx_max, crop_Ry_min, crop_Ry_max):
    # crop
    datacube.data = datacube.data[
        crop_Rx_min:crop_Rx_max, crop_Ry_min:crop_Ry_max, :, :
    ]

    # set dim vectors
    Rpixsize = datacube.calibration.get_R_pixel_size()
    Rpixunits = datacube.calibration.get_R_pixel_units()
    datacube.set_dim(
        0,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Rx'
    )
    datacube.set_dim(
        1,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Ry'
    )

    # return
    return datacube


def bin_data_diffraction(datacube, bin_factor):
    """
    Performs diffraction space binning of data by bin_factor.
    """
    # validate inputs
    assert(type(bin_factor) is int
        ), f"Error: binning factor {bin_factor} is not an int."
    if bin_factor == 1:
        return datacube

    # get shape
    R_Nx, R_Ny, Q_Nx, Q_Ny = (
        datacube.R_Nx,
        datacube.R_Ny,
        datacube.Q_Nx,
        datacube.Q_Ny,
    )
    # crop edges if necessary
    if (Q_Nx % bin_factor == 0) and (Q_Ny % bin_factor == 0):
        pass
    elif Q_Nx % bin_factor == 0:
        datacube.data = datacube.data[:, :, :, : -(Q_Ny % bin_factor)]
    elif Q_Ny % bin_factor == 0:
        datacube.data = datacube.data[:, :, : -(Q_Nx % bin_factor), :]
    else:
        datacube.data = datacube.data[
            :, :, : -(Q_Nx % bin_factor), : -(Q_Ny % bin_factor)
        ]

    # bin
    datacube.data = datacube.data.reshape(
        R_Nx,
        R_Ny,
        int(Q_Nx / bin_factor),
        bin_factor,
        int(Q_Ny / bin_factor),
        bin_factor,
    ).sum(axis=(3, 5))


    # set dim vectors
    Qpixsize = datacube.calibration.get_Q_pixel_size() * bin_factor
    Qpixunits = datacube.calibration.get_Q_pixel_units()
    datacube.set_dim(
        2,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qx'
    )
    datacube.set_dim(
        3,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qy'
    )
    # set calibration pixel size
    datacube.calibration.set_Q_pixel_size(Qpixsize)

    # return
    return datacube


def bin_data_mmap(datacube, bin_factor, dtype=np.float32):
    """
    Performs diffraction space binning of data by bin_factor.

    """
    # validate inputs
    assert type(bin_factor) is int, f"Error: binning factor {bin_factor} is not an int."
    if bin_factor == 1:
        return datacube

    # get shape
    R_Nx, R_Ny, Q_Nx, Q_Ny = (
        datacube.R_Nx, datacube.R_Ny, datacube.Q_Nx, datacube.Q_Ny)
    # allocate space
    data = np.zeros(
        (
            datacube.R_Nx,
            datacube.R_Ny,
            datacube.Q_Nx // bin_factor,
            datacube.Q_Ny // bin_factor,
        ),
        dtype=dtype,
    )
    # bin
    for Rx, Ry in tqdmnd(datacube.R_Ny, datacube.R_Ny):
        data[Rx, Ry, :, :] = bin2D(datacube.data[Rx, Ry, :, :], bin_factor, dtype=dtype)
    datacube.data = data

    # set dim vectors
    Qpixsize = datacube.calibration.get_Q_pixel_size() * bin_factor
    Qpixunits = datacube.calibration.get_Q_pixel_units()
    datacube.set_dim(
        2,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qx'
    )
    datacube.set_dim(
        3,
        [0,Qpixsize],
        units = Qpixunits,
        name = 'Qy'
    )
    # set calibration pixel size
    datacube.calibration.set_Q_pixel_size(Qpixsize)

    # return
    return datacube


def bin_data_real(datacube, bin_factor):
    """
    Performs diffraction space binning of data by bin_factor.
    """
    # validate inputs
    assert(type(bin_factor) is int
        ), f"Bin factor {bin_factor} is not an int."
    if bin_factor <= 1:
        return datacube

    # set shape
    R_Nx, R_Ny, Q_Nx, Q_Ny = (
        datacube.R_Nx,
        datacube.R_Ny,
        datacube.Q_Nx,
        datacube.Q_Ny,
    )
    # crop edges if necessary
    if (R_Nx % bin_factor == 0) and (R_Ny % bin_factor == 0):
        pass
    elif R_Nx % bin_factor == 0:
        datacube.data = datacube.data[:, : -(R_Ny % bin_factor), :, :]
    elif R_Ny % bin_factor == 0:
        datacube.data = datacube.data[: -(R_Nx % bin_factor), :, :, :]
    else:
        datacube.data = datacube.data[
            : -(R_Nx % bin_factor), : -(R_Ny % bin_factor), :, :
        ]
    # bin
    datacube.data = datacube.data.reshape(
        int(R_Nx / bin_factor),
        bin_factor,
        int(R_Ny / bin_factor),
        bin_factor,
        Q_Nx,
        Q_Ny,
    ).sum(axis=(1, 3))

    # set dim vectors
    Rpixsize = datacube.calibration.get_R_pixel_size() * bin_factor
    Rpixunits = datacube.calibration.get_R_pixel_units()
    datacube.set_dim(
        0,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Rx'
    )
    datacube.set_dim(
        1,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Ry'
    )
    # set calibration pixel size
    datacube.calibration.set_R_pixel_size(Rpixsize)

    # return
    return datacube


def thin_data_real(datacube, thinning_factor):
    """
    Reduces data size by a factor of `thinning_factor`^2 by skipping every `thinning_factor` beam positions in both x and y.
    """
    # get shapes
    Rshape0 = datacube.Rshape
    Rshapef = tuple([x // thinning_factor for x in Rshape0])

    # allocate memory
    data = np.empty(
        (Rshapef[0], Rshapef[1], datacube.Qshape[0], datacube.Qshape[1]),
        dtype=datacube.data.dtype,
    )

    # populate data
    for rx, ry in tqdmnd(Rshapef[0], Rshapef[1]):

        rx0 = rx * thinning_factor
        ry0 = ry * thinning_factor
        data[rx, ry, :, :] = datacube[rx0, ry0, :, :]

    datacube.data = data

    # set dim vectors
    Rpixsize = datacube.calibration.get_R_pixel_size() * thinning_factor
    Rpixunits = datacube.calibration.get_R_pixel_units()
    datacube.set_dim(
        0,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Rx'
    )
    datacube.set_dim(
        1,
        [0,Rpixsize],
        units = Rpixunits,
        name = 'Ry'
    )
    # set calibration pixel size
    datacube.calibration.set_R_pixel_size(Rpixsize)

    # return
    return datacube


def filter_hot_pixels(datacube, thresh, ind_compare=1, return_mask=False):
    """
    This function performs pixel filtering to remove hot / bright pixels. We first compute a moving local ordering filter,
    applied to the mean diffraction image. This ordering filter will return a single value from the local sorted intensity
    values, given by ind_compare. ind_compare=0 would be the highest intensity, =1 would be the second hightest, etc.
    Next, a mask is generated for all pixels which are least a value thresh higher than the local ordering filter output.
    Finally, we loop through all diffraction images, and any pixels defined by mask are replaced by their 3x3 local median.

    Args:
        datacube (DataCube):      py4DSTEM Datacube
        thresh (float):           threshold for replacing hot pixels, if pixel value minus local ordering filter exceeds it.
        ind_compare (int):        which median filter value to compare against. 0 = brightest pixel, 1 = next brightest, etc.
        return_mask (bool): if True, returns the filter mask

    Returns:
        datacube                     datacube
        mask (bool):                 (optional) the bad pixel mask
    """

    # Mean image over all probe positions
    diff_mean = np.mean(datacube.data, axis=(0, 1))

    # Moving local ordered pixel values
    diff_local_med = np.sort(
        np.vstack(
            [
                np.roll(diff_mean, (-1, -1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (0, -1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (1, -1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-1, 0), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (0, 0), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (1, 0), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-1, 1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (0, 1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (1, 1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-1, -2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (0, -2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (1, -2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-1, 2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (0, 2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (1, 2), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-2, -1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-2, 0), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (-2, 1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (2, -1), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (2, 0), axis=(0, 1)).ravel(),
                np.roll(diff_mean, (2, 1), axis=(0, 1)).ravel(),
            ]
        ),
        axis=0,
    )
    # arry of the ind_compare'th pixel intensity
    diff_compare = np.reshape(diff_local_med[-ind_compare - 1, :], diff_mean.shape)

    # Generate mask
    mask = diff_mean - diff_compare > thresh

    # apply filtering
    for ax, ay in tqdmnd(
        *(datacube.R_Nx, datacube.R_Ny), desc="Cleaning pixels", unit=" images"
    ):
        # Calculate local 3x3 median images
        im_med = median_filter(datacube.data[ax, ay, :, :], size=3, mode="nearest")
        datacube.data[ax, ay, :, :][mask] = im_med[mask]

    if return_mask is True:
        return datacube, mask
    else:
        return datacube


def datacube_diffraction_shift(
    datacube,
    xshifts,
    yshifts,
    periodic=True,
    bilinear=False,
):
    """
    This function shifts each 2D diffraction image by the values defined by
    (xshifts,yshifts). The shift values can be scalars (same shift for all
    images) or arrays with the same dimensions as the probe positions in
    datacube.

    Args:
            datacube (DataCube):   py4DSTEM DataCube
            xshifts (float):       Array or scalar value for the x dim shifts
            yshifts (float):       Array or scalar value for the y dim shifts
            periodic (bool):       Flag for periodic boundary conditions. If set to false, boundaries are assumed to be periodic.
            bilinear (bool):       Flag for bilinear image shifts. If set to False, Fourier shifting is used.

        Returns:
            datacube (DataCube):   py4DSTEM DataCube
    """

    # if the shift values are constant, expand to arrays
    xshifts = np.array(xshifts)
    yshifts = np.array(yshifts)
    if xshifts.ndim == 0:
        xshifts = xshifts * np.ones((datacube.R_Nx, datacube.R_Ny))
    if yshifts.ndim == 0:
        yshifts = yshifts * np.ones((datacube.R_Nx, datacube.R_Ny))

    # Loop over all images
    for ax, ay in tqdmnd(
        *(datacube.R_Nx, datacube.R_Ny), desc="Shifting images", unit=" images"
    ):
        datacube.data[ax, ay, :, :] = get_shifted_ar(
            datacube.data[ax, ay, :, :],
            xshifts[ax, ay],
            yshifts[ax, ay],
            periodic=periodic,
            bilinear=bilinear,
        )

    return datacube


def resample_data_diffraction(
    datacube, resampling_factor=None, output_size=None, method="bilinear"
):
    """
    Performs diffraction space resampling of data by resampling_factor or to match output_size.
    """
    if method == "fourier":
        from py4DSTEM.process.utils import fourier_resample

        if np.size(resampling_factor) != 1:
            warnings.warn(
                (
                    "Fourier resampling currently only accepts a scalar resampling_factor. "
                    f"'resampling_factor' set to {resampling_factor[0]}."
                ),
                UserWarning,
            )
            resampling_factor = resampling_factor[0]

        datacube.data = fourier_resample(
            datacube.data, scale=resampling_factor, output_size=output_size
        )

    elif method == "bilinear":
        from scipy.ndimage import zoom

        if resampling_factor is not None:

            if output_size is not None:
                raise ValueError(
                    "Only one of 'resampling_factor' or 'output_size' can be specified."
                )

            resampling_factor = np.array(resampling_factor)
            if resampling_factor.shape == ():
                resampling_factor = np.tile(resampling_factor, 2)

        else:

            if output_size is None:
                raise ValueError(
                    "At-least one of 'resampling_factor' or 'output_size' must be specified."
                )

            if len(output_size) != 2:
                raise ValueError(
                    f"'output_size' must have length 2, not {len(output_size)}"
                )

            resampling_factor = np.array(output_size) / np.array(datacube.shape[-2:])

        resampling_factor = np.concatenate(((1, 1), resampling_factor))
        datacube.data = zoom(datacube.data, resampling_factor, order=1)
    else:
        raise ValueError(
            f"'method' needs to be one of 'bilinear' or 'fourier', not {method}."
        )

    return datacube


def pad_data_diffraction(datacube, pad_factor=None, output_size=None):
    """
    Performs diffraction space padding of data by pad_factor or to match output_size.
    """
    Qx, Qy = datacube.shape[-2:]

    if pad_factor is not None:

        if output_size is not None:
            raise ValueError(
                "Only one of 'pad_factor' or 'output_size' can be specified."
            )

        pad_factor = np.array(pad_factor)
        if pad_factor.shape == ():
            pad_factor = np.tile(pad_factor, 2)

        if np.any(pad_factor < 1):
            raise ValueError("'pad_factor' needs to be larger than 1.")

        pad_kx = np.round(Qx * (pad_factor[0] - 1) / 2).astype("int")
        pad_kx = (pad_kx, pad_kx)
        pad_ky = np.round(Qy * (pad_factor[1] - 1) / 2).astype("int")
        pad_ky = (pad_ky, pad_ky)

    else:

        if output_size is None:
            raise ValueError(
                "At-least one of 'pad_factor' or 'output_size' must be specified."
            )

        if len(output_size) != 2:
            raise ValueError(
                f"'output_size' must have length 2, not {len(output_size)}"
            )

        Sx, Sy = output_size

        if Sx < Qx or Sy < Qy:
            raise ValueError(f"'output_size' must be at-least as large as {(Qx,Qy)}.")

        pad_kx = Sx - Qx
        pad_kx = (pad_kx // 2, pad_kx // 2 + pad_kx % 2)

        pad_ky = Sy - Qy
        pad_ky = (pad_ky // 2, pad_ky // 2 + pad_ky % 2)

    pad_width = (
        (0, 0),
        (0, 0),
        pad_kx,
        pad_ky,
    )

    datacube.data = np.pad(datacube.data, pad_width=pad_width, mode="constant")

    return datacube










