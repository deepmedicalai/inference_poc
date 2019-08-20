
from webserver import query_db, upsert_db, delete_db

#stages of session
# SESSION_STARTED = 0
# SESSION_RECEIVING_FILES_IN_PROGRESS = 1
# SESSION_RECEIVING_FILES_COMPLETED = 9
# SESSION_RELEVANCE_CLASSIFICATION_PREPARING_FILES = 11
# SESSION_RELEVANCE_CLASSIFICATION_IN_PROGRESS = 15
# SESSION_RELEVANCE_CLASSIFICATION_COMPLETED = 19
# SESSION_MASK_CLASSIFICATION_PREPARING_FILES = 21
# SESSION_MASK_CLASSIFICATION_IN_PROGRESS = 25
# SESSION_MASK_CLASSIFICATION_COMPLETED = 29
# SESSION_DX_CLASSIFICATION_PREPARING_FILES = 31
# SESSION_DX_CLASSIFICATION_IN_PROGRESS = 35
# SESSION_DX_CLASSIFICATION_COMPLETED = 39
# SESSION_RESULTS_PREPARATION = 41
# SESSION_RESULTS_READY_FOR_REVIEW = 50
# SESSION_ARCHIVED = 99

SESSION_STAGE_TO_INDEX = {
    'started':0,
    'receiving_files_in_progress':1,
    'receiving_files_completed':9,
    'relevance_classification_preparing_files':11,
    'relevance_classification_in_progress':15,
    'relevance_classification_completed':19,
    'mask_classification_preparing_files':21,
    'mask_classification_in_progress':25,
    'mask_classification_completed':29,
    'dx_classification_preparing_files':31,
    'dx_classification_in_progress':35,
    'dx_classification_completed':39,
    'result_preparation':41,
    'ready_for_review':50,
    'archived':99,
    'error':199
}

SESSION_STAGE = {v: k for k, v in SESSION_STAGE_TO_INDEX.items()}   #reverse key/value

FILE_STAGE_TO_INDEX = {
    'announced':1,
    'moved_to_processing':11,
    'has_relevance_frame':21,
    'has_relevance_result':29,
    'has_mask_frame':31,
    'has_mask_result':39,
    'ready_for_results':99,
    'errored':199
}
FILE_STAGE = {v: k for k, v in FILE_STAGE_TO_INDEX.items()}   #reverse key/value


def set_session_stage_to(db_conn, session_id, new_state):
    upsert_db(db_conn, 'UPDATE sessions SET stage = ? WHERE id = ?', [new_state, session_id])



def get_session_status(db_conn, session_id):
    row = query_db(db_conn, 'SELECT stage from sessions where id = ? LIMIT 1 ', [session_id], one=True)
    if row is None:
        return None
    stage = row['stage']
    info = {}
    info['session_id'] = session_id
    info['stage'] = stage
    info['stage_str'] = SESSION_STAGE[stage]
    return info

