import numpy as np
from scipy.spatial import KDTree



def pairs(data1, rand1, data2, rand2, rpmax, cosmo, wp):

    d1tree, r1tree, d2tree, r2tree = construct_trees([data1, rand1, data2, rand2], wp)

    print 'Computing D1D2 pairs'
    d1d2pairs = compute_pairs(data1, data2, d2tree, rpmax, cosmo, wp)
    print 'Computing D1R2 pairs'
    d1r2pairs = compute_pairs(data1, rand2, r2tree, rpmax, cosmo, wp)
    print 'Computing D2R1 pairs'
    d2r1pairs = compute_pairs(data2, rand1, r1tree, rpmax, cosmo, wp)
    print 'Computing R1R2 pairs'
    r1r2pairs = compute_pairs(rand1, rand2, r2tree, rpmax, cosmo, wp)

    print len(data1)
    print len(rand1)
    print len(d1d2pairs)
    print len(d1r2pairs)
    print len(d2r1pairs)
    print len(r1r2pairs)

    return d1d2pairs, d1r2pairs, d2r1pairs, r1r2pairs


# TODO: rename rp to r
def compute_pairs(df_cat, df_tree, tree, rmax, cosmo, wp):

    pairs = []
    ncat = len(df_cat)
    ntree = len(tree.data)

    for i in range(ncat):
        ipoint = np.array([df_cat['xproj'][i], df_cat['yproj'].values[i], df_cat['zproj'].values[i]])
        if not wp:
            ipoint *= df_cat['dcm_mpc'][i] #turn projected into real space
            rmax_tree = rmax
        if wp:
            # here the given rmax rmax is really rpmax
            rmax_tree = rmax/(df_cat['dcm_transverse_mpc'][i] * cosmo.h) #turn bin into unit dist

        dists, locs = tree.query(ipoint, k=ntree, distance_upper_bound=rmax_tree)

        # Query returns infinities when <k neighbors are found, cut these
        if locs[-1] == ntree:
            imax = next(index for index, value in enumerate(locs) if value == ntree)
            locs = locs[:imax]
            dists = dists[:imax]

        if wp:
            dists = np.array([dists[k]*0.5*(df_cat['dcm_transverse_mpc'][i]
                    + df_tree['dcm_transverse_mpc'][locs[k]]) for k in range(len(locs))])

        # if wp: dists are transverse distances in mpc/h
        # if not wp: dists are real space 3d dists in mpc/h
        dists *= cosmo.h
        pairs += [(i, locs[k], dists[k]) for k in range(len(locs))]

    return pairs


def construct_trees(dfs, wp):
    print 'Constructing trees'
    trees = []
    for df in dfs:
        points = np.array([df['xproj'], df['yproj'], df['zproj']])
        if not wp:
            points *= df['dcm_mpc']
        trees.append(KDTree(list(points.T)))
    return trees