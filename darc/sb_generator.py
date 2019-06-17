#!/usr/bin/env python
#
# synthesized beam generator

import os
import socket
import yaml
import numpy as np

from darc.definitions import *


class SBGeneratorException(Exception):
    pass


class SBGenerator(object):

    def __init__(self, fname=None, science_case=None):
        self.sb_table = None
        self.nsub = None
        self.numtab = None
        self.numsb = None
        self.__reversed = None

        # Load config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)['sb_generator']

        # set config, expanding strings
        kwargs = {'home': os.path.expanduser('~'), 'hostname': socket.gethostname()}
        for key, value in config.items():
            if isinstance(value, str):
                value = value.format(**kwargs)
            setattr(self, key, value)

        # Get full path to SB table
        if fname:
            if not fname.startswith('/'):
                fname = os.path.join(self.table_folder, fname)
        elif science_case:
            if science_case == 3:
                fname = os.path.join(self.table_folder, self.table_sc3)
            else:
                fname = os.path.join(self.table_folder, self.table_sc4)
        self.science_case = science_case
        self.fname = fname

        # load the table
        self._load_table()

    @property
    def reversed(self):
        """
        Whether or not the SB table is reversed for use on filterbank data
        :return: reversed (bool)
        """
        return self.__reversed

    @reversed.setter
    def reversed(self, state):
        """
        Reverse the SB table for use on filterbank data
        :param state: bool, whether or not to reverse the table
        """
        if self.__reversed == state:
            # already in desired state
            return
        else:
            # reverse the table
            self.sb_table = self.sb_table[::-1]
            # store state
            self.__reversed = state

    @classmethod
    def from_table(cls, fname):
        """
        Initalize with provided SB table
        :param fname: Path to SB table
        :return: SBGenerator object
        """
        return cls(fname=fname)

    @classmethod
    def from_science_case(cls, science_case):
        """
        Initalize default table for given science cases
        :param science_case: science case (3 or 4)
        :return: SBGenerator object
        """
        if science_case not in (3, 4):
            raise SBGeneratorException('Invalid science case: {}'.format(science_case))
        return cls(science_case=science_case)

    def _load_table(self):
        """
        Load the SB table
        """
        self.sb_mapping = np.loadtxt(self.fname, dtype=int)
        numsb, self.nsub = self.sb_mapping.shape
        # do some extra checks if table is loaded based on science case
        # otherwise this is the users's responsibility
        if self.science_case:
            # check that the number of SBs is what we expect and TABs are not out of range
            if self.science_case == 3:
                expected_numtab = self.numtab['sc3']
                expected_numsb = self.numsb['sc3']
            else:
                expected_numtab = self.numtab['sc4']
                expected_numsb = self.numsb['sc4']
            # number of SBs and TABs

            # verify number of SBs
            if not expected_numsb == numsb:
                raise SBGeneratorException("Number of SBs ({}) not equal to expected value ({})".format(numsb,
                                                                                                        expected_numsb))
            # verify max TAB index, might be less than maximum if not all SBs are generated
            if not max(self.sb_mapping) < expected_numtab:
                raise SBGeneratorException("Maximum TAB ({}) higher than maximum for this science case ({})".format(
                                           max(self.sb_mapping), expected_numtab))
            self.numsb = numsb
            self.numtab = expected_numtab
        self.reversed = False

    def synthesize_beam(self, data, sb):
        """
        Synthesize beam
        :param data: TAB data with shape [TAB, freq, time]
        :param sb: SB index
        :return: SB data with shape [freq, time]
        """
        ntab, nfreq, ntime = data.shape
        # verify that SB index is ok
        if not sb < self.numsb:
            raise SBGeneratorException("SB index too high: {}; maximum is {}".format(sb, self.numsb - 1))
        if not sb >= 0:
            raise SBGeneratorException("SB index cannot be negative")
        # verify that number of TABs is ok
        if not ntab == self.numtab:
            raise SBGeneratorException("Number of TABs ({}) not equal to expected number of TABs ({})".format(
                                        ntab, self.numtab))
        # verify number of channels
        if not nfreq % self.nsub:
            raise SBGeneratorException("Error: Number of subbands ({}) is not a factor of "
                                       "number of channels ({})".format(self.nsub, nfreq))

        nchan_per_subband = nfreq / self.nsub
        beam = np.zeros((nfreq, self.nsub))
        for subband, tab in enumerate(self.sb_mapping[sb]):
            # get correct subband of correct tab and add it to raw SB
            # after vsplit, shape is (nsub, nfreq/nsub, ntime) -> simply [subband] gets correct subband
            # assign to subband of sb
            beam[subband*nchan_per_subband:(subband+1)*nchan_per_subband] = np.vsplit(data[tab], self.nsub)[subband]
        return beam
