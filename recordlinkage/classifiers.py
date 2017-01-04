# classifier.py

from recordlinkage.algorithms.em import ECMEstimate

import pandas
import numpy

from sklearn import cluster, linear_model, naive_bayes, svm
from sklearn.utils.validation import NotFittedError

import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)


class LearningError(Exception):
    """Learning error"""


class Classifier(object):
    """Base class for classification of records pairs.

    This class contains methods for training the classifier. Distinguish
    different types of training, such as supervised and unsupervised learning.

    """

    def __init__(self):

        self._params = {}

        # The actual classifier. Maybe this is slightly strange because of
        # inheritance.
        self.classifier = None

    def learn(self, comparison_vectors, match_index, return_type='index'):
        """Train the classifier.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The comparison vectors.
        match_index : pandas.MultiIndex
            The true matches.
        return_type : 'index' (default), 'series', 'array'
            The format to return the classification result. The argument value
            'index' will return the pandas.MultiIndex of the matches. The
            argument value 'series' will return a pandas.Series with zeros
            (distinct) and ones (matches). The argument value 'array' will
            return a numpy.ndarray with zeros and ones.

        Returns
        -------
        pandas.Series
            A pandas Series with the labels 1 (for the matches) and 0 (for the
            non-matches).

        """

        if isinstance(match_index, (pandas.MultiIndex, pandas.Index)):

            # The match_index variable is of type MultiIndex
            train_series = pandas.Series(False, index=comparison_vectors.index)

            try:
                train_series.loc[match_index & comparison_vectors.index] = True

            except pandas.IndexError as err:

                # The are no matches. So training is not possible.
                if len(match_index & comparison_vectors.index) == 0:
                    raise LearningError(
                        "both matches and non-matches needed in the" +
                        "trainingsdata, only non-matches found"
                    )
                else:
                    raise err

        self.classifier.fit(
            comparison_vectors.as_matrix(),
            numpy.array(train_series)
        )

        return self.predict(comparison_vectors, return_type)

    def predict(self, comparison_vectors, return_type='index'):
        """Predict the class of the record pairs.

        Classify a set of record pairs based on their comparison vectors into
        matches, non-matches and possible matches. The classifier has to be
        trained to call this method.


        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            Dataframe with comparison vectors.
        return_type : 'index' (default), 'series', 'array'
            The format to return the classification result. The argument value
            'index' will return the pandas.MultiIndex of the matches. The
            argument value 'series' will return a pandas.Series with zeros
            (distinct) and ones (matches). The argument value 'array' will
            return a numpy.ndarray with zeros and ones.

        Returns
        -------
        pandas.Series
            A pandas Series with the labels 1 (for the matches) and 0 (for the
            non-matches).

        """
        try:
            prediction = self.classifier.predict(
                comparison_vectors.as_matrix())
        except NotFittedError:
            raise NotFittedError(
                "This {} is not fitted yet. Call 'learn' with appropriate "
                "arguments before using this method.".format(
                    type(self).__name__
                )
            )

        return self._return_result(prediction, return_type, comparison_vectors)

    def prob(self, comparison_vectors, return_type='series'):
        """Compute the probabilities for each record pair.

        For each pair of records, estimate the probability of being a match.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The dataframe with comparison vectors.
        return_type : 'series' or 'array'
            Return a pandas series or numpy array. Default 'series'.

        Returns
        -------
        pandas.Series or numpy.ndarray
            The probability of being a match for each record pair.

        """

        probs = self.classifier.predict_proba(comparison_vectors.as_matrix())

        if return_type == 'series':
            return pandas.Series(probs[:, 0], index=comparison_vectors.index)
        elif return_type == 'array':
            return probs[:, 0]
        else:
            raise ValueError(
                "return_type {} unknown. Choose 'index', 'series' or "
                "'array'".format(return_type))

    def _return_result(
        self, result, return_type='index', comparison_vectors=None
    ):
        """Return different formatted classification results.

        """

        if type(result) != numpy.ndarray:
            raise ValueError("numpy.ndarray expected.")

        # return the pandas.MultiIndex
        if return_type == 'index':
            return comparison_vectors.index[result.astype(bool)]

        # return a pandas.Series
        elif return_type == 'series':
            return pandas.Series(
                result,
                index=comparison_vectors.index,
                name='classification')

        # return a numpy.ndarray
        elif return_type == 'array':
            return result

        # return_type not known
        else:
            raise ValueError(
                "return_type {} unknown. Choose 'index', 'series' or "
                "'array'".format(return_type))


class KMeansClassifier(Classifier):
    """KMeans classifier.

    The `K-means clusterings algorithm (wikipedia)
    <https://en.wikipedia.org/wiki/K-means_clustering>`_ partitions candidate
    record pairs into matches and non-matches. Each comparison vector belongs
    to the cluster with the nearest mean. The K-means algorithm does not need
    trainings data, but it needs two starting points (one for the matches and
    one for the non-matches). The K-means clustering problem is NP-hard.

    Note
    ----
    There are way better methods for linking records than the k-means
    clustering algorithm. However, this algorithm does not need trainings data
    and is useful to do an initial partition.

    """

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        self.classifier = cluster.KMeans(n_clusters=2, n_init=1)

    def learn(self, comparison_vectors, return_type='index'):
        """Train the K-means classifier.

        The K-means classifier is unsupervised and therefore does not need
        labels. The K-means classifier classifies the data into two sets of
        links and non- links. The starting point of the cluster centers are
        0.05 for the non-matches and 0.95 for the matches.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The dataframe with comparison vectors.
        return_type : 'index' (default), 'series', 'array'
            The format to return the classification result. The argument value
            'index' will return the pandas.MultiIndex of the matches. The
            argument value 'series' will return a pandas.Series with zeros
            (distinct) and ones (matches). The argument value 'array' will
            return a numpy.ndarray with zeros and ones.

        Returns
        -------
        pandas.MultiIndex, pandas.Series or numpy.ndarray
            The prediction (see also the argument 'return_type')

        """

        # Set the start point of the classifier.
        self.classifier.init = numpy.array([
            [0.05] * len(list(comparison_vectors)),
            [0.95] * len(list(comparison_vectors))
        ])

        # Fit and predict
        prediction = self.classifier.fit_predict(
            comparison_vectors.as_matrix())

        return self._return_result(prediction, return_type, comparison_vectors)

    def prob(self, *args, **kwargs):

        raise AttributeError(
            "It is not possible to compute "
            "probabilities for the KMeansClassfier")


# DeterministicClassifier = LogisticRegressionClassifier
class LogisticRegressionClassifier(Classifier):
    """Logistic Regression Classifier.

    This classifier is an application of the `logistic regression model
    (wikipedia) <https://en.wikipedia.org/wiki/Logistic_regression>`_. The
    classifier partitions candidate record pairs into matches and non-matches.

    Parameters
    ----------
    coefficients : list, numpy.array
        The coefficients of the logistic regression.
    intercept : float
        The interception value.

    Attributes
    ----------
    coefficients : numpy.array
        The coefficients of the logistic regression.
    intercept : float
        The interception value.

    """

    def __init__(self, coefficients=None, intercept=None):
        super(self.__class__, self).__init__()

        self.classifier = linear_model.LogisticRegression()

        self.coefficients = coefficients
        self.intercept = intercept

        self.classifier.classes_ = numpy.array([False, True])

    @property
    def coefficients(self):
        # Return the coefficients if available
        try:
            return self.classifier.coef_[0]
        except Exception:
            return None

    @property
    def intercept(self):

        try:
            return float(self.classifier.intercept_[0])
        except Exception:
            return None

    @coefficients.setter
    def coefficients(self, value):

        if value is not None:

            # Check if array if numpy array
            if type(value) is not numpy.ndarray:
                value = numpy.array(value)

            # print (numpy.array(value))
            self.classifier.coef_ = value.reshape((1, len(value)))

    @intercept.setter
    def intercept(self, value):

        if value is not None:

            # Check if array if numpy array
            if type(value) is not numpy.ndarray:
                value = numpy.array([value])

        self.classifier.intercept_ = value


class NaiveBayesClassifier(Classifier):
    """
    NaiveBayesClassifier(alpha=1.0)

    Naive Bayes Classifier.

    The `Naive Bayes classifier (wikipedia)
    <https://en.wikipedia.org/wiki/Naive_Bayes_classifier>`_ partitions
    candidate record pairs into matches and non-matches. The classifier is
    based on probabilistic principles. The Naive Bayes classification method
    is proven to be mathematical equivalent with the Fellegi and Sunter model.

    alpha : float
        Additive (Laplace/Lidstone) smoothing parameter (0 for no smoothing).

    """

    def __init__(self, alpha=1.0, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        self.classifier = naive_bayes.BernoulliNB(alpha=alpha, binarize=None)


class SVMClassifier(Classifier):
    """
    SVMClassifier()

    Support Vector Machines

    The `Support Vector Machine classifier (wikipedia)
    <https://en.wikipedia.org/wiki/Support_vector_machine>`_ partitions
    candidate record pairs into matches and non-matches. This implementation
    is a non-probabilistic binary linear classifier. Support vector machines
    are supervised learning models. Therefore, the SVM classifiers needs
    training-data.

    """

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        self.classifier = svm.LinearSVC()

    def prob(self, *args, **kwargs):

        raise AttributeError(
            "It is not possible to compute "
            "probabilities for the SVMClassfier")


class FellegiSunter(Classifier):
    """Fellegi and Sunter framework.

    Base class for probabilistic classification of records pairs with the
    Fellegi and Sunter (1969) framework.

    """

    def __init__(self, random_decision_rule=False):

        self.random_decision_rule = random_decision_rule

    @property
    def p(self):
        try:
            return self.algorithm._p
        except Exception:
            pass

    def _decision_rule(self, probabilities, threshold, random_decision_rule=False):

        if not self.random_decision_rule:
            return (probabilities >= threshold).astype(int)
        else:
            raise NotImplementedError(
                "Random decisions are not possible at the moment.")


class ECMClassifier(FellegiSunter):
    """Expectation/Conditional Maxisation vlassifier.

    [EXPERIMENTAL] Expectation/Conditional Maximisation algorithm used as
    classifier. This probabilistic record linkage algorithm is used in
    combination with Fellegi and Sunter model.

    """

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        self.algorithm = ECMEstimate()

    def learn(self, comparison_vectors, init='jaro', return_type='index'):
        """ Train the algorithm.

        Train the Expectation-Maximisation classifier. This method is well-
        known as the ECM-algorithm implementation in the context of record
        linkage.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The dataframe with comparison vectors.
        params_init : dict
            A dictionary with initial parameters of the ECM algorithm
            (optional).
        return_type : 'index' (default), 'series', 'array'
            The format to return the classification result. The argument value
            'index' will return the pandas.MultiIndex of the matches. The
            argument value 'series' will return a pandas.Series with zeros
            (distinct) and ones (matches). The argument value 'array' will
            return a numpy.ndarray with zeros and ones.

        Returns
        -------
        pandas.Series
            A pandas Series with the labels 1 (for the matches) and 0 (for the
            non-matches).

        """

        probs = self.algorithm.train(comparison_vectors.as_matrix())

        n_matches = int(self.algorithm.p * len(probs))
        self.p_threshold = numpy.sort(probs)[len(probs) - n_matches]

        prediction = self._decision_rule(probs, self.p_threshold)

        return self._return_result(prediction, return_type, comparison_vectors)

    def predict(self, comparison_vectors, return_type='index', *args, **kwargs):
        """Predict the class of reord pairs.

        Classify a set of record pairs based on their comparison vectors into
        matches, non-matches and possible matches. The classifier has to be
        trained to call this method.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The dataframe with comparison vectors.
        return_type : 'index' (default), 'series', 'array'
            The format to return the classification result. The argument value
            'index' will return the pandas.MultiIndex of the matches. The
            argument value 'series' will return a pandas.Series with zeros
            (distinct) and ones (matches). The argument value 'array' will
            return a numpy.ndarray with zeros and ones.

        Returns
        -------
        pandas.Series
            A pandas Series with the labels 1 (for the matches) and 0 (for the
            non-matches).

        Note
        ----
        Prediction is risky for this unsupervised learning method. Be aware
        that the sample from the population is valid.


        """

        enc_vectors = self.algorithm._transform_vectors(
            comparison_vectors.as_matrix())

        probs = self.algorithm._expectation(enc_vectors)

        prediction = self._decision_rule(probs, self.p_threshold)

        return self._return_result(prediction, return_type, comparison_vectors)

    def prob(self, comparison_vectors):
        """Compute the probabilities for each record pair.

        For each pair of records, estimate the probability of being a match.

        Parameters
        ----------
        comparison_vectors : pandas.DataFrame
            The dataframe with comparison vectors.
        return_type : 'series' or 'array'
            Return a pandas series or numpy array. Default 'series'.

        Returns
        -------
        pandas.Series or numpy.ndarray
            The probability of being a match for each record pair.

        """

        enc_vectors = self.algorithm._transform_vectors(
            comparison_vectors.as_matrix())

        return pandas.Series(
            self.algorithm._expectation(enc_vectors),
            index=comparison_vectors.index
        )
