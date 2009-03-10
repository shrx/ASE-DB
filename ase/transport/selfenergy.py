import numpy as np
from ase.transport.tools import dagger


class LeadSelfEnergy:
    conv = 1e-8 # Convergence criteria for surface Green function
    
    def __init__(self, hs_dii, hs_dij, hs_dim, eta=1e-4):
        self.h_ii, self.s_ii = hs_dii # onsite principal layer
        self.h_ij, self.s_ij = hs_dij # coupling between principal layers
        self.h_im, self.s_im = hs_dim # coupling to the central region
        self.nbf = self.h_im.shape[1] # nbf for the scattering region
        self.eta = eta
        self.energy = None
        self.bias = 0
        self.sigma_mm = np.empty((self.nbf, self.nbf), complex)

    def __call__(self, energy):
        """Return self-energy (sigma) evaluated at specified energy."""
        if energy != self.energy:
            self.energy = energy
            z = energy - self.bias + self.eta * 1.j           
            tau_im = z * self.s_im - self.h_im
            a_im = np.linalg.solve(self.get_sgfinv(energy), tau_im)
            tau_mi = z * dagger(self.s_im) - dagger(self.h_im)
            self.sigma_mm[:] = np.dot(tau_mi, a_im)

        return self.sigma_mm

    def set_bias(self, bias):
        self.bias = bias

    def get_lambda(self, energy):
        """Return the lambda (aka Gamma) defined by i(S-S^d).

        Here S is the retarded selfenergy, and d denotes the hermitian
        conjugate.
        """
        sigma_mm = self(energy)
        return 1.j * (sigma_mm - dagger(sigma_mm))
        
    def get_sgfinv(self, energy):
        """The inverse of the retarded surface Green function""" 
        z = energy - self.bias + self.eta * 1.0j
        
        v_00 = z * dagger(self.s_ii) - dagger(self.h_ii)
        v_11 = v_00.copy()
        v_10 = z * self.s_ij - self.h_ij
        v_01 = z * dagger(self.s_ij) - dagger(self.h_ij)

        delta = self.conv + 1
        n = 0
        while delta > self.conv:
            a = np.linalg.solve(v_11, v_01)
            b = np.linalg.solve(v_11, v_10)
            v_01_dot_b = np.dot(v_01, b)
            v_00 -= v_01_dot_b
            v_11 -= np.dot(v_10, a) 
            v_11 -= v_01_dot_b
            v_01 = -np.dot(v_01, a)
            v_10 = -np.dot(v_10, b)
        
            delta = abs(v_01).max()
            n += 1

        return v_00
