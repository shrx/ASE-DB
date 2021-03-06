from random import randint

import numpy as np

from ase import Atoms
from ase.constraints import dict2constraint
from ase.calculators.calculator import get_calculator, all_properties
from ase.calculators.singlepoint import SinglePointCalculator
from ase.data import chemical_symbols, atomic_masses
from ase.io.jsonio import decode
from ase.utils import hill


class FancyDict(dict):
    """Dictionary with keys available as attributes also."""
    def __getattr__(self, key):
        if key not in self:
            return dict.__getattribute__(self, key)
        value = self[key]
        if isinstance(value, dict):
            return FancyDict(value)
        return value

    def __dir__(self):
        return self.keys()  # for tab-completion
        

def atoms2dict(atoms):
    dct = {
        'numbers': atoms.numbers,
        'pbc': atoms.pbc,
        'cell': atoms.cell,
        'positions': atoms.positions,
        'unique_id': '%x' % randint(16**31, 16**32 - 1)}
    if atoms.has('magmoms'):
        dct['initial_magmoms'] = atoms.get_initial_magnetic_moments()
    if atoms.has('charges'):
        dct['initial_charges'] = atoms.get_initial_charges()
    if atoms.has('masses'):
        dct['masses'] = atoms.get_masses()
    if atoms.has('tags'):
        dct['tags'] = atoms.get_tags()
    if atoms.has('momenta'):
        dct['momenta'] = atoms.get_momenta()
    if atoms.constraints:
        dct['constraints'] = [c.todict() for c in atoms.constraints]
    if atoms.calc is not None:
        dct['calculator'] = atoms.calc.name.lower()
        dct['calculator_parameters'] = atoms.calc.todict()
        if len(atoms.calc.check_state(atoms)) == 0:
            for prop in all_properties:
                try:
                    x = atoms.calc.get_property(prop, atoms, False)
                except NotImplementedError:
                    pass
                else:
                    if x is not None:
                        dct[prop] = x
    return dct
    
    
class AtomsRow:
    def __init__(self, dct):
        if isinstance(dct, dict):
            dct = dct.copy()
        else:
            dct = atoms2dict(dct)
        self._constraints = dct.pop('constraints', [])
        self._data = dct.pop('data', None)
        kvp = dct.pop('key_value_pairs', {})
        self._keys = list(kvp.keys())
        self.__dict__.update(kvp)
        self.__dict__.update(dct)
        
    def __contains__(self, key):
        return key in self.__dict__
        
    def __iter__(self):
        return (key for key in self.__dict__ if key[0] != '_')
        
    def get(self, key, default=None):
        """Return value of key if present or default if not."""
        return getattr(self, key, default)
        
    @property
    def key_value_pairs(self):
        """Return dict of key-value pairs."""
        return dict((key, self.get(key)) for key in self._keys)
        
    def count_atoms(self):
        """Count atoms.
        
        Return dict mapping chemical symbol strings to number of atoms.
        """
        count = {}
        for symbol in self.symbols:
            count[symbol] = count.get(symbol, 0) + 1
        return count
        
    def __getitem__(self, key):
        return getattr(self, key)
        
    def __setitem__(self, key, value):
        setattr(self, key, value)
        
    @property
    def constraints(self):
        """List of constraints."""
        if not isinstance(self._constraints, list):
            # Lazy decoding:
            cs = decode(self._constraints)
            self._constraints = []
            for c in cs:
                # Convert to new format:
                name = c.pop('__name__', None)
                if name:
                    c = {'name': name, 'kwargs': c}
                if c['name'].startswith('ase'):
                    c['name'] = c['name'].rsplit('.', 1)[1]
                self._constraints.append(c)
        return [dict2constraint(d) for d in self._constraints]
        
    @property
    def data(self):
        """Data dict."""
        if self._data is None:
            raise AttributeError
        if not isinstance(self._data, dict):
            self._data = decode(self._data)  # lazy decoding
        return FancyDict(self._data)
        
    @property
    def natoms(self):
        """Number of atoms."""
        return len(self.numbers)
        
    @property
    def formula(self):
        """Chemical formula string."""
        return hill(self.numbers)
    
    @property
    def symbols(self):
        """List of chemical symbols."""
        return [chemical_symbols[Z] for Z in self.numbers]
        
    @property
    def fmax(self):
        """Maximum atomic force."""
        forces = self.constrained_forces
        return (forces**2).sum(1).max()**0.5
        
    @property
    def constrained_forces(self):
        """Forces after applying constraints."""
        forces = self.forces
        constraints = self.constraints
        if constraints:
            forces = forces.copy()
            for constraint in constraints:
                constraint.adjust_forces(self.positions, forces)
            
        return forces

    @property
    def smax(self):
        """Maximum stress tensor component."""
        return (self.stress**2).max()**0.5

    @property
    def mass(self):
        """Total mass."""
        if 'masses' in self:
            return self.masses.sum()
        return atomic_masses[self.numbers].sum()

    @property
    def volume(self):
        """Volume of unit cell."""
        return abs(np.linalg.det(self.cell))

    @property
    def charge(self):
        """Total charge."""
        charges = self.get('inital_charges')
        if charges is None:
            return 0.0
        return charges.sum()

    def toatoms(self, attach_calculator=False,
                add_additional_information=False):
        """Create Atoms object."""
        atoms = Atoms(self.numbers,
                      self.positions,
                      cell=self.cell,
                      pbc=self.pbc,
                      magmoms=self.get('initial_magmoms'),
                      charges=self.get('initial_charges'),
                      tags=self.get('tags'),
                      masses=self.get('masses'),
                      momenta=self.get('momenta'),
                      constraint=self.constraints)
    
        if attach_calculator:
            params = decode(self.get('calculator_parameters', '{}'))
            atoms.calc = get_calculator(self.calculator)(**params)
        else:
            results = {}
            for prop in all_properties:
                if prop in self:
                    results[prop] = self[prop]
            if results:
                atoms.calc = SinglePointCalculator(atoms, **results)
                atoms.calc.name = self.calculator

        if add_additional_information:
            atoms.info = {}
            atoms.info['unique_id'] = self.unique_id
            if self._keys:
                atoms.info['key_value_pairs'] = self.key_value_pairs
            data = self.get('data')
            if data:
                atoms.info['data'] = data
                    
        return atoms
