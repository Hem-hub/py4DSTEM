# Base class for all py4DSTEM data
# which adds a pointer to 'calibration' metadata

import warnings

from emdfile import Node
from py4DSTEM.classes import Calibration


class Data:

    def __init__(self):
        assert(isinstance(self,Node)), "Data instances must alse inherit from Node"
        pass


    # calibration

    @property
    def calibration(self):
        try:
            return self.root.metadata['calibration']
        except KeyError:
            return None
        except AttributeError:
            return None

    @calibration.setter
    def calibration(self, x):
        assert( isinstance( x, Calibration) )
        if 'calibration' in self.root.metadata.keys():
            warnings.warn("A 'calibration' key already exists in root.metadata - overwriting...")
        x.name = 'calibration'
        self.root.metadata['calibration'] = x





