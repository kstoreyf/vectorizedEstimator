import numpy as np
import pandas as pd
from scipy import interpolate
from astropy.cosmology import LambdaCDM
import time

import treecorr
import corrfunc

import pairs
import estimator
import plotter


def main():

    #nd = 10
    #nd = 31
    nd = 102
    #nd = 3158
    #nd = 10015
    data1fn = '../../lss/mangler/samples/a0.6452_0001.v5_ngc_ifield_ndata{}.rdzw'.format(nd)
    rand1fn = '../../lss/mangler/samples/a0.6452_rand20x.dr12d_cmass_ngc_ifield_ndata{}.rdz'.format(nd)
    data2fn = data1fn
    rand2fn = rand1fn

    print 'Running for n_data={}'.format(nd)

    K = 4
    #Separations should be given in Mpc/h
    pimax = 1000 #Mpc/h
    rpmin = 0.1
    rpmax = 10. #Mpc/h
    bin_sep = np.log(rpmax / rpmin) / float(K)

    rps = []
    wprps = []
    labels = []

    basisfunc = [estimator.tophat]
    labels = ['tophat_orig']
    #basisfunc = [estimator.tophat, estimator.piecewise, estimator.gaussian, estimator.trig]
    #labels = ['tophat', 'piecewise', 'gaussian', 'trig']


    #rpbins = np.logspace(np.log10(rpmin), np.log10(rpmax), K+1)
    rpbins = np.logspace(np.log(rpmin), np.log(rpmax), K+1, base=np.e)

    rpbins_avg = 0.5 * (rpbins[1:] + rpbins[:-1])
    logrpbins_avg = np.log10(rpbins_avg)

    logwidth = np.log10(rpbins_avg[1]) - np.log10(rpbins_avg[0])
    wp = True #vs 3d

    cosmo = LambdaCDM(H0=70, Om0=0.3, Ode0=0.7)



    start = time.time()
    rps, wprps = run(data1fn, rand1fn, data2fn, rand2fn, pimax, rpmin, rpmax, bin_sep,
                           basisfunc, K, cosmo, wp, rpbins, logrpbins_avg, logwidth)

    end = time.time()
    #print 'Time: {:3f} s'.format(end-start)

    labels += ['tophat_orig']
    labels += ['treecorr']

    # est_corrfunc, wprp_corrfunc = run_corrfunc(data1fn, rand1fn, data2fn, rand2fn, rpbins, pimax)
    # rps.append(rpbins_avg)
    # wprps.append(wprp_corrfunc)
    # labels.append('corrfunc')
    #
    #
    # data1 = pd.read_csv(data1fn)
    # rand1 = pd.read_csv(rand1fn)
    # xi_tree = run_treecorr(data1, rand1, data1, rand1, rpmin, rpmax, bin_sep, pimax, wp)
    # rps.append(rpbins_avg)
    # wprps.append(xi_tree)
    # labels.append('treecorr')

    print bin_sep
    print rpbins

    print len(wprps)
    print len(rps)
    print labels
    plotter.plot_wprp(rps, wprps, labels, wp_tocompare='tophat_orig')


def run(data1fn, rand1fn, data2fn, rand2fn, pimax, rmin, rmax, bin_sep, basisfunc, K, cosmo, wp, rpbins, *args):
    print 'Loading data'
    data1 = pd.read_csv(data1fn)
    rand1 = pd.read_csv(rand1fn)
    data2 = pd.read_csv(data2fn)
    rand2 = pd.read_csv(rand2fn)

    # should make so can take list
    print 'Adding info to dataframes'
    data1 = add_info(data1, zfile=None)
    rand1 = add_info(rand1, zfile=None)
    data2 = add_info(data2, zfile=None)
    rand2 = add_info(rand2, zfile=None)

    # if wp, rmax means rpmax
    # TODO: now mine returns all up to max and treecorr's returns above rmin too - make consistent!
    # TODO: and don't forget self-corrs
    start = time.time()
    xi, d1d2pairs_tc, d1r2pairs_tc, d2r1pairs_tc, r1r2pairs_tc = pairs_treecorr(data1, rand1, data2, rand2,
                                                                rmin, rmax, bin_sep, pimax, wp)
    end = time.time()
    print "Time treecorr pairs:", end-start

    start = time.time()
    d1d2pairs, d1r2pairs, d2r1pairs, r1r2pairs = pairs.pairs(data1, rand1, data2, rand2,
                                                             rmax, cosmo, wp)
    end = time.time()
    print "Time pairs:", end-start

    # print 'pair comp'
    # print d1d2pairs
    # print d1d2pairs_tc
    # print len(d1d2pairs)
    # print len(d1d2pairs_tc)

    #TODO next: decide whether want to include self-corrs (1, 1) and double count pairs /
    #TODO aka (1,2) and (2,1), and calculate xi in the right corresponding way
    #TODO but in mine not perfectly semetric, 0,1 there but not 1,0

    #TODO figure out why slightly diff pairs
    #TODO figure out why r-separations different for same pairs in my vs treecorr


    #print stopit

    if type(basisfunc)!=list:
        basisfunc = [basisfunc]
    a = estimator.est(d1d2pairs, d1r2pairs, d2r1pairs, r1r2pairs,
                      data1, rand1, data2, rand2, pimax, rmax, cosmo, basisfunc, K, wp, *args)

    # TODO: change for not projected? look at corrfunc

    rps, wprps = calc_wprp(a, basisfunc, K, rpbins, *args)
    # just tophat orig
    rps_orig, wprps_orig = calc_wprp_orig(a, [basisfunc[0]], K, rpbins, *args)
    #print wprps
    print wprps_orig

    rps += rps_orig
    wprps += wprps_orig

    rps += rps_orig
    wprps.append(xi)
    #test treecorr

    return rps, wprps


def calc_wprp(a, basisfunc, K, rpbins, *args):

    x = np.logspace(np.log10(min(rpbins)), np.log10(max(rpbins)), 500)
    rps = []
    wprps = []
    for bb in range(len(basisfunc)):
        bases = basisfunc[bb](None, None, None, None, x, *args)
        xi_rp = np.zeros_like(x)
        for k in range(len(bases)):
            xi_rp += a[bb][k]*bases[k]

        rps.append(x)
        wprps.append(list(2*xi_rp))
    return rps, wprps


def calc_wprp_orig(a, basisfunc, K, rpbins, *args):

    rpbins_avg = 0.5*np.array(rpbins[1:]+rpbins[:-1])
    rps = []
    wprps = []
    for bb in range(len(basisfunc)):
        xi_rp = np.zeros(K)
        for i in range(K):
            u = basisfunc[bb](None, None, None, None, rpbins_avg[i], *args)
            xi_rp[i] = np.matmul(a[bb], u)

        rps.append(rpbins_avg)
        wprps.append(list(2*xi_rp))
    return rps, wprps


def run_corrfunc(data1fn, rand1fn, data2fn, rand2fn, rpbins, pimax):
    print 'Loading data'
    data1 = pd.read_csv(data1fn)
    rand1 = pd.read_csv(rand1fn)
    data2 = pd.read_csv(data2fn)
    rand2 = pd.read_csv(rand2fn)

    #can only do autocorrelations right now
    dd, dr, rr = corrfunc.counts(data1['ra'].values, data1['dec'].values, data1['z'].values,
                    rand1['ra'].values, rand1['dec'].values, rand1['z'].values,
                    rpbins, pimax, comoving=True)

    dd = np.sum(dd, axis=0)
    dr = np.sum(dr, axis=0)
    rr = np.sum(rr, axis=0)

    print 'corrfunc'
    print dd
    print dr
    print rr
    est_ls, wprp = corrfunc.calc_wprp_nopi(dd, dr, rr, len(data1), len(rand1))
    nd = float(len(data1['ra'].values))
    nr = float(len(rand1['ra'].values))
    wprp = (dd*(nr/nd)*(nr/nd) - 2*dr*(nr/nd) + rr)/rr
    print wprp
    print
    return est_ls, wprp


def run_treecorr(data1, rand1, data2, rand2, min_sep, max_sep, bin_size, pimax, wp):

    #TODO: make work for 2 data and 2 rand catalogs

    ra = data1['ra'].values
    dec = data1['dec'].values
    dist = data1['z'].apply(get_comoving_dist).values

    ra_rand = rand1['ra'].values
    dec_rand = rand1['dec'].values
    dist_rand = rand1['z'].apply(get_comoving_dist).values

    ndata = len(ra)
    nrand = len(ra_rand)

    print ndata, nrand
    idx = np.arange(ndata, dtype=long)
    idx_rand = np.arange(nrand, dtype=long)

    cat_data = treecorr.Catalog(ra=ra, dec=dec, r=dist, idx=idx, ra_units='deg', dec_units='deg')
    cat_rand = treecorr.Catalog(ra=ra_rand, dec=dec_rand, r=dist_rand, idx=idx_rand, ra_units='deg', dec_units='deg')

    if wp:
        metric = 'Rperp'
    else:
        metric = 'Euclidean'

    dd = treecorr.NNCorrelation(min_sep=min_sep, max_sep=max_sep, bin_size=bin_size,
                                res_size=ndata**2, min_rpar=-pimax, max_rpar=pimax,
                                bin_slop=0, num_threads=1)
    dd.process(cat_data, metric=metric)
    print 'DD pairs:', len(dd.idxpairs1)

    dr = treecorr.NNCorrelation(min_sep=min_sep, max_sep=max_sep, bin_size=bin_size,
                                res_size=ndata*nrand, min_rpar=-pimax, max_rpar=pimax,
                                bin_slop=0, num_threads=1)
    dr.process(cat_data, cat_rand, metric=metric)
    print 'DR pairs:', len(dr.idxpairs1)

    rd = dr

    rr_res = nrand**2
    if rr_res > 1e8:
        rr_res = 1e8
    rr = treecorr.NNCorrelation(min_sep=min_sep, max_sep=max_sep, bin_size=bin_size,
                                res_size=rr_res, min_rpar=-pimax, max_rpar=pimax,
                                bin_slop=0, num_threads=1)
    rr.process(cat_rand, metric=metric)
    print 'RR pairs:', len(rr.idxpairs1)

    xi, varxi = dd.calculateXi(rr, dr)
    print xi
    #TODO: Figure out factor of 2 issue
    # This gives diff answer - maybe because of fac of two issue (?)
    #xils = calc_ls(dd.npairs, dr.npairs, rr.npairs, ndata, nrand)
    #print xils
    #nd = float(len(ra))
    #nr = float(len(ra_rand))
    # These give same answer, and same as treecor calculateXi function
    #xi = (dd.npairs - 2*dr.npairs*(dd.tot/dr.tot) + rr.npairs*(dd.tot/rr.tot))/(rr.npairs*(dd.tot/rr.tot))
    #xi = (dd.npairs*(nr/nd)*(nr/nd) - dr.npairs*(nr/nd) + rr.npairs)/(rr.npairs)
    return xi, dd, dr, rd, rr


def pairs_treecorr(data1, rand1, data2, rand2, min_sep, max_sep, bin_size, pimax, wp):

    xi, dd, dr, rd, rr = run_treecorr(data1, rand1, data2, rand2, min_sep, max_sep, bin_size, pimax, wp)

    d1d2pairs = zip(dd.idxpairs1, dd.idxpairs2, dd.dists)
    d1r2pairs = zip(dr.idxpairs1, dr.idxpairs2, dr.dists)
    d2r1pairs = zip(rd.idxpairs1, rd.idxpairs2, rd.dists)
    r1r2pairs = zip(rr.idxpairs1, rr.idxpairs2, rr.dists)

    return xi, d1d2pairs, d1r2pairs, d2r1pairs, r1r2pairs


def add_info(df, zfile=None):
    # Project onto unit sphere
    df['xproj'], df['yproj'], df['zproj'] = zip(*df.apply(ra_dec_to_unitxyz, axis=1))

    if zfile==None:
        zfile = '../tables/z_lookup_lcdm_H070_Om0.3_Ode0.7_4dec.csv'

    zdf = pd.read_csv(zfile)

    # Get comoving distances
    interp_dcm = interpolate.interp1d(zdf['z_round'], zdf['dcm_mpc'])
    interp_dcm_transverse = interpolate.interp1d(zdf['z_round'], zdf['dcm_transverse_mpc'])
    df['dcm_mpc'] = df['z'].apply(interp_dcm)
    df['dcm_transverse_mpc'] = df['z'].apply(interp_dcm_transverse)

    #3d position in Mpc
    df['xpos'], df['ypos'], df['zpos'] = zip(*df.apply(unitxyz_to_xyz, axis=1))

    return df


def calc_rp(cat1, cat2, i, j):

    unitdist = np.sqrt((cat1['xproj'][i] - cat2['xproj'][j])**2
                     + (cat1['yproj'][i] - cat2['yproj'][j])**2
                     + (cat1['zproj'][i] - cat2['zproj'][j])**2)

    #making dcm_transverse average of two but idk what is correct
    dcm_transverse = 0.5*(cat1['dcm_transverse_mpc'][i]+cat2['dcm_transverse_mpc'][j])
    rp = unitdist * dcm_transverse * cosmo.h
    return rp

# Real-space distance in Mpc/h
def calc_r3d(cat1, cat2, i, j):

    dist = np.sqrt((cat1['xpos'][i] - cat2['xpos'][j])**2
                     + (cat1['ypos'][i] - cat2['ypos'][j])**2
                     + (cat1['zpos'][i] - cat2['zpos'][j])**2)
    dist *= cosmo.h
    return dist

# Assumes RA, dec in degrees
def ra_dec_to_unitxyz(row):
    ra = row['ra'] * np.pi / 180.
    dec = row['dec'] * np.pi / 180.
    x = np.cos(ra) * np.cos(dec)
    y = np.sin(ra) * np.cos(dec)
    z = np.sin(dec)
    return x, y, z

def unitxyz_to_xyz(row):
    d = row['dcm_mpc']
    x = d*row['xproj']
    y = d*row['yproj']
    z = d*row['zproj']
    return x, y, z

cosmo = LambdaCDM(H0=70, Om0=0.3, Ode0=0.7)

def get_comoving_dist(z):
    comov = cosmo.comoving_distance(z)
    return comov.value*cosmo.h

def calc_ls(dd_counts, dr_counts, rr_counts, ndata, nrand):
    fN = float(nrand)/float(ndata)
    return (fN*fN*dd_counts - 2*fN*dr_counts + rr_counts)/rr_counts


if __name__=='__main__':
    main()