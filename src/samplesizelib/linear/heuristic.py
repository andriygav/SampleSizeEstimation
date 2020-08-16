#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
The :mod:`samplesizelib.linear.heuristic` contains classes:

- :class:`samplesizelib.linear.heuristic.CrossValidationEstimator`
- :class:`samplesizelib.linear.heuristic.BootstrapEstimator`
"""
from __future__ import print_function

__docformat__ = 'restructuredtext'

from multiprocessing import Pool

import numpy as np
from tqdm import tqdm
from sklearn.utils import shuffle

from ..shared.estimator import SampleSizeEstimator
from ..shared.utils import Dataset

class CrossValidationEstimator(SampleSizeEstimator):
    r"""
    Description of Cross Validation Method

    :param statmodel: the machine learning algorithm
    :type statmodel: RegressionModel or LogisticModel
    :param averaging: to do
    :type averaging: float
    :param epsilon: to do
    :type epsilon: float
    :param begin: to do
    :type begin: int
    :param end: to do
    :type end: int
    :param num: to do
    :type num: int
    :param test_size: to do
    :type test_size: float
    :param multiprocess: to do
    :type multiprocess: bool
    :param progressbar: to do
    :type progressbar: bool
    """

    def __init__(self, statmodel, **kwards):
        r"""Constructor method
        """
        self.statmodel = statmodel

        self.averaging = int(kwards.pop('averaging', 100))
        if self.averaging <= 0:
            raise ValueError(
                "The averaging should be positive but get {}".format(
                    self.averaging))

        self.test_size = kwards.pop('test_size', 0.5)
        if self.test_size < 0 or self.test_size > 1:
            raise ValueError(
                "The test_size must be between 0 and 1 but get {}".format(
                    self.test_size))

        self.epsilon = kwards.pop('epsilon', 0.05)
        if self.epsilon <= 0:
            raise ValueError(
                "The epsilon must be positive value but get {}".format(
                    self.epsilon))
        
        self.begin = kwards.pop('begin', None)
        if self.begin is not None and self.begin <0:
            raise ValueError(
                "The begin must be positive value but get {}".format(
                    self.begin))

        self.end = kwards.pop('end', None)
        if self.end is not None and self.end < 0:
            raise ValueError(
                "The end must be positive value but get {}".format(
                    self.end))

        if self.end is not None and self.begin is not None and self.end <= self.begin:
            raise ValueError(
                "The end value must be greater than the begin value but {}<={}".format(
                    self.end, self.begin))

        self.num = kwards.pop('num', 5)
        if self.num <=0:
            raise ValueError(
                "The num must be positive value but get {}".format(
                    self.num))
        if self.end is not None and self.begin is not None and self.num >= self.end - self.begin:
            raise ValueError(
                "The num value must be smaler than (end - begin) but {}>={}".format(
                    self.num, self.end - self.begin))

        self.multiprocess = kwards.pop('multiprocess', False)
        if not isinstance(self.multiprocess, bool):
            raise ValueError(
                "The multiprocess must be bool value but get {}".format(
                    self.multiprocess))

        self.progressbar = kwards.pop('progressbar', False)
        if not isinstance(self.progressbar, bool):
            raise ValueError(
                "The progressbar must be bool value but get {}".format(
                    self.progressbar))

        if kwards:
            raise ValueError("Invalid parameters: %s" % str(kwards))

        self.dataset = None

    def _RS(self, dataset):
        r"""
        Return ...
        """
        X_train, X_test, y_train, y_test = dataset.train_test_split(self.test_size)

        w_hat = self.statmodel(y_train, X_train).fit()

        S_train = self.statmodel(y_train, X_train).loglike(w_hat)/y_train.shape[0]
        S_test = self.statmodel(y_test, X_test).loglike(w_hat)/y_test.shape[0]
        return S_train - S_test

    def _score_subsample(self, m):
        r"""
        Return ...
        """
        X_m, y_m = self.dataset.sample(m)
        dataset_m = Dataset(X_m, y_m)
        return self._RS(dataset_m)

    def forward(self, features, target):
        r"""
        Returns sample size prediction for the given dataset.
        
        :param features: The tensor of shape
            `num_elements` :math:`\times` `num_feature`.
        :type features: array.
        :param target: The tensor of shape `num_elements`.
        :type target: array.
        
        :return: sample size estimation for the given dataset.
        :rtype: dict
        """

        self.dataset = Dataset(features, target)

        if self.end is None:
            end = len(self.dataset) - 1
        else:
            end = self.end

        if self.begin is None:
            begin = 2*self.dataset.n
        else:
            begin = self.begin

        if end <= begin:
            raise ValueError(
                "The end value must be greater than the begin value but {}<={}".format(
                    end, begin))

        if self.num >= end - begin:
            raise ValueError(
                "The num value must be smaler than (end - begin) but {}>={}".format(
                    self.num, end - begin))

        subset_sizes = np.arange(begin, end, self.num, dtype=np.int64)

        list_of_answers = []
        points_one = np.ones(self.averaging, dtype=np.int64)

        if self.multiprocess:
            pool = Pool()
            mapping = pool.map
        else:
            mapping = map

        if self.progressbar:
            iterator = tqdm(subset_sizes)
        else:
            iterator = subset_sizes

        for m in iterator:
            list_of_answers.append(
                np.asarray(
                    list(mapping(self._score_subsample, m*points_one))))

        if self.multiprocess:
            pool.close()
            pool.join()

        list_of_answers = np.asarray(list_of_answers)

        list_of_E = np.mean(list_of_answers, axis = 1)
        list_of_S = np.std(list_of_answers, axis = 1)

        m_size = end
        for m, mean in zip(reversed(subset_sizes), reversed(list_of_E)):
            if mean < self.epsilon:
                m_size = m

        return {'m*': m_size,
                'E': np.array(list_of_E),
                'S': np.array(list_of_S),
                'm': np.array(subset_sizes),
               }


class BootstrapEstimator(SampleSizeEstimator):
    r"""
    Description of Bootstrap Method

    :param statmodel: the machine learning algorithm
    :type statmodel: RegressionModel or LogisticModel
    :param averaging: to do
    :type averaging: float
    :param epsilon: to do
    :type epsilon: float
    :param begin: to do
    :type begin: int
    :param end: to do
    :type end: int
    :param num: to do
    :type num: int
    :param multiprocess: to do
    :type multiprocess: bool
    :param progressbar: to do
    :type progressbar: bool
    """

    def __init__(self, statmodel, **kwards):
        r"""Constructor method
        """
        self.statmodel = statmodel

        self.averaging = int(kwards.pop('averaging', 100))
        if self.averaging <= 0:
            raise ValueError(
                "The averaging should be positive but get {}".format(
                    self.averaging))

        self.epsilon = kwards.pop('epsilon', 0.5)
        if self.epsilon <= 0:
            raise ValueError(
                "The epsilon must be positive value but get {}".format(
                    self.epsilon))
        
        self.begin = kwards.pop('begin', None)
        if self.begin is not None and self.begin < 0:
            raise ValueError(
                "The begin must be positive value but get {}".format(
                    self.begin))

        self.end = kwards.pop('end', None)
        if self.end is not None and self.end < 0:
            raise ValueError(
                "The end must be positive value but get {}".format(
                    self.end))

        if self.end is not None and self.begin is not None and self.end <= self.begin:
            raise ValueError(
                "The end value must be greater than the begin value but {}<={}".format(
                    self.end, self.begin))

        self.num = kwards.pop('num', 5)
        if self.num <=0:
            raise ValueError(
                "The num must be positive value but get {}".format(
                    self.num))
        if self.end is not None and self.begin is not None and self.num >= self.end - self.begin:
            raise ValueError(
                "The num value must be smaler than (end - begin) but {}>={}".format(
                    self.num, self.end - self.begin))

        self.multiprocess = kwards.pop('multiprocess', False)
        if not isinstance(self.multiprocess, bool):
            raise ValueError(
                "The multiprocess must be bool value but get {}".format(
                    self.multiprocess))

        self.progressbar = kwards.pop('progressbar', False)
        if not isinstance(self.progressbar, bool):
            raise ValueError(
                "The progressbar must be bool value but get {}".format(
                    self.progressbar))

        if kwards:
            raise ValueError("Invalid parameters: %s" % str(kwards))

        self.dataset = None


    def _bFunction(self, dataset):
        r"""
        Return ...
        """
        X, y = dataset.sample()

        w_hat = self.statmodel(y, X).fit()

        if len(list(set(list(y)))) != 2:
            y_hat = self.statmodel(y, X).predict(w_hat)
            Es = y - y_hat
            y_new = y_hat + (Es - Es.mean())
            w_res = self.statmodel(y_new, X).fit()
        else:
            w_res = w_hat
        return w_res

    def _score_subsample(self, m):
        r"""
        Return ...
        """
        X_m, y_m = self.dataset.sample(m)
        dataset_m = Dataset(X_m, y_m)
        return self._bFunction(dataset_m)

    def forward(self, features, target):
        r"""
        Returns sample size prediction for the given dataset.
        
        :param features: The tensor of shape
            `num_elements` :math:`\times` `num_feature`.
        :type features: array.
        :param target: The tensor of shape `num_elements`.
        :type target: array.
        
        :return: sample size estimation for the given dataset.
        :rtype: dict
        """

        self.dataset = Dataset(features, target)

        if self.end is None:
            end = len(self.dataset) - 1
        else:
            end = self.end

        if self.begin is None:
            begin = 2*self.dataset.n
        else:
            begin = self.begin

        if end <= begin:
            raise ValueError(
                "The end value must be greater than the begin value but {}<={}".format(
                    end, begin))

        if self.num >= end - begin:
            raise ValueError(
                "The num value must be smaler than (end - begin) but {}>={}".format(
                    self.num, end - begin))

        subset_sizes = np.arange(begin, end, self.num, dtype=np.int64)

        list_of_answers = []
        points_one = np.ones(self.averaging, dtype=np.int64)

        if self.multiprocess:
            pool = Pool()
            mapping = pool.map
        else:
            mapping = map

        if self.progressbar:
            iterator = tqdm(subset_sizes)
        else:
            iterator = subset_sizes

        for m in iterator:
            list_of_answers.append(
                np.asarray(
                    list(mapping(self._score_subsample, m*points_one))))

        if self.multiprocess:
            pool.close()
            pool.join()

        list_of_answers = np.asarray(list_of_answers)

        percentile_diff = np.abs(
            np.percentile(list_of_answers, 2.5, axis=1)
            -np.percentile(list_of_answers, 97.5, axis=1))

        list_of_E = np.max(percentile_diff, axis=-1)
        list_of_S = np.zeros_like(list_of_E)

        m_size = end
        for m, mean in zip(reversed(subset_sizes), reversed(list_of_E)):
            if mean < self.epsilon:
                m_size = m

        return {'m*': m_size,
                'E': np.array(list_of_E),
                'S': np.array(list_of_S),
                'm': np.array(subset_sizes),
               }














