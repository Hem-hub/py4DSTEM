# Reader for py4DSTEM v0.12 files

import h5py
import numpy as np
from os.path import splitext, exists
from py4DSTEM.io.legacy.read_utils import is_py4DSTEM_file, get_py4DSTEM_topgroups, get_py4DSTEM_version, version_is_geq
from py4DSTEM.io.legacy.legacy12.read_utils_v0_12 import get_py4DSTEM_dataobject_info
from emdfile import (
    PointList,
    PointListArray
)
from py4DSTEM.classes import (
    DataCube,
    DiffractionSlice,
    RealSlice,
)
from emdfile import tqdmnd

def read_v0_12(fp, **kwargs):
    """
    File reader for files written by py4DSTEM v0.12.  Precise behavior is detemined by which
    arguments are passed -- see below.

    Accepts:
        filepath    str or Path     When passed a filepath only, this function checks if the path
                                    points to a valid py4DSTEM file, then prints its contents to screen.
        data_id     int/str/list    Specifies which data to load. Use integers to specify the
                                    data index, or strings to specify data names. A list or
                                    tuple returns a list of DataObjects. Returns the specified data.
        topgroup     str            Stricty, a py4DSTEM file is considered to be
                                    everything inside a toplevel subdirectory within the
                                    HDF5 file, so that if desired one can place many py4DSTEM
                                    files inside a single H5.  In this case, when loading
                                    data, the topgroup argument is passed to indicate which
                                    py4DSTEM file to load. If an H5 containing multiple
                                    py4DSTEM files is passed without a topgroup specified,
                                    the topgroup names are printed to screen.
        metadata    bool            If True, returns a dictionary with the file metadata.
        log         bool            If True, writes the processing log to a plaintext file
                                    called splitext(fp)[0]+'.log'.
        mem         str             Only used if a single DataCube is loaded. In this case, mem
                                    specifies how the data should be stored; must be "RAM"
                                    or "MEMMAP" or "DASK". See docstring for py4DSTEM.file.io.read. Default
                                    is "RAM".
        binfactor   int             Only used if a single DataCube is loaded. In this case,
                                    a binfactor of > 1 causes the data to be binned by this amount
                                    as it's loaded.
        dtype       dtype           Used when binning data, ignored otherwise. Defaults to whatever
                                    the type of the raw data is, to avoid enlarging data size. May be
                                    useful to avoid 'wraparound' errors.

    Returns:
        data,md                     The function always returns a length 2 tuple corresponding
                                    to data and md.  If no input arguments with return values (i.e.
                                    data, metadata), these will return None.  Otherwise, their return
                                    values are as described above. E.f. passing data=[0,1,2],metadata=True
                                    will return a length two tuple, the first element being a list of 3
                                    DataObject instances and the second a MetaData instance.
    """
    assert(exists(fp)), "Error: specified filepath does not exist"
    assert(is_py4DSTEM_file(fp)), "Error: {} isn't recognized as a py4DSTEM file.".format(fp)

    # For HDF5 files containing multiple valid EMD type 2 files, disambiguate desired data
    tgs = get_py4DSTEM_topgroups(fp)
    if 'topgroup' in kwargs.keys():
        tg = kwargs['topgroup']
        assert(tg in tgs), "Error: specified topgroup, {}, not found.".format(tg)
    else:
        if len(tgs)==1:
            tg = tgs[0]
        else:
            print("Multiple topgroups detected.  Please specify one by passing the 'topgroup' keyword argument.")
            print("")
            print("Topgroups found:")
            for tg in tgs:
                print(tg)
            return None,None

    version = get_py4DSTEM_version(fp, tg)
    assert(version_is_geq(version,(0,12,0))), "File must be v0.12+"
    _data_id = 'data_id' in kwargs.keys()  # Flag indicating if data was requested

    # If metadata is requested
    if 'metadata' in kwargs.keys():
        if kwargs['metadata']:
            raise NotImplementedError("Legacy metadata reader missing...")
            # return metadata_from_h5(fp, tg)

    # If data is requested
    elif 'data_id' in kwargs.keys():
        data_id = kwargs['data_id']
        assert(isinstance(data_id,(int,np.int_,str,list,tuple))), "Error: data must be specified with strings or integers only."
        if not isinstance(data_id,(int,np.int_,str)):
            assert(all([isinstance(d,(int,np.int_,str)) for d in data_id])), "Error: data must be specified with strings or integers only."

        # Parse optional arguments
        if 'mem' in kwargs.keys():
            mem = kwargs['mem']
            assert(mem in ('RAM','MEMMAP', 'DASK'))
        else:
            mem='RAM'
        if 'binfactor' in kwargs.keys():
            binfactor = kwargs['binfactor']
            assert(isinstance(binfactor,(int,np.int_)))
        else:
            binfactor=1
        if 'dtype' in kwargs.keys():
            bindtype = kwargs['dtype']
            assert(isinstance(bindtype,type))
        else:
            bindtype = None

        return get_data(fp,tg,data_id,mem,binfactor,bindtype)

    # If no data is requested
    else:
        print_py4DSTEM_file(fp,tg)
        return


###### Get data ######

def get_data(filepath,tg,data_id,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts a filepath to a valid py4DSTEM file and an int/str/list specifying data, and returns the data.
    """
    if isinstance(data_id,(int,np.int_)):
        return get_data_from_int(filepath,tg,data_id,mem=mem,binfactor=binfactor,bindtype=bindtype)
    elif isinstance(data_id,str):
        return get_data_from_str(filepath,tg,data_id,mem=mem,binfactor=binfactor,bindtype=bindtype)
    else:
        return get_data_from_list(filepath,tg,data_id)

def get_data_from_int(filepath,tg,data_id,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts a filepath to a valid py4DSTEM file and an integer specifying data, and returns the data.
    """
    assert(isinstance(data_id,(int,np.int_)))
    with h5py.File(filepath,'r') as f:
        grp_dc = f[tg+'/data/datacubes/']
        grp_cdc = f[tg+'/data/counted_datacubes/']
        grp_ds = f[tg+'/data/diffractionslices/']
        grp_rs = f[tg+'/data/realslices/']
        grp_pl = f[tg+'/data/pointlists/']
        grp_pla = f[tg+'/data/pointlistarrays/']
        grp_coords = f[tg+'/data/coordinates/']
        grps = [grp_dc,grp_cdc,grp_ds,grp_rs,grp_pl,grp_pla,grp_coords]

        Ns = np.cumsum([len(grp.keys()) for grp in grps])
        i = np.nonzero(data_id<Ns)[0][0]
        grp = grps[i]
        N = data_id-Ns[i]
        name = sorted(grp.keys())[N]

        group_name = grp.name+'/'+name

        if mem == "RAM":
            grp_data = f[group_name]
            data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)

    if mem == "MEMMAP":
        f = h5py.File(filepath,'r')
        grp_data = f[group_name]
        data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)
    # ADDING STUFF IN HERE,
    # I need to change datacube and counted datacube 
    elif mem == "DASK":
        f = h5py.File(filepath, 'r')
        grp_data = f[group_name]
        data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)

    return data

def get_data_from_str(filepath,tg,data_id,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts a filepath to a valid py4DSTEM file and a string specifying data, and returns the data.
    """
    assert(isinstance(data_id,str))
    with h5py.File(filepath,'r') as f:
        grp_dc = f[tg+'/data/datacubes/']
        grp_cdc = f[tg+'/data/counted_datacubes/']
        grp_ds = f[tg+'/data/diffractionslices/']
        grp_rs = f[tg+'/data/realslices/']
        grp_pl = f[tg+'/data/pointlists/']
        grp_pla = f[tg+'/data/pointlistarrays/']
        grp_coords = f[tg+'/data/coordinates/']
        grps = [grp_dc,grp_cdc,grp_ds,grp_rs,grp_pl,grp_pla,grp_coords]

        l_dc = list(grp_dc.keys())
        l_cdc = list(grp_cdc.keys())
        l_ds = list(grp_ds.keys())
        l_rs = list(grp_rs.keys())
        l_pl = list(grp_pl.keys())
        l_pla = list(grp_pla.keys())
        l_coords = list(grp_coords.keys())
        names = l_dc+l_cdc+l_ds+l_rs+l_pl+l_pla+l_coords

        inds = [i for i,name in enumerate(names) if name==data_id]
        assert(len(inds)!=0), "Error: no data named {} found.".format(data_id)
        assert(len(inds)<2), "Error: multiple data blocks named {} found.".format(data_id)
        ind = inds[0]

        Ns = np.cumsum([len(grp.keys()) for grp in grps])
        i_grp = np.nonzero(ind<Ns)[0][0]
        grp = grps[i_grp]
        group_name = grp.name+'/'+data_id

        if mem == "RAM":
            grp_data = f[group_name]
            data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)

    if mem == "MEMMAP":
        f = h5py.File(filepath,'r')
        grp_data = f[group_name]
        data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)
    elif mem == 'DASK':
        f = h5py.File(filepath,'r')
        grp_data = f[group_name]
        data = get_data_from_grp(grp_data,mem=mem,binfactor=binfactor,bindtype=bindtype)

    return data

def get_data_from_list(filepath,tg,data_id,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts a filepath to a valid py4DSTEM file and a list or tuple specifying data, and returns the data.
    """
    assert(isinstance(data_id,(list,tuple)))
    assert(all([isinstance(d,(int,np.int_,str)) for d in data_id]))
    data = []
    for el in data_id:
        if isinstance(el,(int,np.int_)):
            data.append(get_data_from_int(filepath,tg,data_id=el,mem=mem,binfactor=binfactor,bindtype=bindtype))
        elif isinstance(el,str):
            data.append(get_data_from_str(filepath,tg,data_id=el,mem=mem,binfactor=binfactor,bindtype=bindtype))
        else:
            raise Exception("Data must be specified with strings or integers only.")
    return data

def get_data_from_grp(g,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts an h5py Group corresponding to a single dataobject in an open, correctly formatted H5 file,
        and returns a py4DSTEM DataObject.
    """
    dtype = g.name.split('/')[-2]
    if dtype == 'datacubes':
        return get_datacube_from_grp(g,mem,binfactor,bindtype)
    elif dtype == 'counted_datacubes':
        raise NotImplementedError("CountedDataCube objects are not available in py4DSTEM v0.13")
        # return get_counted_datacube_from_grp(g)
    elif dtype == 'diffractionslices':
        return get_diffractionslice_from_grp(g)
    elif dtype == 'realslices':
        return get_realslice_from_grp(g)
    elif dtype == 'pointlists':
        return get_pointlist_from_grp(g)
    elif dtype == 'pointlistarrays':
        return get_pointlistarray_from_grp(g)
    elif dtype == 'coordinates':
        raise NotImplementedError("Conversion from legacy Coordinates object to v0.13 Calibration is not available...")
        # return get_coordinates_from_grp(g)
    else:
        raise Exception('Unrecognized data object type {}'.format(dtype))


# Print to screen

def print_py4DSTEM_file(filepath,tg):
    """ Accepts a filepath to a valid py4DSTEM file and prints to screen the file contents.
    """
    info = get_py4DSTEM_dataobject_info(filepath,tg)

    version = get_py4DSTEM_version(filepath, tg)
    print(f"py4DSTEM file version {version[0]}.{version[1]}.{version[2]}")

    print("{:10}{:18}{:24}{:54}".format('Index', 'Type', 'Shape', 'Name'))
    print("{:10}{:18}{:24}{:54}".format('-----', '----', '-----', '----'))
    for el in info:
        print("  {:8}{:18}{:24}{:54}".format(str(el['index']),str(el['type']),str(el['shape']),str(el['name'])))
    return


#####################################################
# READERS SCRAPED FROM DATASTRUCTURE FILES IN v0.12 #
#####################################################

def get_datacube_from_grp(g,mem='RAM',binfactor=1,bindtype=None):
    """ Accepts an h5py Group corresponding to a single datacube in an open, correctly formatted H5 file,
        and returns a DataCube.
    """
    # TODO: add binning
    assert binfactor == 1, "Bin on load is currently unsupported for EMD files."

    if (mem, binfactor) == ("RAM", 1):
        stack_pointer = g['data']
        data = np.array(g['data'])
    elif (mem, binfactor) == ("MEMMAP", 1):
        data = g['data']
        stack_pointer = None
    name = g.name.split('/')[-1]
    return DataCube(data=data,name=name)


def get_diffractionslice_from_grp(g):
    """ Accepts an h5py Group corresponding to a diffractionslice in an open, correctly formatted H5 file,
        and returns a DiffractionSlice.
    """
    data = np.array(g['data'])
    name = g.name.split('/')[-1]
    Q_Nx,Q_Ny = data.shape[:2]
    if len(data.shape)==2:
        return DiffractionSlice(data=data,name=name)
    else:
        lbls = g['dim3']
        if('S' in lbls.dtype.str): # Checks if dim3 is composed of fixed width C strings
            with lbls.astype('S64'):
                lbls = lbls[:]
            lbls = [lbl.decode('UTF-8') for lbl in lbls]
        return DiffractionSlice(data=data,name=name,slicelabels=lbls)


def get_realslice_from_grp(g):
    """ Accepts an h5py Group corresponding to a realslice in an open, correctly formatted H5 file,
        and returns a RealSlice.
    """
    data = np.array(g['data'])
    name = g.name.split('/')[-1]
    R_Nx,R_Ny = data.shape[:2]
    if len(data.shape)==2:
        return RealSlice(data=data,name=name)
    else:
        lbls = g['dim3']
        if('S' in lbls.dtype.str): # Checks if dim3 is composed of fixed width C strings
            with lbls.astype('S64'):
                lbls = lbls[:]
            lbls = [lbl.decode('UTF-8') for lbl in lbls]
        return RealSlice(data=data,name=name,slicelabels=lbls)

def get_pointlist_from_grp(g):
    """ Accepts an h5py Group corresponding to a pointlist in an open, correctly formatted H5 file,
        and returns a PointList.
    """
    name = g.name.split('/')[-1]
    coordinates = []
    coord_names = list(g.keys())
    length = len(g[coord_names[0]+'/data'])
    if length==0:
        for coord in coord_names:
            coordinates.append((coord,None))
    else:
        for coord in coord_names:
            dtype = type(g[coord+'/data'][0])
            coordinates.append((coord, dtype))
    data = np.zeros(length,dtype=coordinates)
    for coord in coord_names:
        data[coord] = np.array(g[coord+'/data'])
    return PointList(data=data,name=name)

def get_pointlistarray_from_grp(g):
    """ Accepts an h5py Group corresponding to a pointlistarray in an open, correctly formatted H5 file,
        and returns a PointListArray.
    """
    name = g.name.split('/')[-1]
    dset = g['data']
    shape = dset.shape
    coordinates = h5py.check_vlen_dtype(dset.dtype)
    pla = PointListArray(dtype=coordinates,shape=shape,name=name)
    for (i,j) in tqdmnd(shape[0],shape[1],desc="Reading PointListArray",unit="PointList"):
        try:
            pla.get_pointlist(i,j).data = dset[i,j]
        except ValueError:
            pass
    return pla
