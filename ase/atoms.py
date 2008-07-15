"""Definition of the Atoms class.

This module defines the central object in the ASE package: the Atoms
object.
"""

from math import cos, sin

import numpy as npy

from ase.atom import Atom
from ase.data import atomic_numbers, chemical_symbols, atomic_masses


class Atoms(object):
    """
    The Atoms object can represent an isolated molecule, or a
    periodically repeated structure.  It may have a unit cell and
    there may be periodic boundary conditions along any of the three
    unit cell axes.

    Information about the atoms (atomic numbers and position) is
    stored in ndarrays.  Optionally, there can be information about
    tags, momenta, masses, magnetic moments and charges.

    In order to calculate energies, forces and stresses, a calculator
    object has to attached to the atoms object.

        Parameters:

        symbols: str (formula) or list of str
            Can be a string formula, a list of symbols or a list of
            Atom objects.  Examples: 'H2O', 'COPt12', ['H', 'H', 'O'],
            [Atom('Ne', (x, y, z), ...].
        positions: list of xyz-positions
            Atomic positions.  Anything that can be converted to an
            ndarray of shape (n, 3) will do: [(x1,y1,z1), (x2,y2,z2),
            ...].
        scaled_positions: list of scaled-positions
            Like positions, but given in units of the unit cell.
            Can not be set at the same time as positions.
        numbers: list of int
            Atomic numbers (use only one of symbols/numbers).
        tags: list of int
            Special purpose tags.
        momenta: list of xyz-momenta
            Momenta for all atoms.
        masses: list of float
            Atomic masses in atomic units.
        magmoms: list of float
            Magnetic moments.
        charges: list of float
            Atomic charges.
        cell: 3x3 matrix
            Unit cell vectors.  Can also be given as just three
            numbers for orthorhombic cells.  Default value: [1, 1, 1].
        pbc: one or three bool
            Periodic boundary conditions flags.  Examples: True,
            False, 0, 1, (1, 1, 0), (True, False, False).  Default
            value: False.
        constraint: constraint object(s)
            Used for applying one or more constraints during structure
            optimization.
        calculator: calculator object
            Used to attach a calculator for calulating energies and atomic
            forces.

        Examples:

        These three are equivalent:

        >>> d = 1.104  # N2 bondlength
        >>> a = Atoms('N2', [(0, 0, 0), (0, 0, d)])
        >>> a = Atoms(numbers=[7, 7], positions=[(0, 0, 0), (0, 0, d)])
        >>> a = Atoms([Atom('N', (0, 0, 0)), Atom('N', (0, 0, d)])

        FCC gold:

        >>> a = 4.05  # Gold lattice constant
        >>> b = a / 2
        >>> fcc = Atoms('Au',
        ...             cell=[(0, b, b), (b, 0, b), (b, b, 0)],
        ...             pbc=True)

        Hydrogen wire:
        
        >>> d = 0.9  # H-H distance
        >>> L = 7.0
        >>> h = Atoms('H', positions=[(0, L / 2, L / 2)],
        ...           cell=(d, L, L),
        ...           pbc=(1, 0, 0))
        """

    __slots__ = ['arrays', 'cell', 'pbc', 'calc', 'constraints',
                 'addsorbate_info']

    def __init__(self, symbols=None,
                 positions=None, numbers=None,
                 tags=None, momenta=None, masses=None,
                 magmoms=None, charges=None,
                 scaled_positions=None,
                 cell=None, pbc=None,
                 constraint=None,
                 calculator=None):

        atoms = None

        if hasattr(symbols, 'GetUnitCell'):
            from ase.old import OldASEListOfAtomsWrapper
            atoms = OldASEListOfAtomsWrapper(symbols)
            symbols = None
        elif isinstance(symbols, Atoms):
            atoms = symbols
            symbols = None    
        elif (isinstance(symbols, (list, tuple)) and
              len(symbols) > 0 and isinstance(symbols[0], Atom)):
            # Get data from a list or tuple of Atom objects:
            data = zip(*[atom.get_data() for atom in symbols])
            atoms = Atoms(None, *data)
            symbols = None    
                
        if atoms is not None:
            # Get data from another Atoms object:
            if scaled_positions is not None:
                raise NotImplementedError
            if symbols is None and numbers is None:
                numbers = atoms.get_atomic_numbers()
            if positions is None:
                positions = atoms.get_positions()
            if tags is None and atoms.has('tags'):
                tags = atoms.get_tags()
            if momenta is None and atoms.has('momenta'):
                momenta = atoms.get_momenta()
            if magmoms is None and atoms.has('magmoms'):
                magmoms = atoms.get_initial_magnetic_moments()
            if masses is None and atoms.has('masses'):
                masses = atoms.get_masses()
            if charges is None and atoms.has('charges'):
                charges = atoms.get_charges()
            if cell is None:
                cell = atoms.get_cell()
            if pbc is None:
                pbc = atoms.get_pbc()
            if constraint is None:
                constraint = [c.copy() for c in atoms.constraints]

        self.arrays = {}
        
        if symbols is None:
            if numbers is None:
                if positions is None:
                    natoms = 0
                else:
                    natoms = len(positions)
                numbers = npy.zeros(natoms, int)
            self.new_array('numbers', numbers, int)
        else:
            if numbers is not None:
                raise ValueError(
                    'Use only one of "symbols" and "numbers".')
            else:
                self.new_array('numbers', symbols2numbers(symbols), int)

        if cell is None:
            cell = npy.eye(3)
        self.set_cell(cell)

        if positions is None:
            if scaled_positions is None:
                positions = npy.zeros((len(self.arrays['numbers']), 3))
            else:
                positions = npy.dot(scaled_positions, self.cell)
        else:
            if scaled_positions is not None:
                raise RuntimeError, 'Both scaled and cartesian positions set!'
        self.new_array('positions', positions, float)

        self.set_constraint(constraint)
        self.set_tags(default(tags, 0))
        self.set_momenta(default(momenta, (0.0, 0.0, 0.0)))
        self.set_masses(default(masses, None))
        self.set_magnetic_moments(default(magmoms, 0.0))
        self.set_charges(default(charges, 0.0))
        if pbc is None:
            pbc = False
        self.set_pbc(pbc)

        self.set_calculator(calculator)
        self.addsorbate_info = {}

    def set_calculator(self, calc=None):
        """Attach calculator object."""
        if hasattr(calc, '_SetListOfAtoms'):
            from ase.old import OldASECalculatorWrapper
            calc = OldASECalculatorWrapper(calc, self)
        self.calc = calc

    def get_calculator(self):
        """Get currently attached calculator object."""
        return self.calc

    def set_constraint(self, constraint=None):
        if constraint is None:
            self.constraints = []
        else:
            if isinstance(constraint, (list, tuple)):
                self.constraints = constraint
            else:
                self.constraints = [constraint]
    
    def set_cell(self, cell, scale_atoms=False, fix=None):
        """Set unit cell vectors.

        Parameters
        ----------
        cell : 
            Unit cell.  A 3x3 matrix (the three unit cell vectors) or
            just three numbers for an orthorhombic cell.
        scale_atoms : bool
            Fix atomic positions or move atoms with the unit cell?
            Default behavior is to *not* move the atoms (scale_atoms=False).

        Examples
        --------
        Two equivalent ways to define an orthorhombic cell:
        
        >>> a.set_cell([a, b, c])
        >>> a.set_cell([(a, 0, 0), (0, b, 0), (0, 0, c)])

        FCC unit cell:

        >>> a.set_cell([(0, b, b), (b, 0, b), (b, b, 0)])
        """

        if fix is not None:
            raise TypeError('Please use scale_atoms=%s' % (not fix))

        cell = npy.array(cell, float)
        if cell.shape == (3,):
            cell = npy.diag(cell)
        elif cell.shape != (3, 3):
            raise ValueError('Cell must be length 3 sequence or '
                             '3x3 matrix!')
        if scale_atoms:
            M = npy.linalg.solve(self.cell, cell)
            self.arrays['positions'][:] = npy.dot(self.arrays['positions'], M)
        self.cell = cell

    def get_cell(self):
        """Get the three unit cell vectors as a 3x3 ndarray."""
        return self.cell.copy()

    def set_pbc(self, pbc):
        """Set periodic boundary condition flags."""
        if isinstance(pbc, int):
            pbc = (pbc,) * 3
        self.pbc = npy.array(pbc, bool)
        
    def get_pbc(self):
        """Get periodic boundary condition flags."""
        return self.pbc.copy()

    def new_array(self, name, a, dtype=None):
        if dtype is not None:
            a = npy.array(a, dtype)
        else:
            a = a.copy()
            
        if name in self.arrays:
            raise RuntimeError

        for b in self.arrays.values():
            if len(a) != len(b):
                raise ValueError('Array has wrong length: %d != %d.' %
                                 (len(a), len(b)))
            break
        
        self.arrays[name] = a
    
    def set_array(self, name, a, dtype=None):
        b = self.arrays.get(name)
        if b is None:
            if a is not None:
                self.new_array(name, a, dtype)
        else:
            if a is None:
                del self.arrays[name]
            else:
                b[:] = a

    def has(self, name):
        """Check for existance of array.

        name must be one of: 'tags', 'momenta', 'masses', 'magmoms',
        'charges'."""
        return name in self.arrays
    
    def set_atomic_numbers(self, numbers):
        self.set_array('numbers', numbers, int)

    def get_atomic_numbers(self):
        return self.arrays['numbers']

    def set_chemical_symbols(self, symbols):
        self.set_array('numbers', symbols2numbers(symbols), int)

    def get_chemical_symbols(self):
        """Getlist of chemical symbols."""
        return [chemical_symbols[Z] for Z in self.arrays['numbers']]

    def set_tags(self, tags):
        self.set_array('tags', tags, int)
        
    def get_tags(self):
        if 'tags' in self.arrays:
            return self.arrays['tags'].copy()
        else:
            return npy.zeros(len(self), int)

    def set_momenta(self, momenta):
        if len(self.constraints) > 0 and momenta is not None:
            momenta = npy.array(momenta)  # modify a copy
            for constraint in self.constraints:
                constraint.adjust_forces(self.arrays['positions'], momenta)
        self.set_array('momenta', momenta, float)

    def get_momenta(self):
        if 'momenta' in self.arrays:
            return self.arrays['momenta'].copy()
        else:
            return npy.zeros((len(self), 3))
        
    def set_masses(self, masses='defaults'):
        """Set atomic masses.

        The array masses should contain the a list masses.  In case
        the masses argument is not given or for those elements of the
        masses list that are None, standard values are set."""
        
        if masses == 'defaults':
            masses = atomic_masses[self.arrays['numbers']]
        elif isinstance(masses, (list, tuple)):
            newmasses = []
            for m, Z in zip(masses, self.arrays['numbers']):
                if m is None:
                    newmasses.append(atomic_masses[Z])
                else:
                    newmasses.append(m)
            masses = newmasses
        self.set_array('masses', masses, float)

    def get_masses(self):
        if 'masses' in self.arrays:
            return self.arrays['masses'].copy()
        else:
            return atomic_masses[self.arrays['numbers']]
        
    def set_magnetic_moments(self, magmoms):
        """Sets the initial magnetic moments."""
        self.set_array('magmoms', magmoms, float)

    def get_initial_magnetic_moments(self):
        if 'magmoms' in self.arrays:
            return self.arrays['magmoms'].copy()
        else:
            return npy.zeros(len(self))

    def get_magnetic_moments(self):
        """Get calculated local magnetic moments."""
        if self.calc is None:
            raise RuntimeError('Atoms object has no calculator.')
        if self.calc.get_spin_polarized():
            return self.calc.get_magnetic_moments(self)
        else:
            return npy.zeros(len(self))
        
    def get_magnetic_moment(self):
        """Get calculated total magnetic moment."""
        if self.calc is None:
            raise RuntimeError('Atoms object has no calculator.')
        if self.calc.get_spin_polarized():
            return self.calc.get_magnetic_moment(self)
        else:
            return 0.0

    def set_charges(self, charges):
        self.set_array('charges', charges, int)

    def get_charges(self):
        if 'charges' in self.arrays:
            return self.arrays['charges'].copy()
        else:
            return npy.zeros(len(self))

    def set_positions(self, newpositions):
        positions = self.arrays['positions']
        if self.constraints:
            newpositions = npy.asarray(newpositions, float)
            for constraint in self.constraints:
                constraint.adjust_positions(positions, newpositions)
                
        positions[:] = newpositions

    def get_positions(self):
        return self.arrays['positions'].copy()

    def get_potential_energy(self):
        if self.calc is None:
            raise RuntimeError('Atoms object has no calculator.')
        return self.calc.get_potential_energy(self)

    def get_kinetic_energy(self):
        momenta = self.arrays.get('momenta')
        if momenta is None:
            return 0.0
        return 0.5 * npy.vdot(momenta, self.get_velocities())

    def get_velocities(self):
        momenta = self.arrays.get('momenta')
        if momenta is None:
            return None
        m = self.arrays.get('masses')
        if m is None:
            m = atomic_masses[self.arrays['numbers']]
        return momenta / m.reshape(-1, 1)
    
    def get_total_energy(self):
        return self.get_potential_energy() + self.get_kinetic_energy()

    def get_forces(self, apply_constraint=True):
        if self.calc is None:
            raise RuntimeError('Atoms object has no calculator.')
        forces = self.calc.get_forces(self)
        if apply_constraint:
            for constraint in self.constraints:
                constraint.adjust_forces(self.arrays['positions'], forces)
        return forces

    def get_stress(self):
        if self.calc is None:
            raise RuntimeError('Atoms object has no calculator.')
        return self.calc.get_stress(self)
    
    def copy(self):
        atoms = Atoms(cell=self.cell, pbc=self.pbc)

        atoms.arrays = {}
        for name, a in self.arrays.items():
            atoms.arrays[name] = a.copy()
            
        return atoms

    def __len__(self):
        return len(self.arrays['positions'])

    def __repr__(self):
        if len(self) < 20:
            symbols = ''.join(self.get_chemical_symbols())
        else:
            symbols = ''.join([chemical_symbols[Z] 
                               for Z in self.arrays['numbers'][:15]]) + '...'
        s = "Atoms(symbols='%s', " % symbols
        for name in self.arrays:
            if name == 'numbers':
                continue
            s += '%s=..., ' % name
        s += 'cell=%s, ' % self.cell.tolist()
        s += 'pbc=%s, ' % self.pbc.tolist()
        if len(self.constraints) == 1:
            s += 'constraint=%s, ' % repr(self.constraints[0])
        if len(self.constraints) > 1:
            s += 'constraint=%s, ' % repr(self.constraints)
        if self.calc is not None:
            s += 'calculator=%s(...), ' % self.calc.__class__.__name__
        return s[:-2] + ')'

    def __add__(self, other):
        atoms = self.copy()
        atoms += other
        return atoms

    def __iadd__(self, other):
        if isinstance(other, Atom):
            other = Atoms([other])
            
        n1 = len(self)
        n2 = len(other)
        
        for name, a1 in self.arrays.items():
            a = npy.zeros((n1 + n2,) + a1.shape[1:], a1.dtype)
            a[:n1] = a1
            a2 = other.arrays.get(name)
            if a2 is not None:
                a[n1:] = a2
            self.arrays[name] = a

        for name, a2 in other.arrays.items():
            if name in self.arrays:
                continue
            a = npy.zeros((n1 + n2,) + a2.shape[1:], a2.dtype)
            a[n1:] = a2
            self.set_array(name, a)

        return self

    extend = __iadd__

    def append(self, atom):
        self.extend(Atoms([atom]))

    def __getitem__(self, i):
        if isinstance(i, int):
            natoms = len(self)
            if i < -natoms or i >= natoms:
                raise IndexError('Index out of range.')

            return Atom(atoms=self, index=i)

        atoms = Atoms(cell=self.cell, pbc=self.pbc)

        atoms.arrays = {}
        for name, a in self.arrays.items():
            atoms.arrays[name] = a[i].copy()
            
        return atoms

    def __delitem__(self, i):
        mask = npy.ones(len(self), bool)
        mask[i] = False
        for name, a in self.arrays.items():
            self.arrays[name] = a[mask]

    def pop(self, i=-1):
        atom = self[i]
        atom.cut_reference_to_atoms()
        del self[i]
        return atom
    
    def __imul__(self, m):
        if isinstance(m, int):
            m = (m, m, m)
        M = npy.product(m)
        n = len(self)
        
        for name, a in self.arrays.items():
            self.arrays[name] = npy.tile(a, (M,) + (1,) * (len(a.shape) - 1))

        positions = self.arrays['positions']
        i0 = 0
        for m2 in range(m[2]):
            for m1 in range(m[1]):
                for m0 in range(m[0]):
                    i1 = i0 + n
                    positions[i0:i1] += npy.dot((m0, m1, m2), self.cell)
                    i0 = i1
        self.cell = npy.array([m[c] * self.cell[c] for c in range(3)])
        return self

    def __mul__(self, m):
        atoms = self.copy()
        atoms *= m
        return atoms

    repeat = __mul__
    
    def translate(self, displacement):
        """Translate atomic positions.

        The displacement argument can be a float an xyz vector or an
        nx3 array (where n is the number of atoms)."""

        self.arrays['positions'] += npy.array(displacement)

    def center(self, vacuum=None, axis=None):
        """Center atoms in unit cell"""
        p = self.arrays['positions']
        p0 = p.min(0)
        p1 = p.max(0)
        if axis is None:
            if vacuum is not None:
                self.cell = npy.diag(p1 - p0 + 2 * npy.asarray(vacuum))
            p += 0.5 * (self.cell.sum(0) - p0 - p1)
        else:
            c = self.cell.copy()
            c.flat[::4] = 0.0
            if c.any():
                raise NotImplementedError('Unit cell must be orthorhombic!')
            
            if vacuum is not None:
                self.cell[axis, axis] = p1[axis] - p0[axis] + 2 * vacuum
            p[:, axis] += 0.5 * (self.cell[axis, axis] - p0[axis] - p1[axis])

    def get_center_of_mass(self):
        m = self.arrays.get('masses')
        if m is None:
            m = atomic_masses[self.arrays['numbers']]
        return npy.dot(m, self.arrays['positions']) / m.sum()

    def rotate(self, v, a=None):
        """Rotate atoms.

        Rotate the angle a around the vector v.  If a is not given,
        the length of v is used as the angle.  If a is a vector, then
        v is rotated into a.  The point (0, 0, 0) is always fixed.
        Vectors can also be strings: 'x', '-x', 'y', ... .

        Examples
        --------
        Rotate 90 degrees around the z-axis, so that the x-axis is
        rotated into the y-axis:

        >>> a = pi / 2
        >>> atoms.rotate('z', a)
        >>> atoms.rotate((0, 0, 1), a)
        >>> atoms.rotate('-z', -a)
        >>> atoms.rotate((0, 0, a))
        >>> atoms.rotate('x', 'y')
        """

        norm = npy.linalg.norm
        v = string2vector(v)
        if a is None:
            a = norm(v)
        if isinstance(a, (float, int)):
            v /= norm(v)
            c = cos(a)
            s = sin(a)
        else:
            v2 = string2vector(a)
            v /= norm(v)
            v2 /= norm(v2)
            c = npy.dot(v, v2)
            v = npy.cross(v, v2)
            s = norm(v)
            v /= s
        p = self.arrays['positions']
        p[:] = (c * p - 
                npy.cross(p, s * v) + 
                npy.outer(npy.dot(p, v), (1.0 - c) * v))

    def rattle(self, stdev=0.001, seed=42):
        """Randomly displace atoms.

        This method adds random displacements to the atomic positions,
        taking a possible constraint into account.  The random numbers are
        drawn from a normal distribution of standard deviation stdev.

        For a parallel calculation, it is important to use the same
        seed on all processors!  """
        
        rs = npy.random.RandomState(seed)
        positions = self.arrays['positions']
        self.set_positions(positions +
                           rs.normal(scale=stdev, size=positions.shape))
        
    def get_distance(self, a0, a1, mic=False):
        """Return distance between two atoms.

        Use mic=True to use the Minimum Image Convention.
        """

        R = self.arrays['positions']
        D = R[a1] - R[a0]
        if mic:
            raise NotImplemented  # XXX
        return npy.linalg.norm(D)

    def set_distance(self, a0, a1, distance, fix=0.5):
        """Set the distance between two atoms.

        Set the distance between atoms *a0* and *a1* to *distance*.
        By default, the center of the two atoms will be fixed.  Use
        *fix=0* to fix the first atom, *fix=1* to fix the second
        atom and *fix=0.5* (default) to fix the center of the bond."""

        R = self.arrays['positions']
        D = R[a1] - R[a0]
        x = 1.0 - distance / npy.linalg.norm(D)
        R[a0] += (x * fix) * D
        R[a1] -= (x * (1.0 - fix)) * D

    def get_scaled_positions(self):
        """Get positions relative to unit cell.

        Atoms outside the unit cell will be wrapped into the cell in
        those directions with periodic boundary conditions so that the
        scaled coordinates are beween zero and one."""

        scaled = npy.linalg.solve(self.cell.T, self.arrays['positions'].T).T
        for i in range(3):
            if self.pbc[i]:
                scaled[:, i] %= 1.0
        return scaled

    def set_scaled_positions(self, scaled):
        """Set positions relative to unit cell."""
        self.arrays['positions'][:] = npy.dot(scaled, self.cell)

    def identical_to(self, other):
        """Check for identity of two atoms object.

        Identity means: same positions, atomic numbers, unit cell and
        periodic boundary conditions."""

        a = self.arrays
        b = other.arrays
        return (len(self) == len(other) and
                (a['positions'] == b['positions']).any() and
                (a['numbers'] == b['numbers']).any() and
                (self.cell == other.cell).any() and
                (self.pbc == other.pbc).any())

    def get_volume(self):
        return abs(npy.linalg.det(self.cell))
    
    def add_adsorbate(self, adsorbate, height, position=(0, 0), offset=None):
        """Add an adsorbate to a surface.
    
        This function adds an adsorbate to a slab.  If the slab is
        produced by one of the utility functions in ase.lattice.surface, it
        is possible to specify the position of the adsorbate by a keyword
        (the supported keywords depend on which function was used to
        create the atoms).
    
        If the adsorbate is a molecule, the first atom (number 0) is
        adsorbed to the surface, and it is the responsability of the user
        to orient the adsorbate in a sensible way.
    
        This function can be called multiple times to add more than one
        adsorbate.
    
        Parameters:
    
        atoms: The surface onto which the adsorbate should be added.
    
        adsorbate:  The adsorbate. Must be one of the following three types:
            A string containing the chemical symbol for a single atom.
            An atom object.
            An atoms object (for a molecular adsorbate).
    
        height: Height above the surface.
    
        position: The x-y position of the adsorbate, either as a tuple of
            two numbers or as a keyword (if the surface is produced by one
            of the functions in ase.lattice.surfaces).
    
        offset (default: None): Offsets the adsorbate by a number of unit
            cells. Mostly useful when adding more than one adsorbate.
    
        Note *position* is given in absolute xy coordinates (or as
        a keyword), whereas offset is specified in unit cells.  This
        can be used to give the positions in units of the unit cell by
        using *offset* instead.
        
        """
        info = self.addsorbate_info

        
        pos = npy.array([0.0, 0.0])  # (x, y) part
        spos = npy.array([0.0, 0.0]) # part relative to unit cell
        if offset is not None:
            spos += offset / info['size']

        if isinstance(position, str):
            # A site-name:
            if 'sites' not in info:
                raise TypeError('If the atoms are not made by an ' +
                                'ase.lattice.surface function, ' +
                                'position cannot be a name.')
            if position not in info['sites']:
                raise TypeError('Adsorption site %s not supported.' % position)
            spos += info['sites'][position] / info['size']
        else:
            pos += position
    
        pos += npy.dot(spos, self.cell[:2, :2])
    
        # Convert the adsorbate to an Atoms object
        if isinstance(adsorbate, Atoms):
            ads = adsorbate
        elif isinstance(adsorbate, Atom):
            ads = Atoms([adsorbate])
        else:
            # Hope it is a useful string or something like that
            ads = Atoms(adsorbate)
    
        # Get the z-coordinate:
        try:
            a = info['top layer atom index']
        except KeyError:
            a = self.positions[:, 2].argmax()
            info['top layer atom index']= a
        z = self.positions[a, 2] + height

        # Move adsorbate into position
        ads.translate([pos[0], pos[1], z] - ads.positions[0])
    
        # Attach the adsorbate
        self.extend(ads)
    
    def add_vacuum(self, vacuum, axis=2):
        """Add vacuum layer to the atoms.
    
        vacuum: The thickness of the vacuum layer.
        """
        if axis != 2:
            raise NotImplementedError

        uc = self.cell
        normal = np.cross(uc[0], uc[1])
        costheta = np.dot(normal, uc[2]) / np.sqrt(np.dot(normal, normal) *
                                                   np.dot(uc[2], uc[2]))
        length = np.sqrt(np.dot(uc[2], uc[2]))
        newlength = length + vacuum / costheta
        uc[2] *= newlength / length
    
    def _get_positions(self):
        return self.arrays['positions']
    
    def _set_positions(self, pos):
        self.arrays['positions'][:] = pos
    
    positions = property(_get_positions, _set_positions,
                         doc='Attribute for direct ' +
                         'manipulation of the positions.')

    def _get_numbers(self):
        return self.arrays['numbers']
    
    numbers = property(_get_numbers, doc='Attribute for direct ' +
                       'manipulation of the atomic numbers.')

        
def string2symbols(s):
    """Convert string to list of chemical symbols."""
    n = len(s)

    if n == 0:
        return []
    
    c = s[0]
    
    if c.isdigit():
        i = 1
        while i < n and s[i].isdigit():
            i += 1
        return int(s[:i]) * string2symbols(s[i:])

    if c == '(':
        p = 0
        for i, c in enumerate(s):
            if c == '(':
                p += 1
            elif c == ')':
                p -= 1
                if p == 0:
                    break
        j = i + 1
        while j < n and s[j].isdigit():
            j += 1
        if j > i + 1:
            m = int(s[i + 1:j])
        else:
            m = 1
        return m * string2symbols(s[1:i]) + string2symbols(s[j:])

    if c.isupper():
        i = 1
        if 1 < n and s[1].islower():
            i += 1
        j = i
        while j < n and s[j].isdigit():
            j += 1
        if j > i:
            m = int(s[i:j])
        else:
            m = 1
        return m * [s[:i]] + string2symbols(s[j:])

def symbols2numbers(symbols):
    if isinstance(symbols, str):
        symbols = string2symbols(symbols)
    numbers = []
    for s in symbols:
        if isinstance(s, str):
            numbers.append(atomic_numbers[s])
        else:
            numbers.append(s)
    return numbers

def string2vector(v):
    if isinstance(v, str):
        if v[0] == '-':
            return -string2vector(v[1:])
        w = npy.zeros(3)
        w['xyz'.index(v)] = 1.0
        return w
    return npy.asarray(v, float)

def default(data, dflt):
    """Helper function for setting default values."""
    if data is None:
        return None
    elif isinstance(data, (list, tuple)):
        newdata = []
        allnone = True
        for x in data:
            if x is None:
                newdata.append(dflt)
            else:
                newdata.append(x)
                allnone = False
        if allnone:
            return None
        return newdata
    else:
        return data
                               
