"""This module defines an ASE interface to DftbPlus

http://http://www.dftb-plus.info//
http://www.dftb.org/

markus.kaukonen@iki.fi

The file 'geom.out.gen' contains the input and output geometry 
and it will be updated during the dftb calculations.

If restart == None 
                   it is assumed that a new input file 'dftb_hsd.in'
                   will be written by ase using default keywords
                   and the ones given by the user.

If restart != None 
                   it is assumed that keywords are in file restart

The keywords are given, for instance, as follows::

    Hamiltonian_SCC ='YES',
    Hamiltonian_SCCTolerance = 1.0E-008,
    Hamiltonian_MaxAngularMomentum = '',
    Hamiltonian_MaxAngularMomentum_O = '"p"',
    Hamiltonian_MaxAngularMomentum_H = '"s"',
    Hamiltonian_InitialCharges_ = '',
    Hamiltonian_InitialCharges_AllAtomCharges_ = '',
    Hamiltonian_InitialCharges_AllAtomCharges_1 = -0.88081627,
    Hamiltonian_InitialCharges_AllAtomCharges_2 = 0.44040813,
    Hamiltonian_InitialCharges_AllAtomCharges_3 = 0.44040813,

"""

import os

import numpy as np

from ase.io.dftb import write_dftb, read_dftb
from ase.data import atomic_numbers
from ase.calculators.calculator import FileIOCalculator, Parameters, kpts2mp, \
    kptdensity2monkhorstpack, ReadError

class Dftb(FileIOCalculator):
    if os.environ.has_key('DFTB_COMMAND'):
        command = os.environ['DFTB_COMMAND'] + ' > PREFIX.out'
    else:
        command = 'dftb+ > PREFIX.out'

    implemented_properties = ['energy', 'forces']
    
    """

        """

    def __init__(self, restart=None, ignore_bad_restart_file=False,
                 label='dftb', atoms=None, kpts= None,
                 **kwargs):
        """Construct a DFTB+ calculator.
 
        """
        from ase.io import write, read
        from ase.dft.kpoints import monkhorst_pack

        if os.environ.has_key('DFTB_PREFIX'):
            slako_dir = os.environ['DFTB_PREFIX']
        else:
            slako_dir = './'

        self.default_parameters = dict(
            Hamiltonian_='DFTB',
            Driver_='ConjugateGradient',
            Driver_MaxForceComponent = '1E-4',
            Driver_MaxSteps = 0,
            Hamiltonian_SlaterKosterFiles_ = 'Type2FileNames',
            Hamiltonian_SlaterKosterFiles_Prefix = slako_dir,
            Hamiltonian_SlaterKosterFiles_Separator = '"-"',
            Hamiltonian_SlaterKosterFiles_Suffix = '".skf"'
            )  

        FileIOCalculator.__init__(self, restart, ignore_bad_restart_file,
                                  label, atoms, **kwargs)

        self.kpts = kpts
        # kpoint stuff by ase
        if self.kpts != None:
            mpgrid = kpts2mp(atoms, self.kpts)
            mp = monkhorst_pack(mpgrid)
            initkey='Hamiltonian_KPointsAndWeights'
            self.parameters[initkey+'_']=''
            for i, imp in enumerate(mp):
                key = initkey+'_empty'+str(i)
                self.parameters[key]=str(mp[i]).strip('[]')+' 1.0'

        #the input file written only once
        if restart==None:
            self.write_dftb_in()
        else:
            if os.path.exists(restart):
                os.system('cp '+restart+' dftb_in.hsd') 
            if not os.path.exists('dftb_in.hsd'):
                raise IOError('No file "dftb_in.hsd", use restart=None')

        #indexes for the result file
        self.first_time = True
        self.index_energy = None
        self.index_force_begin = None
        self.index_force_end = None

    def write_dftb_in(self):
        #if the atoms have been generated they will be written in 
        #file 'geom.out.gen' for dftb+
        
        outfile = open('dftb_in.hsd','w')
        #geometry is taken always from the file 'geo_end.gen'
        outfile.write('Geometry = GenFormat { \n')
        outfile.write('    <<< "geo_end.gen" \n')
        outfile.write('} \n')
        outfile.write(' \n')

        #--------MAIN KEYWORDS-------
        sorted_parameters = sorted(self.parameters.items())
        previous_key = 'dummy_'
        myspace = ' '
        for key, value in sorted(self.parameters.items()):
            current_depth = key.rstrip('_').count('_')
            previous_depth = previous_key.rstrip('_').count('_')
            #outfile.write(str(current_depth)+str(previous_depth))
            for my_backsclash in reversed(range(previous_depth-current_depth)):
                outfile.write(3*(1+my_backsclash)*myspace + '} \n')
            outfile.write(3*current_depth*myspace)
            if key.endswith('_'):
                outfile.write\
                    (key.rstrip('_').rsplit('_')[-1]+' = '+str(value) + '{ \n')
            elif key.count('_empty')==1:
                outfile.write(str(value) + ' \n')
            else:
                outfile.write(key.rsplit('_')[-1]+' = '+str(value) + ' \n')
            previous_key = key
        current_depth = key.rstrip('_').count('_')
        for my_backsclash in reversed(range(current_depth)):
                outfile.write(3*my_backsclash*myspace + '} \n')
        #output to 'results.tag' file (which has proper formatting)
        outfile.write('Options { \n')
        outfile.write('   WriteResultsTag = Yes  \n')
        outfile.write('} \n')
        outfile.close()
    
    def set(self, **kwargs):
        changed_parameters = FileIOCalculator.set(self, **kwargs)
        if changed_parameters:
            self.reset()
            self.write_dftb_in()
            

    def check_state(self, atoms):
        system_changes = FileIOCalculator.check_state(self, atoms)
        return system_changes

    def write_input(self, atoms, properties=None, system_changes=None):
        from ase.io import write
        FileIOCalculator.write_input(\
            self, atoms, properties, system_changes)
        write('geo_end.gen', atoms)

    def read_results(self):
        """ all results are read from results.tag file """
        file = open('results.tag', 'r')
        self.lines = file.readlines()
        file.close()
        if self.first_time:
            self.first_time = False
            # Energy line index
            for iline, line in enumerate(self.lines):
                estring = 'total_energy'
                if line.find(estring) >=0:
                    self.index_energy=iline+1
                    break
            # Force line indexes
            for iline, line in enumerate(self.lines):
                fstring = 'forces   '
                if line.find(fstring) >=0:
                    self.index_force_begin=iline+1
                    line1=line.replace(':',',')
                    self.index_force_end=iline+1+ \
                        int(line1.split(',')[-1])
                    break

        self.read_energy()
        # read geometry from file in case dftb+ has done steps
        # to move atoms, in that case forces are not read
        if int(self.parameters['Driver_MaxSteps']) > 0:
                self.atoms = read('geo_end.gen')
                self.results['forces'] = np.zeros([len(self.state), 3])
        else:
            self.read_forces()

    def read_energy(self):
        """Read Energy from dftb output file (results.tag)."""
        from ase.units import Hartree

        # Energy:
        energy = float(self.lines[self.index_energy].split()[0]) * Hartree
        self.results['energy'] = energy


    def read_forces(self):
        """Read Forces from dftb output file (results.tag)."""
        from ase.units import Hartree, Bohr

        gradients = []
        for j in range(self.index_force_begin, self.index_force_end):
            word = self.lines[j].split()
            gradients.append([float(word[k]) for k in range(0,3)])
                    
        self.results['forces'] = np.array(gradients) * Hartree / Bohr
        
