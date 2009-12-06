#!/usr/bin/env python
'''
interface to symmol


unzip symmol.tar.tz
compile symmol if necessary:
g77 -o symmol symmol.f

make sure symmol is on your executable path
'''

import math,os,re,string

from Scientific.Geometry import Vector
from Scientific.IO.FortranFormat import *

class SYMMOL:
    def __init__(self,atoms,outfile=None):
        
        unitcell = atoms.get_cell()
        A = Vector(unitcell[0])
        B = Vector(unitcell[1])
        C = Vector(unitcell[2])

        # lengths of the vectors
        a = A.length()#*angstroms2bohr
        b = B.length()#*angstroms2bohr
        c = C.length()#*angstroms2bohr

        # angles between the vectors
        rad2deg = 360./(2.*math.pi)
        alpha = B.angle(C)*rad2deg
        beta = A.angle(C)*rad2deg
        gamma = A.angle(B)*rad2deg

        scaledpositions = atoms.get_scaled_positions()
        chemicalsymbols = [atom.get_symbol() for atom in atoms]

        input = ''
        input += '%1.3f %1.3f %1.3f %1.3f %1.3f %1.3f\n' % (a,b,c,
                                                            alpha,beta,gamma)
        input += '1 1 0.1 0.1\n' 

        for atom in atoms:
            sym = atom.get_symbol()
            group = 1
            x,y,z = atom.get_position()
            #format(a6,i2,6f9.5)
            input += str(FortranLine((sym,
                                      group,
                                      x,y,z),
                                     FortranFormat('a6,i2,3f9.5')))+'\n'
                    
        pin,pout = os.popen2('symmol')
        pin.writelines(input)
        pin.close()
        self.output = pout.readlines()
        pout.close()

        if outfile:
            f = open(outfile,'w')
            f.writelines(self.output)
            f.close()

        if os.path.exists('symmol.log'):
            os.remove('symmol.log')

    def __str__(self):
        return string.join(self.output)

    def get_point_group(self):
        regexp = re.compile('^ Schoenflies symbol')

        for line in self.output:
            if regexp.search(line):
                return line

    def get_moments_of_inertia(self):
        regexp = re.compile('^ PRINCIPAL INERTIA MOMENTS and DEGENERATION DEGREE')
        lines = open('symmol.out').readlines()
        for i,line in enumerate(lines):
            
            if regexp.search(line):
                data = lines[i+1]
                break
        [Ia, Ib, Ic, degen] =  data.split()
        return [float(Ia), float(Ib), float(Ic), int(degen)]


if __name__ == '__test__':

    from ase import *
    from ase.data import molecules
    
    mol = 'CO2'
    atoms = Atoms(mol,
                positions = molecules.data[mol]['positions'])
    
    sg = SYMMOL(atoms)
    print sg.get_point_group()
    print sg.get_moments_of_inertia()
    print atoms.get_moments_of_inertia()

if __name__ == '__main__':
    from ase.calculators.jacapo import *
    from optparse import OptionParser

    parser = OptionParser(usage='symmol.py ncfile',
                      version='0.1')

    parser.add_option('-f',
                      nargs=0,
                      help = 'print full output')

    parser.add_option('-o',
                      nargs=1,
                      help = 'save output in filename')

    options,args = parser.parse_args()
    
    for ncfile in args:       

        sg = SYMMOL(Jacapo.read_atoms(ncfile),outfile=options.o)

        print sg.get_point_group()
        print sg.get_moments_of_inertia()
        if options.f is not None:
            print sg

 
