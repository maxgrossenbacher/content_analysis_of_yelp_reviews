import numpy as np
import textacy
import spacy
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import pyLDAvis
import pyLDAvis.sklearn


class NlpTopicAnalysis(object):
    """
    DESC: Takes a pandas DataFrame and allow nlp processing using textacy
    --Input--
        df: pandas dataframe
        textcol: (str) name of column in pandas DataFrame where text are located
        labelcol: (str) name of column in pandas DataFrame where labels are located
    """
    def __init__(self, df=None, textcol=None, labelcol=None, labelcol2=None, text=[]):
        self.spacy = spacy.load('en')
        self.df = df
        self.textcol = textcol
        self.labelcol = labelcol
        self.labelcol2 = labelcol2
        self.vectorizer = None
        self.corpus = None
        self.model = None
        self.text = text
        self.label = []
        self.label2=[]
        self.pca_mat = None
        self.tfidf = None
        self.topic_matrix = None
        self.latent_topics_top_terms = {}
        self.terms_list = []
        self.topic_w_weights = {}
        self.ldavis = None
        self.tokens = []
        self.token_vectors = None
        self.doc_vectors = None

    def _get_reviews_and_label(self):
        '''
        DESC: Retrive reviews & labels from a column in a pandas DataFrame and append reviews & labels to a list
        ----------------------------------
        --Output--
            Returns 2 lists of items and labels in column of a pandas DataFrame
        '''
        for i in range(self.df.shape[0]):
            self.text.append(self.df[self.textcol].iloc[i])
            if self.labelcol:
                self.label.append(self.df[self.labelcol].iloc[i])
            if self.labelcol2:
                self.label2.append(self.df[self.labelcol2].iloc[i])
        return


    #Part 2 Saving textacy corpus as compressed file
    def process_text(self, filepath=None, filename=None, compression=None):
        '''
        DESC: Tokenizes and processes pandas DataFrame using textacy. If filepath: saves corpus as pickle to filepath.
        --Input--
            filepath: (str) path to directory where textacy corpus will be saved
            filename: (str) name of pickled textacy corpus
            compression: (str) compression of metadata json ('gzip', 'bz2', 'lzma' or None)
        ----------------------------------
        --Output--
            Returns textacy corpus object, if filepath: saves textacy corpus as pickle
        '''
        if len(self.text) == 0:
            self._get_reviews_and_label()
        self.corpus = textacy.Corpus('en')
        self.corpus.add_texts(texts=self.text, batch_size=1000, n_threads=-1)
        if filepath:
            self.corpus.save(filepath, filename, compression)
            print('Saved textacy corpus to filepath.')
        return



    #Part 3 loading textacy corpus from compressed file
    def load_corpus(self, filepath, filename, compression=None):
        '''
        DESC: Loads pickled corpus of textacy/spacy docs
        --Input--
            filepath: (str) path to directory where textacy corpus is located
            filename: (str) name of pickled textacy corpus
            compression: (str) compression of pickled textacy corpus (gzip, 'bz2', 'lzma' or None)
        ----------------------------------
        --Output--
            Returns textacy corpus object
        '''
        self.corpus = textacy.Corpus.load(filepath, filename, compression)
        return


    # Part4 Vectorizing textacy corpus
    def vectorize(self, weighting='tf', min_df=0.1, max_df=0.95, max_n_terms=100000, exclude_pos=['PUNCT','SPACE']):
        '''
        DESC: Creates tf/tfidf/binary matrix of textacy corpus.
            weighting = (str) tf, tfidf, bindary
            min_df = (float/int) exclude terms that appear in less than precentage/number of documents
            max_df = (float/int) exclude terms that appear in more than precentage/number of documents
            max_n_terms = (int) max terms (features) to include in matrix
            exclude_pos = (lst of strs) list of POS tags to remove from vocabulary when creating matrix
        --Output--
            Returns creates tf/tfidf/binary matrix of textacy corpus.
        '''
        for doc in self.corpus:
            self.terms_list.append(list(doc.to_terms_list(n_grams=1, named_entities=True, \
                                                normalize='lemma', as_strings=True, \
                                                filter_stops=True, filter_punct=True, exclude_pos=exclude_pos)))
        self.vectorizer = textacy.Vectorizer(weighting=weighting, normalize=True, \
                                            smooth_idf=True, min_df=min_df, max_df=max_df, max_n_terms=max_n_terms)
        self.tfidf = self.vectorizer.fit_transform(self.terms_list)
        return self.tfidf

    def word2vec(self):
        doc_vects = []
        toks_vects = []
        for ind, doc in enumerate(self.corpus):
            print('going through doc {}...'.format(ind))
            doc_vects.append(doc.spacy_doc.vector)
            for token in doc.spacy_doc:
                if token.orth_ not in self.tokens:
                    toks_vects.append(token.vector)
                    self.tokens.append(token.orth_)
        print('creating arrays')
        print(len(doc_vects))
        self.doc_vectors = np.array(doc_vects)
        print(len(toks_vects))
        self.token_vectors = np.array(toks_vects)
        print('Done.')


    # Principle component analysis for k means graph
    def pca(self, n_components):
        '''
        DESC: Creates lower dimensional representation of tf/tfidf/binary matrix using PCA
            n_components = number of dimensions
        --Output--
            Returns lower dimensional pca_mat
        '''
        p = PCA(n_components=n_components, copy=True, whiten=False, svd_solver='auto', \
                    tol=0.0, iterated_power='auto', random_state=None)
        self.pca_mat = p.fit_transform(self.doc_vectors)
        return


    def k_means(self, n_clusters):
        '''
        DESC: K-nearest neighbors modeling of tfidf matrix.
        --Input--
            n_clusters: number of clusters to model
        ----------------------------------
        --Output--
            Returns centroids for n_clusters and labels for each tfidf document vector
        '''
        knn = KMeans(n_clusters=n_clusters, init='k-means++', n_init=10, max_iter=20, \
                        tol=0.001, precompute_distances='auto', verbose=0, \
                        random_state=None, copy_x=True, n_jobs=-1, algorithm='auto')
        knn.fit(self.pca_mat)
        centroids = knn.cluster_centers_
        k_labels = knn.labels_
        if self.pca_mat.shape[1] == 2:
            plt.scatter(self.pca_mat[:,0], self.pca_mat[:,1], c=k_labels.astype(np.float), alpha=0.3)
            plt.legend()
            plt.title('Review Clustering')
            print('plotting...')
            plt.show()
        return centroids, k_labels

    #Part 2
    def topic_analysis(self, n_topics=10, model_type='lda', n_terms=50, n_highlighted_topics=5, plot=False, save=False, kwargs=None):
        '''
        DESC: Latent topic modeling of tf/tfidf/binary matrix. If plot, generates termite plot of latent topics.
        for corpus on n topics
        --Input--
            n_topics: (int) number of latent topics
            model_type: (str) 'nmf','lsa','lda' or sklearn.decomposition.<model>
            n_terms: (int) number of key terms ploted in termite plot (y-axis)
            n_highlighted_topics: (int) number of highlighted key topics sorted by importance, max highlighted topics is 6
            plot = (bool) if True will create a terminte plot of latent topics
            save = (str) filename to save plot
            kwargs = (dic) takes hyperparameters --> see sklearn.decomposition.<model>
        ----------------------------------
        --Output--
            Creates topic_matrix of num_docs X n_topics dimensions, topic weights/importance for each topic, and termite plot of key terms to latent topics
        '''
        if n_highlighted_topics > 6:
            print('Value Error: n_highlighted_topics must be =< 5')
            return
        highlighting = {}
        self.model = textacy.TopicModel(model_type, n_topics=n_topics, kwargs=kwargs)
        self.model.fit(self.tfidf)
        self.topic_matrix = self.model.transform(self.tfidf)
        for topic_idx, top_terms in self.model.top_topic_terms(self.vectorizer.feature_names, topics=range(n_topics), weights=False):
            self.latent_topics_top_terms[topic_idx] = top_terms
            # print('Topic {}: {}' .format(topic_idx, top_terms))
        for topic, weight in enumerate(self.model.topic_weights(self.topic_matrix)):
            self.topic_w_weights[topic] = weight
            highlighting[weight] = topic
            # print('Topic {} has weight: {}' .format(topic, weight))

        sort_weights = sorted(highlighting.keys())[::-1]
        highlight = [highlighting[i] for i in sort_weights[:n_highlighted_topics]]
        self.model.termite_plot(self.tfidf, \
                                self.vectorizer.feature_names, \
                                topics=-1,  \
                                n_terms=n_terms, \
                                highlight_topics=highlight)
        plt.tight_layout()
        print('plotting...')
        if save:
            plt.savefig(save)
        if plot:
            plt.show()
        return


    def lda_vis(self, n_words=30, name='model'):
        '''
        DESC: Creates pyLDAvis figure. Requires LDA topic_analysis model
        --Input--
            n_words = number of words to display in the barcharts of figure
        ----------------------------------
        --Output--
            Returns pyLDAvis figure in html browser
        '''
        doc_lengths = [len(doc) for doc in self.corpus]
        vocab_lst = self.vectorizer.feature_names
        term_freq = textacy.vsm.get_doc_freqs(self.tfidf, normalized=False)
        topic_terms_tups = list(self.model.top_topic_terms(self.vectorizer.feature_names, topics=-1, top_n=len(vocab_lst), weights=True))
        lst = []
        for topic in topic_terms_tups:
            words = []
            for w in topic[1]:
                words.append(w)
            lst.append(words)
            topic_weight = []
            for topic in lst:
                weights = []
                for word in vocab_lst:
                    for we in topic:
                        if word == we[0]:
                            weights.append(we[1])
                topic_weight.append(weights)
        topic_term = np.array(topic_weight)
        self.ldavis = pyLDAvis.prepare(topic_term, \
                                        self.topic_matrix, \
                                        doc_lengths, \
                                        vocab_lst, \
                                        term_freq, \
                                        R=n_words, \
                                        mds='mmds', \
                                        sort_topics=False)
        pyLDAvis.save_html(self.ldavis, 'pyLDAvis_'+name)
        print('plotting...')
        pyLDAvis.show(self.ldavis)
