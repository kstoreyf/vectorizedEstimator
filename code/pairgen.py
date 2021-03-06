import numpy as np
from scipy.spatial import KDTree




class PairGen():


    def __init__(self, cat1, cat2, rmax, cosmo, wp, chunksize=20):
        self.cat1 = cat1
        self.cat2 = cat2
        self.rmax = rmax
        self.cosmo = cosmo
        self.wp = wp
        #self.cat1loc = 0
        #self.cat1stop = len(cat1)
        self.chunksize = chunksize
        self.construct_tree()


    def get_pairchunk(self, cat1start):

        #print self.cat1loc
        #print self.chunksize

        # if self.cat1loc >= min(self.cat1stop, len(self.cat1)):
        #     return []

        cat1loc = cat1start
        pairchunk = []
        while len(pairchunk) < self.chunksize:
            pairs = self.get_neighbors(cat1loc)
            # Eliminate self-pairs with zero separation
            pairs = [p for p in pairs if p[2] > 0]
            #print len(pairs)
            pairchunk += pairs
            cat1loc += 1
            #print len(pairchunk)
            #print
        return pairchunk, cat1loc


    def get_neighbors(self, cat1loc):

        i = cat1loc
        #print self.cat1
        #print list(self.cat1)
        ipoint = np.array([self.cat1['xproj'].values[i], self.cat1['yproj'].values[i], self.cat1['zproj'].values[i]])
        if not self.wp:
            ipoint *= self.cat1['dcm_mpc'].values[i]  # turn projected into real space
            rmax_tree = self.rmax
        if self.wp:
            # here the given rmax rmax is really rpmax
            rmax_tree = self.rmax / (self.cat1['dcm_transverse_mpc'].values[i] * self.cosmo.h)  # turn bin into unit dist

        ntree = len(self.tree.data)
        dists, locs = self.tree.query(ipoint, k=ntree, distance_upper_bound=rmax_tree)

        # Query returns infinities when <k neighbors are found, cut these
        if locs[-1] == ntree:
            imax = next(index for index, value in enumerate(locs) if value == ntree)
            locs = locs[:imax]
            dists = dists[:imax]

        if self.wp:
            dists = np.array([dists[k] * 0.5 * (self.cat1['dcm_transverse_mpc'].values[i]
                                                + self.cat2['dcm_transverse_mpc'].values[locs[k]]) for k in range(len(locs))])

        # if wp: dists are transverse distances in mpc/h
        # if not wp: dists are real space 3d dists in mpc/h
        # TODO: don't know why don't need this??
        #dists *= self.cosmo.h

        pairs = [(i, locs[k], dists[k]) for k in range(len(locs))]
        #Eliminate self-pairs
        pairs = [p for p in pairs if p[2] > 0]
        #self.cat1loc += 1

        return pairs



    def construct_tree(self):
        print 'Constructing tree from cat2'

        treecat = self.cat2
        points = np.array([treecat['xproj'], treecat['yproj'], treecat['zproj']])
        if not self.wp:
            points *= treecat['dcm_mpc']
        self.tree = KDTree(list(points.T))