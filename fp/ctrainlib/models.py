from typing import Any, List, Dict

import numpy as np
import pandas as pd
from pandas import DataFrame
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from ctrainlib.fplib import FingerprintInfo


class Regressor:
    """
    Wrapper class for other regressor classes like all basic scikit-learn like regressors. A class
    instance holds also all information that are needed for prediction, like the scaler, redundant
    fingerprint columns, used descriptors and so on.

    Parameters
    ----------
    model : Any
        The actual regressor object
    name : str
        Name of the model
    scaler : StandardScaler
        A fitted StandardScaler instance to scale the descriptor data
    redundant_cols : List[str]
        A list of redundant fingerprint columns (generated by fingerprint variance filtering)
    descriptors : List[str]
        List of descriptor names used for training
    fingerprints : List[FingerprintInfo]
        List of FingerprintInfo instances containing information about the fingerprints used for training
    """
    __slots__ = ('model', 'name', 'descriptors', 'fingerprints', 'scaler', 'redundant_cols')

    def __init__(self, model: Any,
                 name: str,
                 scaler: StandardScaler = None,
                 redundant_cols: List[str] = None,
                 descriptors: List[str] = None,
                 fingerprints: List[FingerprintInfo] = None):
        self.model = model
        self.name = name
        self.descriptors = descriptors
        self.fingerprints = fingerprints
        self.scaler = scaler
        self.redundant_cols = redundant_cols

    def predict(self, x_data: DataFrame) -> DataFrame:
        """
        Does a prediction with the provided ``x_data`` against the model in ``self.model``.

        Parameters
        ----------
        x_data : DataFrame
            X data to use for prediction. The DataFrame has to contain all
            descriptors and fingerprints used for training.

        Returns
        -------
        DataFrame
            Containing the predictions for the input X data
        """

        x_data = x_data.copy()
        index = x_data.index

        if self.redundant_cols:
            x_data.drop(columns=self.redundant_cols, inplace=True)

        if self.scaler:
            x_data.loc[:, self.descriptors] = self.scaler.transform(np.array(x_data[self.descriptors]))

        y = self.model.predict(np.array(x_data))

        return pd.DataFrame(data={f'{self.name}_prediction': y}, index=index)


class Classifier:
    """
    Wrapper class for other classifier classes like `CVClassifier`, `NestedClusterCVClassifier` `DNNClassifier`
    and all basic scikit-learn like classifier. A class instance holds also all information that are needed
    for prediction, like the scaler, redundant fingerprint columns, used descriptors and so on.

    Parameters
    ----------
    model : Any
        The actual classifier object
    name : str
        Name of the model
    scaler : StandardScaler
        A fitted StandardScaler instance to scale the descriptor data
    redundant_cols : List[str]
        A list of redundant fingerprint columns (generated by fingerprint variance filtering)
    descriptors : List[str]
        List of descriptor names used for training
    fingerprints : List[FingerprintInfo]
        List of FingerprintInfo instances containing information about the fingerprints used for training
    """
    __slots__ = ('model', 'name', 'descriptors', 'fingerprints', 'scaler', 'redundant_cols')

    def __init__(self, model: Any,
                 name: str,
                 scaler: StandardScaler = None,
                 redundant_cols: List[str] = None,
                 descriptors: List[str] = None,
                 fingerprints: List[FingerprintInfo] = None):
        self.model = model
        self.name = name
        self.descriptors = descriptors
        self.fingerprints = fingerprints
        self.scaler = scaler
        self.redundant_cols = redundant_cols

    def predict(self, x_data: DataFrame) -> DataFrame:
        """
        Does a prediction with the provided ``x_data`` against the model in ``self.model``.

        Parameters
        ----------
        x_data : DataFrame
            X data to use for prediction. The DataFrame has to contain all
            descriptors and fingerprints used for training.

        Returns
        -------
        DataFrame
            Containing the predictions and probabilities for the input X data
        """

        x_data = x_data.copy()
        index = x_data.index

        if self.redundant_cols:
            x_data.drop(columns=self.redundant_cols, inplace=True)

        if self.scaler:
            x_data.loc[:, self.descriptors] = self.scaler.transform(np.array(x_data[self.descriptors]))

        y = self.model.predict_proba(np.array(x_data))

        predictions = []
        probabilities = []

        for values in y:
            best_i = values.argmax()
            predictions.append(self.model.classes_[best_i])
            probabilities.append(values[best_i])
        prediction_name = f'{self.name}_prediction'
        probability_name = f'{self.name}_probability'
        probability_columns = [f'{self.name}_probability_{i}' for i in range(len(self.model.classes_))]
        return pd.concat([pd.DataFrame(data={prediction_name: predictions, probability_name: probabilities},
                                       index=index),
                          pd.DataFrame(y, columns=probability_columns, index=index)], axis=1)


class CVClassifier:
    """
    Classifier that predicts based on predictions of k models from k-fold CV.

    Accepts any Scikit-learn-like classifier as base classifier. It trains k models
    by doing stratified k-fold CV and stores the individual models. Predictions
    on new samples are done by calculating mean probabilities from all models.

    Parameters
    ----------
    clf : Any
        Scikit-learn (-like) classifier object. Must contain .fit(), .predict() and .predict_proba() methods.
    params : Dict[str, Any]
        Classifier parameters
    n_folds : int
        Number of folds for stratified k-fold
    shuffle : bool
        Shuffling of data for CV
    """
    __slots__ = ('clf', 'params', 'models', 'n_folds', 'shuffle', 'classes_')

    def __init__(self, clf: Any, params: Dict[str, Any], n_folds: int = 5, shuffle: bool = True):
        self.clf = clf
        self.params = params
        self.models = []
        self.n_folds = n_folds
        self.shuffle = shuffle
        self.classes_ = None

    def _mean_proba(self, x_data: np.ndarray) -> np.ndarray:
        """
        Calculate probabilities as mean of all probabilities from all models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Array containing the x_data which should be used for prediction

        Returns
        -------
        numpy.ndarray
            Array containing the predicted mean probabilities
        """

        predictions = []
        for model in self.models:
            predictions.append(model.predict_proba(x_data))
        return np.divide(np.sum(predictions, axis=0), self.n_folds)

    def fit(self, x_data: np.ndarray, y_data: np.ndarray) -> None:
        """
        Build a classifier consisting of k-models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Training data
        y_data : numpy.ndarray
            Target values
        """

        skf = StratifiedKFold(n_splits=self.n_folds, shuffle=self.shuffle, random_state=self.params['random_state'])
        kf = skf.split(X=x_data, y=y_data)

        # Fit k models and store them
        for train_index, test_index in kf:
            clf_tmp = self.clf(**self.params)
            clf_tmp.fit(x_data[train_index], y_data[train_index])
            self.models.append(clf_tmp)

    def predict(self, x_data: np.ndarray) -> np.ndarray:
        """
        Predict using majority vote from k models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Samples to predict

        Returns
        -------
        numpy.ndarray
            Predicted classes
        """

        probas = self._mean_proba(x_data)
        pred = np.array([self.classes_[x] for x in list(np.argmax(probas, axis=1))])
        return pred

    def predict_proba(self, x_data: np.ndarray) -> np.ndarray:
        """
        Predict probability using k models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Samples to predict

        Returns
        -------
        numpy.ndarray
            Predicted probabilities
        """

        return self._mean_proba(x_data)


class NestedClusterCVClassifier:
    """
    Classifier that predicts based on predictions of k models from k-fold CV.

    Accepts any Scikit-learn-like classifier as base classifier. It trains k models
    by using the provided outer clusters to generate the folds while fitting. For every cluster/fold,
    the remaining clusters are used to build the inner folds. For example if ``outer_clusters`` contains
    five different clusters, altogether 5 * 4 models are trained and used for prediction.
    Predictions on new samples are done by calculating mean probabilities from all models.

    Parameters
    ----------
    clf : Any
        Scikit-learn (-like) classifier object. Must contain .fit(), .predict() and .predict_proba() methods.
    params : Dict[str, Any]
        Classifier parameters
    outer_clusters : np.ndarray
        Cluster assignments for training molecules to use for fitting and building the inner and outer folds
    shuffle : bool
        Shuffling of data for CV
    """
    __slots__ = ('clf', 'params', 'models', 'n_folds', 'shuffle', 'classes_', 'outer_clusters')

    def __init__(self, clf: Any, params: Dict[str, Any], outer_clusters: np.ndarray, shuffle: bool = True):
        self.clf = clf
        self.params = params
        self.models = []
        self.outer_clusters = outer_clusters
        self.n_folds = len(np.unique(outer_clusters))
        self.shuffle = shuffle
        self.classes_ = None

    def _mean_proba(self, x_data: np.ndarray) -> np.ndarray:
        """
        Calculate probabilities as mean of all probabilities from all models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Array containing the x_data which should be used for prediction

        Returns
        -------
        numpy.ndarray
            Array containing the predicted mean probabilities
        """

        predictions = []
        for model in self.models:
            predictions.append(model.predict_proba(x_data))
        return np.divide(np.sum(predictions, axis=0), self.n_folds)

    def fit(self, x_data: np.ndarray, y_data: np.ndarray) -> None:
        """
        Build a classifier consisting of ``n_clusters * (n_clusters - 1)`` models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Training data
        y_data : numpy.ndarray
            Target values
        """

        for fold in range(self.n_folds):
            inner_cluster_mask = np.logical_not(self.outer_clusters == fold)
            inner_cluster_ix = np.where(inner_cluster_mask)[0]
            inner_x = x_data[inner_cluster_ix]
            inner_y = y_data[inner_cluster_ix]
            inner_clusters = self.outer_clusters[inner_cluster_ix]

            for inner_fold in np.unique(inner_clusters):
                train_ix = np.where(np.logical_not(inner_clusters == inner_fold))[0]
                clf_tmp = self.clf(**self.params)
                clf_tmp.fit(inner_x[train_ix], inner_y[train_ix])
                self.models.append(clf_tmp)

    def predict(self, x_data: np.ndarray) -> np.ndarray:
        """
        Predict using majority vote from k models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Samples to predict

        Returns
        -------
        numpy.ndarray
            Predicted classes
        """

        probas = self._mean_proba(x_data)
        pred = np.array([self.classes_[x] for x in list(np.argmax(probas, axis=1))])
        return pred

    def predict_proba(self, x_data: np.ndarray) -> np.ndarray:
        """
        Predict probability using k models.

        Parameters
        ----------
        x_data : numpy.ndarray
            Samples to predict

        Returns
        -------
        numpy.ndarray
            Predicted probabilities
        """

        return self._mean_proba(x_data)