import pandas as pd
import wordpool
from numpy.random import shuffle
import numpy as np

RAM_LIST_EN = wordpool.load("ram_wordpool_en.txt")
RAM_LIST_SP = wordpool.load("ram_wordpool_sp.txt")

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")


def generate_session_pool(pairs_per_list = 6, num_lists=25,language='EN'):
    """Generate the pool of words for a single task session. This does *not*
    assign stim, no-stim, or PS metadata since this part depends on the
    experiment.

    :param int words_per_list: Number of words in each list.
    :param int num_lists: Total number of lists excluding the practice list.
    :param str language: Session language (``EN`` or ``SP``).
    :returns: Word pool
    :rtype: pd.DataFrame

    """
    old_lists = []
    assert language in ['EN','SP']
    practice_list_words = (PRACTICE_LIST_EN if language=='EN' else PRACTICE_LIST_SP).values
    shuffle(practice_list_words)
    practice_list = pd.DataFrame(practice_list_words.reshape((-1,2)),columns=['word1','word2'])

    practice_list['type']='PRACTICE'
    practice_list['listno']=0

    words = (RAM_LIST_EN if language=='EN' else RAM_LIST_SP).values
    assert len(words)==pairs_per_list*2*num_lists
    shuffle(words)
    word_lists = pd.DataFrame(words.reshape((-1,2)),columns=['word1','word2'])
    word_lists = wordpool.assign_list_numbers(word_lists,num_lists,start=1)
    full_list = pd.concat([practice_list,word_lists],ignore_index=True)
    cue_positions_by_list = [assign_cues(words) for _,words in full_list.groupby('listno')]
    full_list['cue_pos'] = np.concatenate(cue_positions_by_list)
    # if any(old_lists):
    #     matching_pairs = [(full_list['word1']==lst['word1']) & (full_list['word2']==lst['word2']) for lst in old_lists]
    #     all_matches_together = reduce(lambda x,y: x | y, matching_pairs,initial=np.zeros(len(full_list)).astype(np.bool))
    #     while all_matches_together:
    #
    # old_lists.append(full_list)
    return full_list


def assign_cues(words):
    cues = ['word1' if i%2 else 'word2' for i in range(len(words))]
    shuffle(cues)
    return cues



