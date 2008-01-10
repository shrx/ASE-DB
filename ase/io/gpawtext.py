import numpy as npy

from ase.atoms import Atom, Atoms
from ase.calculators import SinglePointCalculator


def read_gpaw_text(fileobj, index=-1):
    if isinstance(fileobj, str):
        fileobj = open(fileobj)

    lines = fileobj.readlines()
    i = lines.index('Unit Cell:\n')
    cell = [float(line.split()[2]) for line in lines[i + 3:i + 6]]
    images = []
    energies = []
    forces = []
    while True:
        try:
            i = lines.index('Positions:\n')
        except ValueError:
            break
        atoms = Atoms(cell=cell)
        for line in lines[i + 1:]:
            words = line.split()
            if len(words) != 5:
                break
            n, symbol, x, y, z = words
            symbol = symbol.split('.')[0]
            atoms.append(Atom(symbol, [float(x), float(y), float(z)]))
        try:
            i = lines.index('-------------------------\n')
        except ValueError:
            e = None
        else:
            line = lines[i + 9]
            assert line.startswith('Zero Kelvin:')
            e = float(line.split()[-1])
        try:
            i = lines.index('Forces in eV/Ang:\n')
        except ValueError:
            f = None
        else:
            f = []
            for i in range(i + 1, i + 1 + len(atoms)):
                x, y, z = lines[i].split()[-3:]
                f.append((float(x), float(y), float(z)))

        if len(images) > 0 and e is None:
            break

        if e is not None or f is not None:
            atoms.set_calculator(SinglePointCalculator(e, f, None, atoms))

        images.append(atoms)
        lines = lines[i:]
        
    return images[index]
