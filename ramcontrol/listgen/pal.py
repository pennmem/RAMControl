import pandas as pd
import wordpool
from numpy.random import shuffle,randint,choice
from random import choice
import numpy as np
from collections import deque
from itertools import chain

wordpools ={
    'EN':wordpool.load("ram_wordpool_en.txt"),
    'SP': wordpool.load("ram_wordpool_sp.txt") }

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")



def generate_n_session_pairs(n_sessions,n_lists=25, n_pairs=6, language='EN'):

    words = wordpools[language].values
    n_words = len(words)
    assert n_lists*n_pairs*2==n_words
    shuffle(words)
    words = deque([w[0] for w in words])
    sess_pools = []
    indices = np.random.choice(np.arange(n_words),size=n_sessions,replace=False)
    for i in indices:
        words.rotate(i)
        word1 = list(words)[:n_words/2]
        word2 = list(words)[n_words/2:]
        word2.reverse()
        new_session = pd.DataFrame(np.array([word1,word2]).T,columns=['word1','word2'])
        sess_pools.append(add_fields(new_session))
        words.rotate(-1*i)
    return sess_pools

def add_fields(word_lists=None,pairs_per_list = 6, num_lists=25,language='EN'):
    """Generate the pool of words for a single task session. This does *not*
    assign stim, no-stim, or PS metadata since this part depends on the
    experiment.

    :param int words_per_list: Number of words in each list.
    :param int num_lists: Total number of lists excluding the practice list.
    :param str language: Session language (``EN`` or ``SP``).
    :returns: Word pool
    :rtype: pd.DataFrame

    """
    if word_lists is None:
        words = wordpools[language].values
        shuffle(words)
        assert len(words) == pairs_per_list * 2 * num_lists
        word_lists = pd.DataFrame(words.reshape((-1,2)),columns=['word1','word2'])

    assert language in ['EN','SP']
    practice_list_words = (PRACTICE_LIST_EN if language=='EN' else PRACTICE_LIST_SP).values
    shuffle(practice_list_words)
    practice_list = pd.DataFrame(practice_list_words.reshape((-1,2)),columns=['word1','word2'])

    practice_list['type']='PRACTICE'
    practice_list['listno']=0

    word_lists = wordpool.assign_list_numbers(word_lists,num_lists,start=1)
    full_list = pd.concat([practice_list,word_lists],ignore_index=True)
    cue_positions_by_list = [assign_cues(words) for _,words in full_list.groupby('listno')]
    full_list['cue_pos'] = np.concatenate(cue_positions_by_list)
    return full_list


def assign_cues(words):
    cues = ['word1' if i%2 else 'word2' for i in range(len(words))]
    shuffle(cues)
    return cues

def equal_pairs(a, b):
    backward = np.array(
        [(b.loc[b.word2 == a.loc[i].word1].word1 == a.loc[i].word2).any()
         for i in a.index]).astype(np.bool)
    forward = np.array(
        [(b.loc[b.word1 == a.loc[i].word1].word2 == a.loc[i].word2).any()
         for i in a.index]).astype(np.bool)
    return backward | forward

def where_(word,wordpool):
    if wordpool.empty:
        return np.array([])
    return (wordpool.word1==word) | (wordpool.word2==word)

def make_unique(wordpools):
    if len(wordpools)<=1:
       pass
    else:
        for i in range(1,len(wordpools)):
            current_pool = wordpools[i]
            prev_pools= wordpools[:i]
            overlap = np.sum([equal_pairs(current_pool,p) for p in prev_pools]).astype(np.bool)
            while overlap.any():
                fix_common_pairs(overlap,current_pool,prev_pools)
                overlap = np.sum([equal_pairs(current_pool, p) for p in prev_pools]).astype(np.bool)

def fix_common_pairs(overlap,current_pool,old_pools):
    common_pairs = current_pool.loc[overlap]



if __name__=='__main__':
    wordpools = generate_n_session_pairs(10)
    for i in range(10):
        for j in range(i):
            pool1 = wordpools[i]
            pool2 = wordpools[j]
            mask = equal_pairs(pool1.loc[pool1.type != 'PRACTICE'],pool2.loc[pool2.type != 'PRACTICE'])








