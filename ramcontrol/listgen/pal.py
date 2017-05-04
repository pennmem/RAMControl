import pandas as pd
import wordpool
from numpy.random import shuffle,randint
import numpy as np
from collections import deque
from itertools import chain

wordpools ={
    'EN':wordpool.load("ram_wordpool_en.txt"),
    'SP': wordpool.load("ram_wordpool_sp.txt") }

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")



def generate_n_session_pairs(n_sessions,n_lists=25, language='EN'):
    words = wordpools[language].values
    n_words = len(words)
    vec=deque([1 for _ in range(n_sessions)] + [0 for _ in range(n_words-n_sessions)])
    vec.rotate(-1*n_sessions/2)
    circulant = np.diag([-1 for _ in words])
    for i in range(len(words)):
        avail = circulant[i]!=-1
        circulant[i,avail] = list(vec)
        vec.rotate(1)
    circulant[circulant==-1]=0
    shuffle(words)
    all_pairs = list(chain(*[[(w,w0) for w0 in words[c]] for (w,c) in zip(words,circulant)]))
    sess_pools = [pd.DataFrame(columns=['word1','word2']) for _ in range(n_sessions)]
    for pair in all_pairs:
        for sess_pool in sess_pools:
            if not (where_(pair[0],sess_pool).any() or where_(pair[1],sess_pool).any()):
                sess_pool.append({'word1':pair[0],'word2':pair[1],},ignore_index=True)
    for i in range(n_sessions):
        sess_pools[i]=add_fields(sess_pools[i],n_lists)

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











