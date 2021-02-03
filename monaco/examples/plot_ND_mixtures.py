"""
Sampling in dimension D
===============================

We discuss the performances of several Monte Carlo samplers on a toy example in dimension 5.

"""


######################
# Introduction
# -------------------
#
# First of all, some standard imports.


import numpy as np
import torch
from matplotlib import pyplot as plt

plt.rcParams.update({"figure.max_open_warning": 0})

use_cuda = torch.cuda.is_available()
dtype = torch.cuda.FloatTensor if use_cuda else torch.FloatTensor

################################
# Our sampling space:

from monaco.euclidean import EuclideanSpace

D = 5
space = EuclideanSpace(dimension=D, dtype=dtype)


#######################################
# Our toy target distribution:


from monaco.euclidean import GaussianMixture, UnitPotential

N, M = (10000 if use_cuda else 50), 5
Nlucky = 100 if use_cuda else 2
nruns = 5

test_case = "gaussians"

if test_case == "gaussians":
    # Let's generate a blend of peaky Gaussians, in the unit square:
    m = torch.rand(M, D).type(dtype)  # mean
    s = torch.rand(M).type(dtype)  # deviation
    w = torch.rand(M).type(dtype)  # weights

    m = 0.25 + 0.5 * m
    s = 0.005 + 0.1 * (s ** 6)
    w = w / w.sum()  # normalize weights

    distribution = GaussianMixture(space, m, s, w)


elif test_case == "sophia":
    m = torch.FloatTensor([0.5, 0.1, 0.2, 0.8, 0.9]).type(dtype)[:, None]
    s = torch.FloatTensor([0.15, 0.005, 0.002, 0.002, 0.005]).type(dtype)
    w = torch.FloatTensor([0.1, 2 / 12, 1 / 12, 1 / 12, 2 / 12]).type(dtype)
    w = w / w.sum()  # normalize weights

    distribution = GaussianMixture(space, m, s, w)

elif test_case == "ackley":

    def ackley_potential(x, stripes=15):
        f_1 = 20 * (-0.2 * (((x - 0.5) * stripes) ** 2).mean(-1).sqrt()).exp()
        f_2 = ((2 * np.pi * ((x - 0.5) * stripes)).cos().mean(-1)).exp()

        return -(f_1 + f_2 - np.exp(1) - 20) / stripes

    distribution = UnitPotential(space, ackley_potential)


#############################
# Display the target density, with a typical sample.

plt.figure(figsize=(8, 8))
space.scatter(distribution.sample(N), "red")
space.plot(distribution.potential, "red")
space.draw_frame()


#################################################
# Sampling
# ---------------------
#
# We start from a uniform sample in the unit hyper-cube:


start = torch.rand(N, D).type(dtype)


#######################################
# Our proposal will stay the same throughout the experiments:
# a combination of uniform samples on balls with radii that
# range from 1/1000 to  0.3.


from monaco.euclidean import BallProposal

proposal = BallProposal(space, scale=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3])


##########################################
# First of all, we illustrate a run of the standard
# Metropolis-Hastings algorithm, parallelized on the GPU:


info = {}

from monaco.samplers import ParallelMetropolisHastings, display_samples

pmh_sampler = ParallelMetropolisHastings(space, start, proposal, annealing=5).fit(
    distribution
)
info["PMH"] = display_samples(pmh_sampler, iterations=20, runs=nruns)


########################################
# Then, the standard Collective Monte Carlo method:


from monaco.samplers import CMC

cmc_sampler = CMC(space, start, proposal, annealing=5).fit(distribution)
info["CMC"] = display_samples(cmc_sampler, iterations=20, runs=nruns)


#############################
# Our first algorithm - CMC with adaptive selection of the kernel bandwidth:


from monaco.samplers import MOKA_CMC

proposal = BallProposal(space, scale=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3])
moka_sampler = MOKA_CMC(space, start, proposal, annealing=5).fit(distribution)
info["MOKA"] = display_samples(moka_sampler, iterations=20, runs=nruns)


#############################
# Our second algorithm - CMC with Richardson-Lucy deconvolution:


from monaco.samplers import KIDS_CMC

proposal = BallProposal(space, scale=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3])
kids_sampler = KIDS_CMC(space, start, proposal, annealing=5, iterations=30).fit(
    distribution
)
info["KIDS"] = display_samples(kids_sampler, iterations=20, runs=nruns)


#############################
# Combining bandwith estimation and deconvolution with the Moka-Kids-CMC sampler:


from monaco.samplers import MOKA_KIDS_CMC

proposal = BallProposal(space, scale=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3])

kids_sampler = MOKA_KIDS_CMC(space, start, proposal, annealing=5, iterations=30).fit(
    distribution
)
info["MOKA+KIDS"] = display_samples(kids_sampler, iterations=20, runs=nruns)


#############################
# Finally, the Non Parametric Adaptive Importance Sampler,
# an efficient non-Markovian method with an extensive
# memory usage:


from monaco.samplers import NPAIS

proposal = BallProposal(space, scale=[0.001, 0.003, 0.01, 0.03, 0.1, 0.3])


class Q_uniform(object):
    def __init__(self):
        None

    def sample(self, n):
        return torch.rand(n, D).type(dtype)

    def potential(self, x):
        return torch.zeros(len(x)).type_as(x)


q0 = Q_uniform()

npais_sampler = NPAIS(space, start, proposal, annealing=5, q0=q0, N=N).fit(distribution)
info["NPAIS"] = display_samples(npais_sampler, iterations=20, runs=nruns)


plt.show()
