import warnings
from simdeep.simdeep_analysis import SimDeep
from simdeep.extract_data import LoadData

from simdeep.coxph_from_r import coxph
from simdeep.coxph_from_r import c_index
from simdeep.coxph_from_r import c_index_multiple
from simdeep.coxph_from_r import NALogicalType

from sklearn.model_selection import KFold
# from sklearn.preprocessing import OneHotEncoder

from collections import Counter
from collections import defaultdict
from itertools import combinations

import numpy as np

from scipy.stats import gmean
from sklearn.metrics import adjusted_rand_score

from simdeep.config import PROJECT_NAME
from simdeep.config import PATH_RESULTS
from simdeep.config import NB_THREADS
from simdeep.config import NB_ITER
from simdeep.config import NB_FOLDS
from simdeep.config import CLASS_SELECTION
from simdeep.config import NB_CLUSTERS
from simdeep.config import NORMALIZATION
from simdeep.config import EPOCHS
from simdeep.config import NEW_DIM
from simdeep.config import NB_SELECTED_FEATURES
from simdeep.config import PVALUE_THRESHOLD
from simdeep.config import CLUSTER_METHOD
from simdeep.config import CLASSIFICATION_METHOD
from simdeep.config import TRAINING_TSV
from simdeep.config import SURVIVAL_TSV
from simdeep.config import PATH_DATA
from simdeep.config import SURVIVAL_FLAG
from simdeep.config import NODES_SELECTION
from simdeep.config import CINDEX_THRESHOLD
from simdeep.config import USE_AUTOENCODERS
from simdeep.config import FEATURE_SURV_ANALYSIS
from simdeep.config import CLUSTERING_OMICS
from simdeep.config import USE_R_PACKAGES_FOR_SURVIVAL

# Parameter for autoencoder
from simdeep.config import LEVEL_DIMS_IN
from simdeep.config import LEVEL_DIMS_OUT
from simdeep.config import LOSS
from simdeep.config import OPTIMIZER
from simdeep.config import ACT_REG
from simdeep.config import W_REG
from simdeep.config import DROPOUT
from simdeep.config import ACTIVATION
from simdeep.config import PATH_TO_SAVE_MODEL
from simdeep.config import DATA_SPLIT
from simdeep.config import MODEL_THRES

from multiprocessing import Pool

from simdeep.deepmodel_base import DeepBase

import simplejson

from distutils.dir_util import mkpath

from os.path import isdir
from os import mkdir

from glob import glob

import gc

from time import time

from numpy import hstack
from numpy import vstack

import pandas as pd

from simdeep.survival_utils import \
    _process_parallel_feature_importance_per_cluster
from simdeep.survival_utils import \
    _process_parallel_survival_feature_importance_per_cluster



class SimDeepBoosting():
    """
    Instanciate a new DeepProg Boosting instance.
    The default parameters are defined in the config.py file

    Parameters:
            :nb_it: Number of models to construct
            :do_KM_plot: Plot Kaplan-Meier (default: True)
            :distribute: Distribute DeepProg using ray (default:  False)
            :nb_threads: Number of python threads to use to compute parallel Cox-PH
            :class_selection: Consensus score to agglomerate DeepProg Instance {'mean', 'max', 'weighted_mean', 'weighted_max'} (default: 'mean')
            :model_thres: Cox-PH p-value threshold to reject a model for DeepProg Boosting module
            :verbose: Verobosity (Default: True)
            :seed: Seed defining the  random split of the training dataset (Default: None).
            :project_name: Project name used to save files
            :use_autoencoders: Use autoencoder steps to embed the data (default: True)
            :feature_surv_analysis: Use individual survival feature detection to filter out features (default: True)
            :split_n_fold: For each instance, the original dataset is split in folds and one fold is left
            :path_results: Path to create a result folder
            :nb_clusters: Number of clusters to use
            :epochs: Number of epochs
            :normalization: Normalisation procedure to use. See config.py file for details
            :nb_selected_features: Number of top features selected for classification
            :cluster_method: Clustering method. possible choice: ['mixture', 'kmeans', 'coxPH'] or class instance having fit and fit_proba attributes
            :pvalue_thres: Threshold for survival significance to set a node as valid
            :classification_method: Possible choice: {'ALL_FEATURES', 'SURVIVAL_FEATURES'} (default: 'ALL_FEATURES')
            :new_dim: Size of the new embedding
            :training_tsv: Input matrix files
            :survival_tsv: Input surival file
            :survival_flag: Survival flag to use
            :path_data: Path of the input file
            :level_dims_in: Autoencoder node layers before the middle layer (default: [])
            :level_dims_out: Autoencoder node layers after the middle layer (default: [])
            :loss: Loss function to minimize (default: 'binary_crossentropy')
            :optimizer: Optimizer (default: adam)
            :act_reg: L2 Regularization constant on the node activity (default: False)
            :w_reg: L1 Regularization constant on the weight (default: False)
            :dropout: Percentage of edges being dropout at each training iteration (None for no dropout) (default: 0.5)
            :data_split: Fraction of the dataset to be used as test set when building the autoencoder (default: None)
            :node_selection: possible choice: {'Cox-PH', 'C-index'} (default: Cox-PH)
            :cindex_thres: Valid if 'c-index' is chosen (default: 0.65)
            :activation: Activation function (default: 'tanh')
            :clustering_omics: Which omics to use for clustering. If empty, then all the available omics will be used (default [] => all)
            :path_to_save_model: path to save the model
            :metadata_usage: Meta data usage with survival models (if metadata_tsv provided as argument to the dataset). Possible choice are [None, False, 'labels', 'new-features', 'all', True] (True is the same as all)
            :subset_training_with_meta: Use a metadata key-value dict {meta_key:value} to subset the training sets
            :alternative_embedding: alternative external embedding to use instead of building autoencoders (default None)
            :kwargs_alternative_embedding: parameters for external embedding fitting
    """
    def __init__(self,
                 nb_it=NB_ITER,
                 do_KM_plot=True,
                 distribute=False,
                 nb_threads=NB_THREADS,
                 class_selection=CLASS_SELECTION,
                 model_thres=MODEL_THRES,
                 verbose=True,
                 seed=None,
                 project_name='{0}_boosting'.format(PROJECT_NAME),
                 use_autoencoders=USE_AUTOENCODERS,
                 feature_surv_analysis=FEATURE_SURV_ANALYSIS,
                 split_n_fold=NB_FOLDS,
                 path_results=PATH_RESULTS,
                 nb_clusters=NB_CLUSTERS,
                 epochs=EPOCHS,
                 normalization=NORMALIZATION,
                 nb_selected_features=NB_SELECTED_FEATURES,
                 cluster_method=CLUSTER_METHOD,
                 pvalue_thres=PVALUE_THRESHOLD,
                 classification_method=CLASSIFICATION_METHOD,
                 new_dim=NEW_DIM,
                 training_tsv=TRAINING_TSV,
                 metadata_usage=None,
                 survival_tsv=SURVIVAL_TSV,
                 metadata_tsv=None,
                 subset_training_with_meta={},
                 survival_flag=SURVIVAL_FLAG,
                 path_data=PATH_DATA,
                 level_dims_in=LEVEL_DIMS_IN,
                 level_dims_out=LEVEL_DIMS_OUT,
                 loss=LOSS,
                 optimizer=OPTIMIZER,
                 act_reg=ACT_REG,
                 w_reg=W_REG,
                 dropout=DROPOUT,
                 data_split=DATA_SPLIT,
                 node_selection=NODES_SELECTION,
                 cindex_thres=CINDEX_THRESHOLD,
                 activation=ACTIVATION,
                 clustering_omics=CLUSTERING_OMICS,
                 path_to_save_model=PATH_TO_SAVE_MODEL,
                 feature_selection_usage='individual',
                 use_r_packages=USE_R_PACKAGES_FOR_SURVIVAL,
                 alternative_embedding=None,
                 kwargs_alternative_embedding={},
                 **additional_dataset_args):
        """ """
        assert(class_selection in ['max', 'mean', 'weighted_mean', 'weighted_max'])
        self.class_selection = class_selection

        self._instance_weights = None
        self.distribute = distribute
        self.model_thres = model_thres
        self.models = []
        self.verbose = verbose
        self.nb_threads = nb_threads
        self.do_KM_plot = do_KM_plot
        self.project_name = project_name
        self._project_name = project_name
        self.path_results = '{0}/{1}'.format(path_results, project_name)
        self.training_tsv = training_tsv
        self.survival_tsv = survival_tsv
        self.survival_flag = survival_flag
        self.path_data = path_data
        self.dataset = None
        self.cindex_thres = cindex_thres
        self.node_selection = node_selection
        self.clustering_omics = clustering_omics
        self.metadata_tsv = metadata_tsv
        self.metadata_usage = metadata_usage
        self.feature_selection_usage = feature_selection_usage
        self.subset_training_with_meta = subset_training_with_meta
        self.use_r_packages = use_r_packages

        self.metadata_mat_full = None

        self.cluster_method = cluster_method
        self.use_autoencoders = use_autoencoders
        self.feature_surv_analysis = feature_surv_analysis

        if self.feature_selection_usage is None:
            self.feature_surv_analysis = False

        self.encoder_for_kde_plot_dict = {}
        self.kde_survival_node_ids = {}
        self.kde_train_matrices = {}

        if not isdir(self.path_results):
            try:
                mkpath(self.path_results)
            except Exception:
                print('cannot find or create the current result path: {0}' \
                      '\n consider changing it as option' \
                      .format(self.path_results))

        self.test_tsv_dict = None
        self.test_survival_file = None
        self.test_normalization = None

        self.test_labels = None
        self.test_labels_proba = None

        self.cv_labels = None
        self.cv_labels_proba = None
        self.full_labels = None
        self.full_labels_dicts = None
        self.full_labels_proba = None
        self.survival_full = None
        self.sample_ids_full = None
        self.feature_scores_per_cluster = {}
        self.survival_feature_scores_per_cluster = {}

        self._pretrained_fit = False

        self.log = {}

        self.alternative_embedding = alternative_embedding
        self.kwargs_alternative_embedding = kwargs_alternative_embedding

        ######## deepprog instance parameters ########
        self.nb_clusters = nb_clusters
        self.normalization = normalization
        self.epochs = epochs
        self.new_dim = new_dim
        self.nb_selected_features = nb_selected_features
        self.pvalue_thres = pvalue_thres
        self.cluster_method = cluster_method
        self.cindex_test_folds = []
        self.classification_method = classification_method
        ##############################################

        self.test_fname_key = ''
        self.matrix_with_cv_array = None

        autoencoder_parameters = {
            'epochs': self.epochs,
            'new_dim': self.new_dim,
            'level_dims_in': level_dims_in,
            'level_dims_out': level_dims_out,
            'loss': loss,
            'optimizer': optimizer,
            'act_reg': act_reg,
            'w_reg': w_reg,
            'dropout': dropout,
            'data_split': data_split,
            'activation': activation,
            'path_to_save_model': path_to_save_model,
        }

        self.datasets = []
        self.seed = seed

        self.log['parameters'] = {}

        for arg in self.__dict__:
            self.log['parameters'][arg] = str(self.__dict__[arg])

        self.log['seed'] = seed
        self.log['parameters'].update(autoencoder_parameters)

        self.log['nb_it'] = nb_it
        self.log['normalization'] = normalization
        self.log['nb clusters'] = nb_clusters
        self.log['success'] = False
        self.log['survival_tsv'] = self.survival_tsv
        self.log['metadata_tsv'] = self.metadata_tsv
        self.log['subset_training_with_meta'] = self.subset_training_with_meta
        self.log['training_tsv'] = self.training_tsv
        self.log['path_data'] = self.path_data

        additional_dataset_args['survival_tsv'] = self.survival_tsv
        additional_dataset_args['metadata_tsv'] = self.metadata_tsv
        additional_dataset_args['subset_training_with_meta'] = self.subset_training_with_meta
        additional_dataset_args['training_tsv'] = self.training_tsv
        additional_dataset_args['path_data'] = self.path_data
        additional_dataset_args['survival_flag'] = self.survival_flag

        if 'fill_unkown_feature_with_0' in additional_dataset_args:
            self.log['fill_unkown_feature_with_0'] = additional_dataset_args[
                'fill_unkown_feature_with_0']

        self.ray = None

        self._init_datasets(nb_it, split_n_fold,
                            autoencoder_parameters,
                            **additional_dataset_args)

    def _init_datasets(self, nb_it, split_n_fold,
                       autoencoder_parameters,
                       **additional_dataset_args):
        """
        """
        if self.seed:
            np.random.seed(self.seed)
        else:
            self.seed = np.random.randint(0, 10000000)

        max_seed = 1000
        min_seed = 0

        if self.seed > max_seed:
            min_seed = self.seed - max_seed
            max_seed = self.seed

        np.random.seed(self.seed)
        random_states = np.random.randint(min_seed, max_seed, nb_it)

        self.split_n_fold = split_n_fold

        for it in range(nb_it):
            if self.split_n_fold:
                split = KFold(n_splits=split_n_fold,
                              shuffle=True, random_state=random_states[it])
            else:
                split = None

            autoencoder_parameters['seed'] = random_states[it]

            dataset = LoadData(cross_validation_instance=split,
                               verbose=False,
                               normalization=self.normalization,
                               _autoencoder_parameters=autoencoder_parameters.copy(),
                               **additional_dataset_args)

            self.datasets.append(dataset)

    def __del__(self):
        """
        """
        for model in self.models:
            del model

        try:
            gc.collect()
        except Exception as e:
            print('Warning: Exception {0} from garbage collector. continuing... '.format(
                e))

    def _from_models(self, fname, *args, **kwargs):
        """
        """
        if self.distribute:
            return self.ray.get([getattr(model, fname).remote(*args, **kwargs)
                                 for model in self.models])
        else:
            return [getattr(model, fname)(*args, **kwargs)
                    for model in self.models]


    def _from_model(self, model, fname, *args, **kwargs):
        """
        """
        if self.distribute:
            return self.ray.get(getattr(model, fname).remote(
                *args, **kwargs))
        else:
            return getattr(model, fname)(*args, **kwargs)

    def _from_model_attr(self, model, atname):
        """
        """
        if self.distribute:
            return self.ray.get(model._get_attibute.remote(atname))
        else:
            return model._get_attibute(atname)

    def _from_models_attr(self, atname):
        """
        """
        if self.distribute:
            return self.ray.get([model._get_attibute.remote(atname)
                                 for model in self.models])
        else:
            return [model._get_attibute(atname) for model in self.models]

    def _from_model_dataset(self, model, atname):
        """
        """
        if self.distribute:
            return self.ray.get(model._get_from_dataset.remote(atname))
        else:
            return model._get_from_dataset(atname)


    def _do_class_selection(self, inputs, **kwargs):
        """
        """
        if self.class_selection == 'max':
            return  _highest_proba(inputs)
        elif self.class_selection == 'mean':
            return _mean_proba(inputs)
        elif self.class_selection == 'weighted_mean':
            return _weighted_mean(inputs, **kwargs)
        elif self.class_selection == 'weighted_max':
            return _weighted_max(inputs, **kwargs)

    def partial_fit(self, debug=False):
        """
        """
        self._fit(debug=debug)

    def fit_on_pretrained_label_file(
            self,
            labels_files=[],
            labels_files_folder="",
            file_name_regex="*.tsv",
            verbose=False,
            debug=False,
    ):
        """
        fit a deepprog simdeep models without training autoencoders but using isntead  ID->labels files (one for each model instance)
        """
        assert(isinstance((labels_files), list))

        if not labels_files and not labels_files_folder:
            raise Exception(
                '## Error with fit_on_pretrained_label_file: ' \
                ' either labels_files or labels_files_folder should be non empty')

        if not labels_files:
            labels_files = glob('{0}/{1}'.format(labels_files_folder,
                                                 file_name_regex))

        if not labels_files:
            raise Exception('## Error: labels_files empty')

        self.fit(
            verbose=verbose,
            debug=debug,
            pretrained_labels_files=labels_files)

    def fit(self, debug=False, verbose=False, pretrained_labels_files=[]):
        """
        if pretrained_labels_files, is given, the models are constructed using these labels
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if pretrained_labels_files:
                self._pretrained_fit = True
            else:
                self._pretrained_fit = False

            if self.distribute:
                self._fit_distributed(
                    pretrained_labels_files=pretrained_labels_files)
            else:
                self._fit(
                    debug=debug,
                    verbose=verbose,
                    pretrained_labels_files=pretrained_labels_files)

    def _fit_distributed(self, pretrained_labels_files=[]):
        """ """
        print('fit models...')
        start_time = time()

        from simdeep.simdeep_distributed import SimDeepDistributed
        import ray
        assert(ray.is_initialized())
        self.ray = ray

        try:
            self.models = [SimDeepDistributed.remote(
                nb_clusters=self.nb_clusters,
                nb_selected_features=self.nb_selected_features,
                pvalue_thres=self.pvalue_thres,
                dataset=dataset,
                load_existing_models=False,
                verbose=dataset.verbose,
                _isboosting=True,
                do_KM_plot=False,
                cluster_method=self.cluster_method,
                clustering_omics=self.clustering_omics,
                use_autoencoders=self.use_autoencoders,
                use_r_packages=self.use_r_packages,
                feature_surv_analysis=self.feature_surv_analysis,
                path_results=self.path_results,
                project_name=self.project_name,
                classification_method=self.classification_method,
                cindex_thres=self.cindex_thres,
                alternative_embedding=self.alternative_embedding,
                kwargs_alternative_embedding=self.kwargs_alternative_embedding,
                node_selection=self.node_selection,
                metadata_usage=self.metadata_usage,
                feature_selection_usage=self.feature_selection_usage,
                deep_model_additional_args=dataset._autoencoder_parameters)
                           for dataset in self.datasets]

            if pretrained_labels_files:
                nb_files = len(pretrained_labels_files)
                if nb_files < len(self.models):
                    print(
                        'Number of pretrained label files' \
                        ' inferior to number of instance{0}'.format(
                            nb_files))
                    self.models = self.models[:nb_files]

                results = ray.get([
                    model._partial_fit_model_with_pretrained_pool.remote(
                        labels)
                    for model, labels in zip(self.models,
                                             pretrained_labels_files)])
            else:
                results = ray.get([
                    model._partial_fit_model_pool.remote()
                    for model in self.models])

            print("Results: {0}".format(results))
            self.models = [model for model, is_fitted in zip(self.models, results) if is_fitted]

            nb_models = len(self.models)

            print('{0} models fitted'.format(nb_models))
            self.log['nb. models fitted'] = nb_models

            assert(nb_models)

        except Exception as e:
            self.log['failure'] = str(e)
            raise e

        else:
            self.log['success'] = True
            self.log['fitting time (s)'] = time() - start_time

            if self.class_selection in ['weighted_mean', 'weighted_max']:
                self.collect_cindex_for_test_fold()

    def _fit(self, debug=False, verbose=False, pretrained_labels_files=[]):
        """
        if pretrained_labels_files, is given, the models are constructed using these labels
        """
        print('fit models...')
        start_time = time()

        try:
            self.models = [SimDeep(
                nb_clusters=self.nb_clusters,
                nb_selected_features=self.nb_selected_features,
                pvalue_thres=self.pvalue_thres,
                dataset=dataset,
                load_existing_models=False,
                verbose=dataset.verbose,
                _isboosting=True,
                do_KM_plot=False,
                cluster_method=self.cluster_method,
                use_autoencoders=self.use_autoencoders,
                feature_surv_analysis=self.feature_surv_analysis,
                path_results=self.path_results,
                project_name=self.project_name,
                cindex_thres=self.cindex_thres,
                node_selection=self.node_selection,
                metadata_usage=self.metadata_usage,
                use_r_packages=self.use_r_packages,
                feature_selection_usage=self.feature_selection_usage,
                alternative_embedding=self.alternative_embedding,
                kwargs_alternative_embedding=self.kwargs_alternative_embedding,
                classification_method=self.classification_method,
                deep_model_additional_args=dataset._autoencoder_parameters)
                           for dataset in self.datasets]

            if pretrained_labels_files:
                nb_files = len(pretrained_labels_files)
                if nb_files < len(self.models):
                    print(
                        'Number of pretrained label files' \
                        ' inferior to number of instance{0}'.format(
                        nb_files))
                    self.models = self.models[:nb_files]

                results = [
                    model._partial_fit_model_with_pretrained_pool(labels)
                    for model, labels in zip(self.models, pretrained_labels_files)]
            else:
                results = [model._partial_fit_model_pool() for model in self.models]

            print("Results: {0}".format(results))
            self.models = [model for model, is_fitted in zip(self.models, results) if is_fitted]

            nb_models = len(self.models)

            print('{0} models fitted'.format(nb_models))
            self.log['nb. models fitted'] = nb_models

            assert(nb_models)

        except Exception as e:
            self.log['failure'] = str(e)
            raise e

        else:
            self.log['success'] = True
            self.log['fitting time (s)'] = time() - start_time

            if self.class_selection in ['weighted_mean', 'weighted_max']:
                self.collect_cindex_for_test_fold()

    def predict_labels_on_test_dataset(self):
        """
        """
        print('predict labels on test datasets...')
        test_labels_proba = np.asarray(self._from_models_attr(
            'test_labels_proba'))

        res = self._do_class_selection(
            test_labels_proba,
            weights=self.cindex_test_folds)
        self.test_labels, self.test_labels_proba = res

        print('#### Report of assigned cluster for TEST dataset {0}:'.format(
            self.test_fname_key))
        for key, value in sorted(Counter(self.test_labels).items()):
            print('class: {0}, number of samples :{1}'.format(key, value))

        nbdays, isdead = self._from_model_dataset(self.models[0], "survival_test").T.tolist()

        if np.isnan(nbdays).all():
            return np.nan, np.nan

        pvalue, pvalue_proba, pvalue_cat = self._compute_test_coxph(
            'KM_plot_boosting_test',
            nbdays, isdead,
            self.test_labels, self.test_labels_proba,
            self.project_name)

        self.log['pvalue test {0}'.format(self.test_fname_key)] = pvalue
        self.log['pvalue proba test {0}'.format(self.test_fname_key)] = pvalue_proba
        self.log['pvalue cat test {0}'.format(self.test_fname_key)] = pvalue_cat

        sample_id_test = self._from_model_dataset(self.models[0], 'sample_ids_test')

        self._from_model(self.models[0], '_write_labels',
                         sample_id_test,
                         self.test_labels,
                         '{0}_test_labels'.format(self.project_name),
                         labels_proba=self.test_labels_proba.T[0],
                         nbdays=nbdays, isdead=isdead)

        return pvalue, pvalue_proba

    def compute_pvalue_for_merged_test_fold(self):
        """
        """
        print('predict labels on test fold datasets...')

        isdead_cv, nbdays_cv, labels_cv = [], [], []

        if self.metadata_usage in ['all', 'labels'] and \
           self.metadata_tsv:
            metadata_mat = []
        else:
            metadata_mat = None

        for model in self.models:
            survival_cv = self._from_model_dataset(model, 'survival_cv')

            if survival_cv is None:
                print('No survival dataset for CV fold returning')
                return

            nbdays, isdead = survival_cv.T.tolist()
            nbdays_cv += nbdays
            isdead_cv += isdead
            labels_cv += self._from_model_attr(model, "cv_labels").tolist()

            if metadata_mat is not None:
                meta2 = self._from_model_dataset(model, 'metadata_mat_cv')

                if not len(metadata_mat):
                    metadata_mat = meta2
                else:
                    metadata_mat = pd.concat([metadata_mat, meta2])

                metadata_mat = metadata_mat.fillna(0)

        pvalue = coxph(
            labels_cv, isdead_cv, nbdays_cv,
            isfactor=False,
            do_KM_plot=self.do_KM_plot,
            png_path=self.path_results,
            fig_name='cv_analysis', seed=self.seed,
            use_r_packages=self.use_r_packages,
            metadata_mat=metadata_mat
        )

        print('Pvalue for test fold concatenated: {0}'.format(pvalue))
        self.log['pvalue cv test'] = pvalue

        return pvalue

    def collect_pvalue_on_test_fold(self):
        """
        """
        print('predict labels on test fold datasets...')
        pvalues, pvalues_proba = [], []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            for model in self.models:
                pvalues.append(self._from_model_attr(model, 'cp_pvalue'))
                pvalues_proba.append(self._from_model_attr(model, 'cp_pvalue_proba'))

            pvalue_gmean, pvalue_proba_gmean = gmean(pvalues), gmean(pvalues_proba)

            if self.verbose:
                print('geo mean pvalues: {0} geo mean pvalues probas: {1}'.format(
                    pvalue_gmean, pvalue_proba_gmean))

            self.log['pvalue geo mean test fold'] = pvalue_gmean
            self.log['pvalue proba geo mean test fold'] = pvalue_proba_gmean

        return pvalues, pvalues_proba

    def collect_pvalue_on_training_dataset(self):
        """
        """
        print('predict labels on training datasets...')
        pvalues, pvalues_proba = [], []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            for model in self.models:
                pvalues.append(self._from_model_attr(model, 'train_pvalue'))
                pvalues_proba.append(self._from_model_attr(model, 'train_pvalue_proba'))

            pvalue_gmean, pvalue_proba_gmean = gmean(pvalues), gmean(pvalues_proba)

            if self.verbose:
                print('training geo mean pvalues: {0} geo mean pvalues probas: {1}'.format(
                    pvalue_gmean, pvalue_proba_gmean))

            self.log['pvalue geo mean train'] = pvalue_gmean
            self.log['pvalue proba geo mean train'] = pvalue_proba_gmean

        return pvalues, pvalues_proba

    def collect_pvalue_on_test_dataset(self):
        """
        """
        print('collect pvalues on test datasets...')

        pvalues, pvalues_proba = [], []

        for model in self.models:
            pvalues.append(self._from_model_attr(model, 'test_pvalue'))
            pvalues_proba.append(self._from_model_attr(model, 'test_pvalue_proba'))

        pvalue_gmean, pvalue_proba_gmean = gmean(pvalues), gmean(pvalues_proba)

        if self.verbose:
            print('test geo mean pvalues: {0} geo mean pvalues probas: {1}'.format(
                pvalue_gmean, pvalue_proba_gmean))

        self.log['pvalue geo mean test {0}'.format(self.test_fname_key)] = pvalue_gmean
        self.log['pvalue proba geo mean test {0}'.format(
            self.test_fname_key)] = pvalue_proba_gmean

        return pvalues, pvalues_proba

    def collect_pvalue_on_full_dataset(self):
        """
        """
        print('collect pvalues on full datasets...')

        pvalues, pvalues_proba = zip(*self._from_models('_get_pvalues_and_pvalues_proba'))
        pvalue_gmean, pvalue_proba_gmean = gmean(pvalues), gmean(pvalues_proba)

        if self.verbose:
            print('full geo mean pvalues: {0} geo mean pvalues probas: {1}'.format(
                pvalue_gmean, pvalue_proba_gmean))

        self.log['pvalue geo mean full'] = pvalue_gmean
        self.log['pvalue proba geo mean full'] = pvalue_proba_gmean

        return pvalues, pvalues_proba

    def collect_number_of_features_per_omic(self):
        """
        """
        counter = defaultdict(list)
        self.log['number of features per omics'] = {}

        for model in self.models:
            valid_node_ids_array = self._from_model_attr(model, 'valid_node_ids_array')
            for key in valid_node_ids_array:
                counter[key].append(len(valid_node_ids_array[key]))

        if self.verbose:
            for key in counter:
                print('key:{0} mean: {1} std: {2}'.format(
                    key, np.mean(counter[key]), np.std(counter[key])))

                self.log['number of features per omics'][key] = float(np.mean(counter[key]))

        return counter


    def collect_cindex_for_test_fold(self):
        """
        """
        self.cindex_test_folds = []

        self._from_models('predict_labels_on_test_fold')
        try:
            cindexes = self._from_models('compute_c_indexes_for_test_fold_dataset')
        except Exception as e:
            print('Exception while computing the c-index for test fold: {0}'.format(e))
            return np.nan

        for cindex in cindexes:
            if np.isnan(cindex) or isinstance(cindex, NALogicalType):
                cindex = np.nan

            self.cindex_test_folds.append(cindex)

        if self.verbose:
            mean, std = np.nanmean(self.cindex_test_folds), np.nanstd(self.cindex_test_folds)
            print('C-index results for test fold: mean {0} std {1}'.format(mean, std))

        self.log['c-indexes test fold (mean)'] = np.mean(mean)

        return self.cindex_test_folds


    def collect_cindex_for_full_dataset(self):
        """
        """
        self._from_models('predict_labels_on_test_fold')

        try:
            cindexes_list = self._from_models('compute_c_indexes_for_full_dataset')
        except Exception as e:
            print('Exception while computing the c-index for full dataset: {0}'.format(e))
            return np.nan

        if self.verbose:
            print('c-index results for full dataset: mean {0} std {1}'.format(
                np.mean(cindexes_list), np.std(cindexes_list)))

        self.log['c-indexes full (mean)'] = np.mean(cindexes_list)

        return cindexes_list


    def collect_cindex_for_training_dataset(self):
        """
        """
        try:
            cindexes_list = self._from_models('compute_c_indexes_for_training_dataset')
        except Exception as e:
            print('Exception while computing the c-index for training dataset: {0}'.format(e))
            self.log['c-indexes train (mean)'] = np.nan
            return np.nan

        if self.verbose:
            print('C-index results for training dataset: mean {0} std {1}'.format(
                np.mean(cindexes_list), np.std(cindexes_list)))

        self.log['c-indexes train (mean)'] = np.mean(cindexes_list)

        return cindexes_list

    def collect_cindex_for_test_dataset(self):
        """
        """
        try:
            cindexes_list = self._from_models('compute_c_indexes_for_test_dataset')
        except Exception as e:
            print('Exception while computing the c-index for test dataset: {0}'.format(e))
            self.log['C-index test {0}'.format(self.test_fname_key)] = np.nan
            return np.nan

        if self.verbose:
            print('C-index results for test: mean {0} std {1}'.format(
                np.mean(cindexes_list), np.std(cindexes_list)))

        self.log['C-index test {0}'.format(self.test_fname_key)] = np.mean(cindexes_list)

        return cindexes_list

    def predict_labels_on_full_dataset(self):
        """
        """
        print('predict labels on full datasets...')
        self._get_probas_for_full_models()
        self._reorder_survival_full_and_metadata()

        print('#### Report of assigned cluster for the full training dataset:')
        for key, value in sorted(Counter(self.full_labels).items()):
            print('class: {0}, number of samples :{1}'.format(key, value))

        nbdays, isdead = self.survival_full.T.tolist()


        pvalue, pvalue_proba, pvalue_cat = self._compute_test_coxph(
            'KM_plot_boosting_full',
            nbdays, isdead,
            self.full_labels, self.full_labels_proba,
            self._project_name)

        self.log['pvalue full'] = pvalue
        self.log['pvalue proba full'] = pvalue_proba
        self.log['pvalue cat full'] = pvalue_cat

        self._from_model(self.models[0], '_write_labels',
                          self.sample_ids_full,
                          self.full_labels,
                          '{0}_full_labels'.format(self._project_name),
                          labels_proba=self.full_labels_proba.T[0],
                          nbdays=nbdays, isdead=isdead)

        return pvalue, pvalue_proba

    def compute_clusters_consistency_for_full_labels(self):
        """
        """
        scores = []

        for model_1, model_2 in combinations(self.models, 2):
            full_labels_1_old = self._from_model_attr(model_1, 'full_labels')
            full_labels_2_old = self._from_model_attr(model_2, 'full_labels')

            full_ids_1 = self._from_model_dataset(model_1, 'sample_ids_full')
            full_ids_2 = self._from_model_dataset(model_2, 'sample_ids_full')

            full_labels_1 = _reorder_labels(full_labels_1_old, full_ids_1)
            full_labels_2 = _reorder_labels(full_labels_2_old, full_ids_2)

            scores.append(adjusted_rand_score(full_labels_1,
                                              full_labels_2))
        print('Adj. Rand scores for full label: mean: {0} std: {1}'.format(
            np.mean(scores), np.std(scores)))

        self.log['Adj. Rand scores'] = np.mean(scores)

        return scores

    def compute_clusters_consistency_for_test_labels(self):
        """
        """
        scores = []

        for model_1, model_2 in combinations(self.models, 2):
            scores.append(adjusted_rand_score(
                self._from_model_attr(model_1, 'test_labels'),
                self._from_model_attr(model_2, 'test_labels'),
            ))
        print('Adj. Rand scores for test label: mean: {0} std: {1}'.format(
            np.mean(scores), np.std(scores)))

        self.log['Adj. Rand scores test {0}'.format(self.test_fname_key)] = np.mean(scores)

        return scores

    def _reorder_survival_full_and_metadata(self):
        """
        """
        survival_old = self._from_model_dataset(self.models[0], 'survival_full')
        sample_ids = self._from_model_dataset(self.models[0], 'sample_ids_full')

        surv_dict = {sample: surv for sample, surv in zip(sample_ids, survival_old)}

        self.survival_full = np.asarray([np.asarray(surv_dict[sample])[0]
                                         for sample in self.sample_ids_full])

        metadata = self._from_model_dataset(self.models[0], 'metadata_mat_full')

        if metadata is not None:

            index_dict = {sample: pos for pos, sample in enumerate(sample_ids)}
            index = np.asarray([index_dict[sample] for sample in self.sample_ids_full])
            self.metadata_mat_full = metadata.T[index].T

    def _reorder_matrix_full(self):
        """
        """
        sample_ids = self._from_model_dataset(self.models[0], 'sample_ids_full')
        index_dict = {sample: ids for ids, sample in enumerate(sample_ids)}
        index = [index_dict[sample] for sample in self.sample_ids_full]

        self.matrix_with_cv_array = self._from_model_dataset(
            self.models[0], 'matrix_array').copy()
        matrix_cv_unormalized_array = self._from_model_dataset(
            self.models[0],
            'matrix_cv_unormalized_array')

        for key in self.matrix_with_cv_array:
            if len(matrix_cv_unormalized_array):
                self.matrix_with_cv_array[key] = vstack(
                    [self.matrix_with_cv_array[key],
                     matrix_cv_unormalized_array[key]])

            self.matrix_with_cv_array[key] = self.matrix_with_cv_array[key][index]

    def _get_probas_for_full_models(self):
        """
        """
        proba_dict = defaultdict(list)

        for sample_proba in self._from_models('_get_probas_for_full_model'):
            sample_set = set()

            for sample, proba in sample_proba:
                if sample in sample_set:
                    continue

                proba_dict[sample].append([np.nan_to_num(proba).tolist()])
                sample_set.add(sample)

        labels, probas = self._do_class_selection(hstack(list(proba_dict.values())),
                                                 weights=self.cindex_test_folds)

        self.full_labels = np.asarray(labels)
        self.full_labels_proba = probas

        self.sample_ids_full = list(proba_dict.keys())

    def _compute_test_coxph(self, fname_base, nbdays,
                            isdead, labels, labels_proba,
                            project_name, metadata_mat=None):
        """ """
        pvalue = coxph(
            labels, isdead, nbdays,
            isfactor=False,
            do_KM_plot=self.do_KM_plot,
            png_path=self.path_results,
            fig_name='{0}_{1}'.format(project_name, fname_base),
            use_r_packages=self.use_r_packages,
            metadata_mat=metadata_mat,
            seed=self.seed)

        if self.verbose:
            print('Cox-PH p-value (Log-Rank) for inferred labels: {0}'.format(pvalue))

        pvalue_proba = coxph(
            labels_proba.T[0],
            isdead, nbdays,
            isfactor=False,
            use_r_packages=self.use_r_packages,
            metadata_mat=metadata_mat,
            seed=self.seed)

        if self.verbose:
            print('Cox-PH proba p-value (Log-Rank) for inferred labels: {0}'.format(pvalue_proba))

        labels_categorical = self._labels_proba_to_labels(labels_proba)

        pvalue_cat = coxph(
            labels_categorical, isdead, nbdays,
            isfactor=False,
            do_KM_plot=self.do_KM_plot,
            png_path=self.path_results,
            use_r_packages=self.use_r_packages,
            fig_name='{0}_proba_{1}'.format(project_name, fname_base),
            metadata_mat=metadata_mat,
            seed=self.seed)

        if self.verbose:
            print('Cox-PH categorical p-value (Log-Rank) for inferred labels: {0}'.format(
                pvalue_cat))

        return pvalue, pvalue_proba, pvalue_cat

    def _labels_proba_to_labels(self, labels_proba):
        """
        """
        probas = labels_proba.T[0]
        labels = np.zeros(len(probas))
        nb_clusters = labels_proba.shape[1]

        for cluster in range(nb_clusters):
            percentile = 100 * (1.0 - 1.0 / (cluster + 1.0))
            value = np.percentile(probas, percentile)
            labels[probas >= value] = nb_clusters - cluster

        return labels

    def compute_c_indexes_for_test_dataset(self):
        """
        return c-index using labels as predicat
        """
        days_full, dead_full = np.asarray(self.survival_full).T
        days_test, dead_test = self._from_model_dataset(self.models[0], 'survival_test').T

        if np.isnan(days_test).all():
            print("Cannot compute C-index for test dataset. Need test survival file")
            return

        labels_test_categorical = self._labels_proba_to_labels(self.test_labels_proba)

        if isinstance(days_test, np.matrix):
            days_test = np.asarray(days_test)[0]
            dead_test = np.asarray(dead_test)[0]

        cindex = c_index(self.full_labels, dead_full, days_full,
                         self.test_labels, dead_test, days_test,
                         use_r_packages=self.use_r_packages,
                         seed=self.seed)

        cindex_cat = c_index(self.full_labels, dead_full, days_full,
                             labels_test_categorical, dead_test, days_test,
                             use_r_packages=self.use_r_packages,
                             seed=self.seed)

        cindex_proba = c_index(self.full_labels_proba.T[0], dead_full, days_full,
                               self.test_labels_proba.T[0], dead_test, days_test,
                               use_r_packages=self.use_r_packages,
                               seed=self.seed)

        if self.verbose:
            print('c-index for boosting test dataset:{0}'.format(cindex))
            print('c-index proba for boosting test dataset:{0}'.format(cindex_proba))
            print('c-index cat for boosting test dataset:{0}'.format(cindex_cat))

        self.log['c-index test boosting {0}'.format(self.test_fname_key)] = cindex
        self.log['c-index proba test boosting {0}'.format(self.test_fname_key)] = cindex_proba
        self.log['c-index cat test boosting {0}'.format(self.test_fname_key)] = cindex_cat

        return cindex

    def compute_c_indexes_for_full_dataset(self):
        """
        return c-index using labels as predicat
        """
        days_full, dead_full = np.asarray(self.survival_full).T
        labels_categorical = self._labels_proba_to_labels(self.full_labels_proba)

        cindex = c_index(self.full_labels, dead_full, days_full,
                         self.full_labels, dead_full, days_full,
                         use_r_packages=self.use_r_packages,
                         seed=self.seed)

        cindex_cat = c_index(labels_categorical, dead_full, days_full,
                             labels_categorical, dead_full, days_full,
                             use_r_packages=self.use_r_packages,
                             seed=self.seed)

        cindex_proba = c_index(self.full_labels_proba.T[0], dead_full, days_full,
                               self.full_labels_proba.T[0], dead_full, days_full,
                               use_r_packages=self.use_r_packages,
                               seed=self.seed)

        if self.verbose:
            print('c-index for boosting full dataset:{0}'.format(cindex))
            print('c-index proba for boosting full dataset:{0}'.format(cindex_proba))
            print('c-index cat for boosting full dataset:{0}'.format(cindex_cat))

        self.log['c-index full boosting {0}'.format(self.test_fname_key)] = cindex
        self.log['c-index proba full boosting {0}'.format(self.test_fname_key)] = cindex_proba
        self.log['c-index cat full boosting {0}'.format(self.test_fname_key)] = cindex_cat

        return cindex

    def compute_c_indexes_multiple_for_test_dataset(self):
        """
        Not Functionnal !
        """
        print('not funtionnal!')
        return

        matrix_array_train = self._from_model_dataset(self.models[0], 'matrix_ref_array')
        matrix_array_test = self._from_model_dataset(self.models[0], 'matrix_test_array')

        nbdays, isdead = self._from_model_dataset(self.models[0],
                                                  'survival').T.tolist()
        nbdays_test, isdead_test = self._from_model_dataset(self.models[0],
                                                            'survival_test').T.tolist()

        activities_train, activities_test = [], []

        for model in self.models:
            activities_train.append(model.predict_nodes_activities(matrix_array_train))
            activities_test.append(model.predict_nodes_activities(matrix_array_test))

        activities_train = hstack(activities_train)
        activities_test = hstack(activities_test)

        cindex = c_index_multiple(
            activities_train, isdead, nbdays,
            activities_test, isdead_test, nbdays_test, seed=self.seed)

        print('total number of survival features: {0}'.format(activities_train.shape[1]))
        print('cindex multiple for test set: {0}:'.format(cindex))

        self.log['c-index multiple test {0}'.format(self.test_fname_key)] = cindex
        self.log['Number of survival features {0}'.format(
            self.test_fname_key)] = activities_train.shape[1]

        return cindex

    def plot_supervised_predicted_labels_for_test_sets(
            self,
            define_as_main_kernel=False,
            use_main_kernel=False):
        """
        """
        print('#### plotting supervised labels....')

        self._from_model(self.models[0], "plot_supervised_kernel_for_test_sets",
                         define_as_main_kernel=define_as_main_kernel,
                         use_main_kernel=use_main_kernel,
                         test_labels_proba=self.test_labels_proba,
                         test_labels=self.test_labels,
                         key='_' + self.test_fname_key)

    def plot_supervised_kernel_for_test_sets(self):
        """
        """
        from simdeep.plot_utils import plot_kernel_plots

        if self.verbose:
            print('plotting survival features using autoencoder...')

        encoder_key = self._create_autoencoder_for_kernel_plot()
        activities, activities_test = self._predict_kde_matrices(
            encoder_key, self.dataset.matrix_test_array)

        html_name = '{0}/{1}_{2}_supervised_kdeplot.html'.format(
            self.path_results,
            self.project_name,
            self.test_fname_key)

        plot_kernel_plots(
            test_labels=self.test_labels,
            test_labels_proba=self.test_labels_proba,
            labels=self.full_labels,
            activities=activities,
            activities_test=activities_test,
            dataset=self.dataset,
            path_html=html_name)

    def _predict_kde_survival_nodes_for_train_matrices(self, encoder_key):
        """
        """
        self.kde_survival_node_ids = {}
        encoder_array = self.encoder_for_kde_plot_dict[encoder_key]

        for key in encoder_array:
            encoder = encoder_array[key]
            matrix_ref = encoder.predict(self.dataset.matrix_ref_array[key])

            survival_node_ids = self._from_model(self.models[0], '_look_for_survival_nodes',
                activities=matrix_ref, survival=self.dataset.survival)

            self.kde_survival_node_ids[key] = survival_node_ids
            self.kde_train_matrices[key] = matrix_ref

    def _predict_kde_matrices(self, encoder_key,
                              matrix_test_array):
        """
        """
        matrix_test_list = []
        matrix_ref_list = []

        encoder_array = self.encoder_for_kde_plot_dict[encoder_key]

        for key in matrix_test_array:
            encoder = encoder_array[key]
            matrix_test = encoder.predict(matrix_test_array[key])
            matrix_ref = self.kde_train_matrices[key]

            survival_node_ids = self.kde_survival_node_ids[key]

            if len(survival_node_ids) > 1:
                matrix_test = matrix_test.T[survival_node_ids].T
                matrix_ref = matrix_ref.T[survival_node_ids].T
            else:
                if self.verbose:
                    print('not enough survival nodes to construct kernel for key: {0}' \
                          'skipping the {0} matrix'.format(key))
                continue

            matrix_ref_list.append(matrix_ref)
            matrix_test_list.append(matrix_test)

        if not matrix_ref_list:
            if self.verbose:
                print('\n<!><!><!><!><!><!><!><!><!><!><!><!><!><!><!><!><!>\n' \
                      ' matrix_ref_list / matrix_test_list empty!' \
                      'take the last OMIC ({0}) matrix as ref \n' \
                      '<!><!><!><!><!><!><!><!><!><!><!><!><!><!><!><!><!><!>\n'.format(key))
            matrix_ref_list.append(matrix_ref)
            matrix_test_list.append(matrix_test)

        return hstack(matrix_ref_list), hstack(matrix_test_list)

    def _create_autoencoder_for_kernel_plot(self):
        """
        """
        key_normalization = {
            key: self.test_normalization[key]
            for key in self.test_normalization
            if self.test_normalization[key]
        }

        encoder_key = str(key_normalization)
        encoder_key = 'omic:{0} normalisation: {1}'.format(
            list(self.test_tsv_dict.keys()),
            encoder_key)

        if encoder_key in self.encoder_for_kde_plot_dict:
            if self.verbose:
                print('loading test data for plotting...')

            self.dataset.load_new_test_dataset(
                tsv_dict=self.test_tsv_dict,
                path_survival_file=self.test_survival_file,
                normalization=self.test_normalization)

            return encoder_key

        self.dataset = LoadData(
            cross_validation_instance=None,
            training_tsv=self.training_tsv,
            survival_tsv=self.survival_tsv,
            metadata_tsv=self.metadata_tsv,
            survival_flag=self.survival_flag,
            path_data=self.path_data,
            verbose=False,
            normalization=self.test_normalization,
            subset_training_with_meta=self.subset_training_with_meta
        )

        if self.verbose:
            print('preparing data for plotting...')

        self.dataset.load_array()
        self.dataset.load_survival()
        self.dataset.load_meta_data()
        self.dataset.subset_training_sets()
        self.dataset.reorder_matrix_array(self.sample_ids_full)
        self.dataset.create_a_cv_split()
        self.dataset.normalize_training_array()

        self.dataset.load_new_test_dataset(
            tsv_dict=self.test_tsv_dict,
            path_survival_file=self.test_survival_file,
            normalization=self.test_normalization)

        if self.verbose:
            print('fitting autoencoder for plotting...')

        autoencoder = DeepBase(dataset=self.dataset,
                               seed=self.seed,
                               verbose=False,
                               dropout=0.1,
                               epochs=50)

        autoencoder.matrix_train_array = self.dataset.matrix_ref_array

        # label_encoded = OneHotEncoder().fit_transform(
        #     self.full_labels.reshape(-1, 1)).todense()

        # autoencoder.construct_supervized_network(label_encoded)

        autoencoder.construct_supervized_network(self.full_labels_proba)

        self.encoder_for_kde_plot_dict[encoder_key] = autoencoder.encoder_array

        if self.verbose:
            print('fitting done!')

        self._predict_kde_survival_nodes_for_train_matrices(encoder_key)

        return encoder_key

    def load_new_test_dataset(self, tsv_dict,
                              fname_key=None,
                              path_survival_file=None,
                              normalization=None,
                              debug=False,
                              verbose=False,
                              survival_flag=None,
                              metadata_file=None
                              ):
        """
        """
        self.test_tsv_dict = tsv_dict
        self.test_survival_file = path_survival_file

        if normalization is None:
            normalization = self.normalization

        self.test_normalization = normalization

        if debug or self.nb_threads < 2:
            pass
        # for model in self.models:
        # model.verbose = True
        # model.dataset.verbose = True

        self.test_fname_key = fname_key

        print("Loading new test dataset {0} ...".format(
            self.test_fname_key))
        t_start = time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._from_models('_predict_new_dataset',
                              tsv_dict=tsv_dict,
                              path_survival_file=path_survival_file,
                              normalization=normalization,
                              survival_flag=survival_flag,
                              metadata_file=metadata_file
            )

        print("Test dataset {1} loaded in {0} s".format(
            time() - t_start, self.test_fname_key))

        if fname_key:
            self.project_name = '{0}_{1}'.format(self._project_name, fname_key)

    def compute_survival_feature_scores_per_cluster(self,
                                                    pval_thres=0.001,
                                                    use_meta=False):
        """
        """
        print('computing survival feature importance per cluster...')
        pool = Pool(self.nb_threads)
        mapf = pool.map

        if (self.metadata_usage in ['all', 'new-features'] or use_meta) and \
           self.metadata_mat_full is not None:
            metadata_mat = self.metadata_mat_full
        else:
            metadata_mat = None

        for label in set(self.full_labels):
            self.survival_feature_scores_per_cluster[label] = []

        feature_dict = self._from_model_dataset(self.models[0], 'feature_array')

        def generator(feature_list, matrix, feature_index):
            for feat in feature_list:
                i = feature_index[feat[0]]
                yield (feat,
                       np.asarray(matrix[i]).reshape(-1),
                       self.survival_full,
                       metadata_mat,
                       pval_thres,
                       self.use_r_packages)

        for key in self.matrix_with_cv_array:
            feature_index = {feat: i for i, feat in enumerate(feature_dict[key])}

            for label in self.feature_scores_per_cluster:
                matrix = self.matrix_with_cv_array[key][:]

                feature_list =  self.feature_scores_per_cluster[label]
                feature_list = [feat for feat in feature_list
                                if feat[0] in feature_index]

                input_list = generator(feature_list, matrix.T, feature_index)

                features_scored = mapf(
                    _process_parallel_survival_feature_importance_per_cluster,
                    input_list)

                for feature, pvalue in features_scored:
                    if feature is not None:
                        self.survival_feature_scores_per_cluster[label].append(
                            (feature, pvalue))

                if label in self.survival_feature_scores_per_cluster:
                    self.survival_feature_scores_per_cluster[label].sort(
                        key=lambda x: x[1])

    def compute_feature_scores_per_cluster(self, pval_thres=0.001):
        """
        """
        print('computing feature importance per cluster...')
        self._reorder_matrix_full()
        mapf = map

        for label in set(self.full_labels):
            self.feature_scores_per_cluster[label] = []

        def generator(labels, feature_list, matrix):
            for i in range(len(feature_list)):
                yield feature_list[i], matrix[i], labels, pval_thres

        feature_dict = self._from_model_dataset(self.models[0], 'feature_array')

        for key in self.matrix_with_cv_array:
            matrix = self.matrix_with_cv_array[key][:]
            labels = self.full_labels[:]

            input_list = generator(labels, feature_dict[key], matrix.T)

            features_scored = mapf(
                _process_parallel_feature_importance_per_cluster, input_list)
            features_scored = [feat for feat_list in features_scored
                               for feat in feat_list]

            for label, feature, median_diff, pvalue in features_scored:
                self.feature_scores_per_cluster[label].append((
                    feature, median_diff, pvalue))

            for label in self.feature_scores_per_cluster:
                self.feature_scores_per_cluster[label].sort(
                    key=lambda x: x[2])

    def write_feature_score_per_cluster(self):
        """
        """
        f_file_name = '{0}/{1}_features_scores_per_clusters.tsv'.format(
            self.path_results, self._project_name)
        f_anti_name = '{0}/{1}_features_anticorrelated_scores_per_clusters.tsv'.format(
            self.path_results, self._project_name)

        f_file = open(f_file_name, 'w')
        f_anti_file = open(f_anti_name, 'w')
        f_file.write('#label\tfeature\tmedian difference\tp-value\n')
        f_anti_file.write('#label\tfeature\tmedian difference\tp-value\n')

        f_file.write('cluster id\tfeature\tmedian diff\tWilcoxon p-value\n')

        for label in self.feature_scores_per_cluster:
            for feature, median_diff, pvalue in self.feature_scores_per_cluster[label]:
                if median_diff > 0:
                    f_to_write = f_file
                else:
                    f_to_write = f_anti_file

                f_to_write.write('{0}\t{1}\t{2}\t{3}\n'.format(
                    label, feature, median_diff, pvalue))

        print('{0} written'.format(f_file_name))
        print('{0} written'.format(f_anti_name))

        if self.survival_feature_scores_per_cluster:
            f_file_name = '{0}/{1}_survival_features_scores_per_clusters.tsv'.format(
                self.path_results, self._project_name)
            f_to_write = open(f_file_name, 'w')
            f_to_write.write(
                '#label\tfeature\tmedian difference\tcluster logrank p-value\tCoxPH Log-rank p-value\n')

            for label in self.survival_feature_scores_per_cluster:
                for feature, pvalue in self.survival_feature_scores_per_cluster[label]:
                    f_to_write.write('{0}\t{1}\t{2}\t{3}\t{4}\n'.format(
                        label, feature[0], feature[1], feature[2], pvalue))

            print('{0} written'.format(f_file_name))
        else:
            print("No survival features detected. File: {0} not writtten".format(f_file_name))

    def evalutate_cluster_performance(self):
        """
        """
        if self._pretrained_fit:
            print('model is fitted on pretrained labels' \
                  ' Cannot evaluate cluster performance')
            return

        bic_scores = np.array([self._from_model_attr(model, 'bic_score') for model in self.models])

        if bic_scores[0] is not None:
            bic = np.nanmean(bic_scores)
            print('bic score: mean: {0} std :{1}'.format(bic_scores.mean(), bic_scores.std()
            ))
            self.log['bic'] = bic
        else:
            bic = np.nan

        silhouette_scores = np.array([self._from_model_attr(model, 'silhouette_score')
                                      for model in self.models])
        silhouette = silhouette_scores.mean()
        print('silhouette score: mean: {0} std :{1}'.format(silhouette,
                                                            silhouette_scores.std()
        ))
        self.log['silhouette'] = silhouette

        calinski_scores = np.array([self._from_model_attr(model, 'calinski_score')
                                    for model in self.models])

        calinski = calinski_scores.mean()
        print('calinski harabasz score: mean: {0} std :{1}'.format(calinski_scores.mean(),
                                                                   calinski_scores.std()
        ))
        self.log['calinski'] = calinski

        return bic, silhouette, calinski

    def save_cv_models_classes(self, path_results=""):
        """
        """
        self.save_models_classes(path_results=path_results,
                                 use_cv_labels=True)

    def save_test_models_classes(self, path_results=""):
        """
        """
        self.save_models_classes(path_results=path_results,
                                 use_test_labels=True)

    def save_models_classes(self, path_results="",
                            use_cv_labels=False,
                            use_test_labels=False):
        """
        """
        if not path_results:
            if use_test_labels:
                path_results = '{0}/saved_models_test_classes'.format(
                    self.path_results)
            elif use_cv_labels:
                path_results = '{0}/saved_models_cv_classes'.format(
                    self.path_results)
            else:
                path_results = '{0}/saved_models_classes'.format(
                    self.path_results)

        if not isdir(path_results):
            mkdir(path_results)

        for i, model in enumerate(self.models):
            if use_test_labels:
                labels = self._from_model_attr(model, 'test_labels')
                labels_proba = self._from_model_attr(model, 'test_labels_proba')
                sample_ids = self._from_model_dataset(model, 'sample_ids_test')
                survival = self._from_model_dataset(model, 'survival_test')
            elif use_cv_labels:
                labels = self._from_model_attr(model, 'cv_labels')
                labels_proba = self._from_model_attr(model, 'cv_labels_proba')
                sample_ids = self._from_model_dataset(model, 'sample_ids_cv')
                survival = self._from_model_dataset(model, 'survival_cv')
            else:
                labels = self._from_model_attr(model, 'labels')
                labels_proba = self._from_model_attr(model, 'labels_proba')
                sample_ids = self._from_model_dataset(model, 'sample_ids')
                survival = self._from_model_dataset(model, 'survival')

            seed = self._from_model_attr(model, 'seed')

            nbdays, isdead = survival.T.tolist()

            if not seed:
                seed = i

            path_file = '{0}/model_instance_{1}.tsv'.format(
                path_results, seed)

            labels_proba = labels_proba.T[0]

            self._from_model(
                model, '_write_labels',
                sample_ids,
                labels,
                path_file=path_file,
                labels_proba=labels_proba,
                nbdays=nbdays, isdead=isdead)

        print('individual model labels saved at: {0}'.format(path_results))

    def _convert_logs(self):
        """
        """
        for key in self.log:
            if isinstance(self.log[key], np.float32):
                self.log[key] = float(self.log[key])
            elif isinstance(self.log[key], NALogicalType):
                self.log[key] = np.nan
            try:
                str(self.log[key])
            except Exception:
                self.log.pop(key)

    def write_logs(self):
        """
        """
        self._convert_logs()

        with open('{0}/{1}.log.json'.format(self.path_results, self._project_name), 'w') as f:
            f.write(simplejson.dumps(self.log, indent=2))


def _highest_proba(proba):
    """
    """
    labels = []
    probas = []

    clusters = range(proba.shape[2])
    samples = range(proba.shape[1])

    for sample in samples:
        proba_vector = [proba.T[cluster][sample].max() for cluster in clusters]
        label = max(enumerate(proba_vector), key=lambda x:x[1])[0]

        labels.append(label)
        probas.append(proba_vector)

    return np.asarray(labels), np.asarray(probas)

def _mean_proba(proba):
    """
    """
    labels = []
    probas = []

    clusters = range(proba.shape[2])
    samples = range(proba.shape[1])

    for sample in samples:
        proba_vector = [proba.T[cluster][sample].mean() for cluster in clusters]
        label = max(enumerate(proba_vector), key=lambda x:x[1])[0]

        labels.append(label)
        probas.append(proba_vector)

    return np.asarray(labels), np.asarray(probas)

def _weighted_mean(proba, weights):
    """
    """
    labels = []
    probas = []
    weights = np.array(weights)
    weights[weights < 0.50] = 0.0
    weights = np.power(weights, 4)

    if weights.sum() == 0:
        weights[:] = 1.0

    clusters = range(proba.shape[2])
    samples = range(proba.shape[1])

    for sample in samples:
        proba_vector = [np.average(proba.T[cluster][sample]) for cluster in clusters]
        label = max(enumerate(proba_vector), key=lambda x:x[1])[0]

        labels.append(label)
        probas.append(proba_vector)

    return np.asarray(labels), np.asarray(probas)


def _weighted_max(proba, weights):
    """
    """
    labels = []
    probas = []
    weights = np.array(weights)
    weights[weights < 0.50] = 0.0
    weights = np.power(weights, 4)

    if weights.sum() == 0:
        weights[:] = 1.0

    clusters = range(proba.shape[2])
    samples = range(proba.shape[1])

    for sample in samples:
        proba_vector = [np.max(proba.T[cluster][sample] * weights) for cluster in clusters]
        label = max(enumerate(proba_vector), key=lambda x:x[1])[0]

        labels.append(label)
        probas.append(proba_vector)

    return np.asarray(labels), np.asarray(probas)


def _reorder_labels(labels, sample_ids):
    """
    """
    sample_dict = {sample: id for id, sample in enumerate(sample_ids)}
    sample_ordered = set(sample_ids)

    index = [sample_dict[sample] for sample in sample_ordered]

    return labels[index]
