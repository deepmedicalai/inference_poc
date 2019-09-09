# /tasks/relevance.py

import time
import os
import shutil
from webserver import query_db, upsert_db, delete_db
import sqlite3
import importlib
from tasks.stages import SESSION_STAGE_TO_INDEX, SESSION_STAGE, FILE_STAGE_TO_INDEX, FILE_STAGE, set_session_stage_to, get_session_status
from dicoms.utils import get_relevance_inference_model, path_to_object, create_frame_for_classification, get_relevance
from dicoms.utils import create_frame_for_classification_internal, get_relevance_internal
from flask import Flask
from functools import partial, reduce
from datetime import datetime
import redis
from rq import Queue, Connection
from tasks.mask import prepare_for_mask

#define pipeline
def compose(*funcs):
    return lambda x: reduce(lambda f, g: g(f), list(funcs), x)


def get_flask_config():
    # instantiate the app
    app = Flask(
        __name__, static_url_path=''
    )

    # set config
    app_settings = os.getenv('APP_SETTINGS')
    app.config.from_object(app_settings)
    return app.config


def get_db():
    config = get_flask_config()
    #db_path = os.path.join( os.path.dirname(os.getcwd()), 'main', './database/database.db')
    print('db_path', config['DATABASE'])
    db = sqlite3.connect(config['DATABASE'])
    return db

def close_connection(db):
    if db is not None:
        db.close()

def get_incoming_dir_for_session(session_id, config):
    incoming_path = config['INCOMING_DIR']
    relative_session_dir = './'+str(session_id)
    session_dir = os.path.join(incoming_path, relative_session_dir)
    return session_dir, relative_session_dir

def prepare_for_relevance(session_id):
    print('Started \'prepare_for_relevance\' for {}'.format(session_id))
    start_dt = datetime.now()
    db_conn = get_db()

    config = get_flask_config()
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

    print('Working in stage {}'.format(session_info['stage_str']))
    set_session_stage_to(db_conn, session_id, SESSION_STAGE_TO_INDEX['relevance_classification_preparing_files'])
    session_info = get_session_status(db_conn, session_id)
    print('Working in stage {}'.format(session_info['stage_str']))

    move_files_to_procesing_dir(db_conn, session_id, config)

    close_connection(db_conn)

    with Connection(redis.from_url(config['REDIS_URL'])):
        q = Queue()
        task = q.enqueue(classify_for_relevance, session_id)
        print('Task scheduled for classify_for_relevance({})'.format(session_id))

    end_dt = datetime.now()
    delta = end_dt - start_dt
    print('prepare_for_relevance for {} took:'.format(session_id), delta)
    return True

def classify_for_relevance(session_id):
    print('Started \'classify_for_relevance\' for {}'.format(session_id))
    start_dt = datetime.now()
    db_conn = get_db()

    config = get_flask_config()
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

    new_stage = SESSION_STAGE_TO_INDEX['relevance_classification_in_progress']
    set_session_stage_to(db_conn, session_id, new_stage)
    print('\'classify_for_relevance\' is in stage {}'.format(new_stage))

    classify_files_for_relevance(db_conn, session_id, config)

    new_stage = SESSION_STAGE_TO_INDEX['relevance_classification_completed']
    set_session_stage_to(db_conn, session_id, new_stage)
    print('\'classify_for_relevance\' is in stage {}'.format(new_stage))
    
    close_connection(db_conn)

    with Connection(redis.from_url(config['REDIS_URL'])):
        q = Queue()
        task = q.enqueue(prepare_for_mask, session_id)
        print('Task scheduled for prepare_for_mask({})'.format(session_id))

    end_dt = datetime.now()
    delta = end_dt - start_dt
    print('classify_for_relevance for {} took:'.format(session_id), delta)
    return True



def move_files_to_procesing_dir(db_conn, session_id, config):

    local_incoming_session_dir, relative_session_dir = get_incoming_dir_for_session(session_id, config)
    local_processing_dir = config['PROCESSING_DIR']
    local_processing_session_dir = os.path.join(local_processing_dir, relative_session_dir)

    os.mkdir(local_processing_session_dir)

    processed_file_dict = []

    for row in query_db(db_conn, 'SELECT id, initial_path FROM files where session_id = ?', [session_id]):
        file_id = row['id']
        file_name = row['initial_path']

        local_incoming_file_path = os.path.join(local_incoming_session_dir, file_name)
        local_processing_file_path = os.path.join(local_processing_session_dir, file_name)

        if os.path.exists(local_incoming_file_path):
            shutil.move(local_incoming_file_path, local_processing_session_dir)

            upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, processing_path = ? WHERE id = ?'
                , [FILE_STAGE_TO_INDEX['moved_to_processing'], local_processing_file_path, file_id])

        else:
            err_msg = 'Problem locating file \'{}\''.format(local_incoming_file_path)
            print(err_msg)
            upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, error_message = ? WHERE id = ?'
                , [FILE_STAGE_TO_INDEX['errored'], err_msg, file_id])

    
    return True


#creates an initial version of the object.
def dbrecord_to_object(row):
    print('dbrecord_to_object: {}'.format(row['id']))
    obj  = lambda: None
    path = row['processing_path']
    obj.file_id = row['id']
    obj.session_id = row['session_id']
    obj.file_stage = row['file_stage']
    obj.dicom_path = path
    obj.base_name = os.path.splitext(os.path.basename(path))[0]

    yield obj

def dbrecord_to_object_internal(row, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('dbrecord_to_object: {}'.format(row['id']))
    obj  = {}
    path = row['processing_path']
    obj['id'] = row['id']
    obj['file_id'] = obj['id']
    obj['session_id'] = row['session_id']
    obj['file_stage'] = row['file_stage']
    obj['dicom_path'] = path
    obj['base_name'] = os.path.splitext(os.path.basename(path))[0]
    obj['is_error'] = False
    obj['break_processing'] = False
    obj['is_supportedSOP'] = False

    return obj

def save_file_stage(iter_element, options, db_conn, stage):
    for ie in iter_element:
        element = ie
        file_id = element.file_id
        element.file_stage = stage
        #get file id and relevance
        upsert_db(db_conn
                , 'UPDATE files SET file_stage = ? WHERE id = ?'
                , [element.file_stage, file_id])
        
        yield element

def save_file_stage_internal(element, options, db_conn, stage):
    if options['SHOW_DEBUG_MESSAGES']:
        print('save_file_stage_internal: ', element['id'])
    file_id = element['id']
    element['file_stage'] = stage
    #get file id and relevance
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ? WHERE id = ?'
            , [element['file_stage'], file_id])
    
    return element

def save_relevance_status(iter_element, options, db_conn):
    for ie in iter_element:
        element = ie
        file_id = element.file_id
        is_relevant_str = 'YES' if element.relevant else 'NO'
        element.file_stage = FILE_STAGE_TO_INDEX['has_relevance_result']
        #get file id and relevance
        upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, relevance_result = ? WHERE id = ?'
                , [element.file_stage, is_relevant_str, file_id])
        
        yield element

def save_relevance_status_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_relevance_status_internal: ', element['id'], element['relevant'])
    file_id = element['id']
    is_relevant_str = 'YES' if element['relevant'] else 'NO'
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_relevance_result']
    #get file id and relevance
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, relevance_result = ? WHERE id = ?'
            , [element['file_stage'], is_relevant_str, file_id])
    
    return element

def classify_files_for_relevance(db_conn, session_id, config):

    options = {}
    options['SHOW_DEBUG_MESSAGES'] = False

    relevance_model = get_relevance_inference_model(config['RELEVANCE_MODEL_FILE'], options)
    if relevance_model is None:
        print('Error loading PyTorch model')
        return
    
    options['CLASSIFICATION_SIZE'] = 48
    options['RELEVANCE_MODEL'] = relevance_model
    options['SHOW_DEBUG_MESSAGES'] = False

    # create_frame_for_classification_with_options = partial(create_frame_for_classification, options=options)
    # save_file_stage_with_options_to_ready_for_ML = partial(save_file_stage, options = options, db_conn = db_conn, stage = FILE_STAGE_TO_INDEX['has_relevance_frame'])
    # get_relevance_with_options = partial(get_relevance, options=options)
    # save_relevance_status_with_options = partial(save_relevance_status, options = options, db_conn = db_conn)



    # relevance_pipeline = compose(dbrecord_to_object
    #     , create_frame_for_classification_with_options
    #     , save_file_stage_with_options_to_ready_for_ML
    #     , get_relevance_with_options
    #     , save_relevance_status_with_options)

    # Test model on random input data.

    if options['SHOW_DEBUG_MESSAGES']:
        count = query_db(db_conn
            ,'SELECT count(*) as count FROM files where session_id = ? and file_stage = ?', [session_id, FILE_STAGE_TO_INDEX['moved_to_processing']], one=True)

        print('Count ({}): '.format(session_id), count)

    for row in query_db(db_conn, 'SELECT id, processing_path, session_id, file_stage FROM files where session_id = ? and file_stage = ?', [session_id, FILE_STAGE_TO_INDEX['moved_to_processing']]):
        
        element = dbrecord_to_object_internal(row, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 1 failure', element)
            continue

        element = create_frame_for_classification_internal(element, options)
        if (element['break_processing']):
            #record reason
            if not element['is_supportedSOP']:
                element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['ready_for_results'])
            else:
                if options['SHOW_DEBUG_MESSAGES']:
                    print('Step 2 failure', element)
            continue

        element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['has_relevance_frame'])
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 3 failure', element)
            continue
        
        element = get_relevance_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 4 failure', element)
            continue
        
        element = save_relevance_status_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 5 failure', element)
            continue
        #for result in relevance_pipeline(row):
        #    pass

        if options['SHOW_DEBUG_MESSAGES']:
            print('Completed processing of file {}'.format(row['id']))


    return True



        


