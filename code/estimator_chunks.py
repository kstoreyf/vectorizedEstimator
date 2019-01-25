import numpy as np
import multiprocessing as mp
import time



def est(ddpg, drpg, rdpg, rrpg, pimax, rmax, cosmo, basisfunc, K, wp, *args):

    nd1 = len(ddpg.cat1)
    nr1 = len(rrpg.cat1)
    nd2 = len(ddpg.cat2)
    nr2 = len(rrpg.cat2)

    print 'Calculating dd vector'
    dds = project_pairs(ddpg, pimax, rmax, cosmo, basisfunc, K, wp, False, None, *args)
    print dds
    # is d1 r2 right? cross?
    print 'Calculating dr vector'
    drs = project_pairs(drpg, pimax, rmax, cosmo, basisfunc, K, wp, False, None, *args)
    print drs

    print 'Calculating rd vector'
    # should check if need to compute both aka if d1==d2 (drs and rds should be same bc using symmetric defs of dcm)
    rds = project_pairs(rdpg, pimax, rmax, cosmo, basisfunc, K, wp, False, None, *args)

    print 'Calculating rr vector'
    rrs, qqs = project_pairs(rrpg, pimax, rmax, cosmo, basisfunc, K, wp, True, None, *args)
    print rrs

    a = []
    for bb in range(len(basisfunc)):
        dd = dds[bb] * 1./(nd1*nd2)
        dr = drs[bb] * 1./(nd1*nr2)
        rd = rds[bb] * 1./(nd2*nr1)
        rr = rrs[bb] * 1./(nr1*nr2)
        qq = qqs[bb] * 1./(nr1*nr2)
        a.append(calc_amplitudes(dd, dr, rd, rr, qq))
    print 'Computed amplitudes'

    return a


def est_multi(ddpg, drpg, rdpg, rrpg, pimax, rmax, cosmo, basisfunc, K, wp, *args):

    nd1 = len(ddpg.cat1)
    nr1 = len(rrpg.cat1)
    nd2 = len(ddpg.cat2)
    nr2 = len(rrpg.cat2)

    print 'Calculating dd vector'

    pair_arrs = [[ddpg, False],
                 [drpg, False],
                 [rdpg, False],
                 [rrpg, True]]

    nproc = 1
    print mp.cpu_count(), nproc

    count_arrs = [[] for _ in range(len(basisfunc))]
    for pg, tensor in pair_arrs:

        start = time.time()
        outq = mp.Queue()
        #print len(pairs)
        subsize = int(np.ceil(float(len(pg.cat1))/float(nproc)))

        loc_arr = [(nn*subsize, min((nn+1)*subsize, len(pg.cat1))) for nn in range(nproc)]
        print loc_arr

        pargs = [[pg, locs, pimax, rmax, cosmo, basisfunc, K, wp, tensor]+[outq]+list(args) for locs in loc_arr]
        processes = [mp.Process(target=project_pairs, args=parg) for parg in pargs]
        print 'Starting'
        for p in processes:
            p.start()
        for p in processes:
            p.join()
        rez = [outq.get() for _ in processes]

        for bb in range(len(basisfunc)):
            counts_multi = np.zeros(K)
            if tensor:
                counts_tensor_multi = np.zeros((K,K))
            for rz in rez:
                if tensor:
                    counts_multi += rz[0][bb]
                    counts_tensor_multi += rz[1][bb]
                else:
                    counts_multi += rz[bb]
            count_arrs[bb].append(counts_multi)
            if tensor:
                count_arrs[bb].append(counts_tensor_multi)
        end = time.time()
        print 'TIME:', end-start

        print counts_multi


    a = []
    for bb in range(len(basisfunc)):
        dds, drs, rds, rrs, qqs = zip(*count_arrs)
        dd = dds[bb] * 1./(nd1*nd2)
        dr = drs[bb] * 1./(nd1*nr2)
        rd = rds[bb] * 1./(nd2*nr1)
        rr = rrs[bb] * 1./(nr1*nr2)
        qq = qqs[bb] * 1./(nr1*nr2)
        a.append(calc_amplitudes(dd, dr, rd, rr, qq))
    print 'Computed amplitudes'
    print a

    return a


def split(a, n):
    k, m = divmod(len(a), n)
    return list((a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in xrange(n)))


def calc_amplitudes(dd, dr, rd, rr, qq):
    print 'Calculating amplitudes'
    qqinv = np.matrix(qq).I
    numerator = dd - dr - rd + rr
    print dd
    print numerator
    a = np.matmul(qqinv, numerator)
    return a


def project_pairs(pg, locs, pimax, rmax, cosmo, basisfunc, K, wp, tensor, outq, *args):

    bnum = len(basisfunc)
    counts = [np.zeros(K) for _ in range(bnum)]
    counts_tensor = [np.zeros((K, K)) for _ in range(bnum)]
    outarr = np.empty((K, K))

    dcm1 = pg.cat1['dcm_mpc'].values
    dcm2 = pg.cat2['dcm_mpc'].values
    dcm1_transverse = pg.cat1['dcm_transverse_mpc'].values
    dcm2_transverse = pg.cat2['dcm_transverse_mpc'].values
    h = cosmo.h

    startloc, endloc = locs
    loc = startloc

    while loc<endloc:
        pairs = pg.get_neighbors(loc)
        for i,j,r in pairs:

            if wp:
                # pi = h * abs(dcm1[i] - dcm2[j])
                pi = get_pi(dcm1, dcm2, int(i), int(j), h)
                #TODO: implement binning in pi
                if pi>pimax:
                    continue
                #r = rp_unit2mpch(dcm1_transverse, dcm2_transverse, i, j, r, h)
                # dcm_transverse_avg = 0.5 * (dcm1_transverse[i] + dcm2_transverse[j])
                # r *= dcm_transverse_avg * h

            # Now this is rp if wp or just r if 3d
            if r<=rmax:
                for bb in range(bnum):
                    u_ij = basisfunc[bb](pg.cat1, pg.cat2, i, j, r, *args)

                    counts[bb] += u_ij

                    if tensor:
                        if u_ij.any() != 0:
                            ein = np.einsum('i,j', u_ij, u_ij, out=outarr)
                            counts_tensor[bb] += ein

        #pairs = pg.get_neighbors(loc)
        loc += 1


    if tensor:
        if outq:
            outq.put([counts, counts_tensor])
            #outq.put(counts_tensor)
        else:
            return counts, counts_tensor
    else:
        if outq:
            outq.put(counts)
        else:
            return counts


def get_pi(dcm1, dcm2, i, j, h):
    pi = h * abs(dcm1[i] - dcm2[j])
    return pi

# Goes from unit rp to physical rp
def rp_unit2mpch(dcm1_t, dcm2_t, i, j, r, h):
    dcm_transverse_avg = 0.5 * (dcm1_t[i] + dcm2_t[j])
    r *= dcm_transverse_avg * h
    return r

def get_obj(cat, idx):
    return cat.iloc[idx]

# def calc_rp(cat1, cat2, i, j, cosmo):
#
#     unitdist = np.sqrt((cat1['xproj'][i] - cat2['xproj'][j])**2
#                      + (cat1['yproj'][i] - cat2['yproj'][j])**2
#                      + (cat1['zproj'][i] - cat2['zproj'][j])**2)
#
#     #making dcm_transverse average of two but idk what is correct
#     dcm_transverse = 0.5*(cat1['dcm_transverse_mpc'][i]+cat2['dcm_transverse_mpc'][j])
#     rp = unitdist * dcm_transverse * cosmo.h
#     return rp

def top(x, peak, width):
    if np.isscalar(x):
        if (x>peak-width/2.)&(x<peak+width/2.):
            return 1
        return 0
    t = np.zeros(len(x))
    t[(x>peak-width/2.)&(x<peak+width/2.)] = 1
    return t

def piece(x, peak, width):
    p = np.array(1 - (1. / width) * abs(x - peak))
    p[(x<peak-width)^(x>peak+width)] = 0
    return p

def gauss(x, peak, width):
    sigma = width/(2.*np.sqrt(2*np.log(2.)))
    return np.array(np.exp(-(x - peak) ** 2 / (2. * sigma ** 2)))

def tophat(cat1, cat2, i, j, rp, logbins_avg, logwidth):
    logrp = np.log10(rp)
    # u = np.zeros(len(logbins_avg))
    # for i in range(len(u)):
    #     peak = logbins_avg[i]
    #     u[i] = top(logrp, peak, logwidth)
    u = np.array([top(logrp, peak, logwidth) for peak in logbins_avg])
    return u

def tophat_fast(cat1, cat2, i, j, rp, logbins, logwidth):
    #print logbins
    #print rp
    ins = int((np.log10(rp) - min(logbins)) / logwidth)
    #print ins
    #print
    u = np.zeros(len(logbins)-1)
    if ins>=0 and ins<len(logbins)-1:
        u[ins] = 1
    return u

#def quad(cat1, cat2, i, j, rp, logbins_avg, logwidth, val=None)

def top_z(cat1, cat2, i, j, rp, logbins_avg, logwidth, val=None):
    logrp = np.log10(rp)
    u = np.array([top(logrp, peak, logwidth) for peak in logbins_avg])
    if not val:
        val = 0.5*(cat1['z'][i] + cat2['z'][j])
    u = np.concatenate((u, u*val, u*val**2))
    return u

def top_Mr(cat1, cat2, i, j, rp, logbins_avg, logwidth, val=None):
    logrp = np.log10(rp)
    u = np.array([top(logrp, peak, logwidth) for peak in logbins_avg])
    if not val:
        val = 0.5*(cat1['M_r'][i] + cat2['M_r'][j])
    u = np.concatenate((u, u*val, u*val**2))
    return u

def gauss_Mr(cat1, cat2, i, j, rp, logbins_avg, logwidth, val=None):
    logrp = np.log10(rp)
    u = np.array([gauss(logrp, peak, logwidth) for peak in logbins_avg])
    if not val:
        val = 0.5*(cat1['M_r'][i] + cat2['M_r'][j])
    u = np.concatenate((u, u*val, u*val**2))
    return u

def gauss_z(cat1, cat2, i, j, rp, logbins_avg, logwidth, val=None):
    logrp = np.log10(rp)
    u = np.array([gauss(logrp, peak, logwidth) for peak in logbins_avg])
    if not val:
        val = 0.5*(cat1['z'][i] + cat2['z'][j])
    u = np.concatenate((u, u*val, u*val**2))
    return u

def piecewise(cat1, cat2, i, j, rp, logbins_avg, logwidth):
    logrp = np.log10(rp)
    u = np.array([piece(logrp, peak, logwidth) for peak in logbins_avg])
    return u

def gaussian(cat1, cat2, i, j, rp, logbins_avg, logwidth):
    logrp = np.log10(rp)
    u = np.array([gauss(logrp, peak, logwidth) for peak in logbins_avg])
    return u

def trig(cat1, cat2, i, j, rp, logbins_avg, logwidth):
    N = len(logbins_avg)/2
    kbins = np.logspace(-1, 1, N)
    if np.isscalar(rp) and rp==0:
        return np.zeros(N*2)
    u = []
    logrp = np.log10(rp)
    L = max(logbins_avg)
    #for n in range(1, N+1):
    for i in range(len(kbins)):
        kmode = kbins[i]
        s = np.sin(2.*np.pi*kmode*logrp / L)
        c = np.cos(2.*np.pi*kmode*logrp / L)
        u.append(s)
        u.append(c)
    return np.array(u)