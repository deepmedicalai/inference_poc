# /tasks/mask.py

import time
import os
import shutil
from webserver import query_db, upsert_db, delete_db
import sqlite3
import importlib
from tasks.stages import SESSION_STAGE_TO_INDEX, SESSION_STAGE, FILE_STAGE_TO_INDEX, FILE_STAGE, set_session_stage_to, get_session_status
from dicoms.utils import get_segmentation_inference_model
from dicoms.utils import get_max_of_frames_internal, save_max_frame_element_internal, get_mask_for_dicom_internal, save_mask_resized_internal
from flask import Flask
from functools import partial, reduce
from datetime import datetime
import redis
from rq import Queue, Connection

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

def prepare_for_mask(session_id):
    print('Started \'prepare_for_mask\' for {}'.format(session_id))
    start_dt = datetime.now()
    db_conn = get_db()

    config = get_flask_config()
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

    print('Working in stage {}'.format(session_info['stage_str']))
    set_session_stage_to(db_conn, session_id, SESSION_STAGE_TO_INDEX['mask_classification_preparing_files'])
    session_info = get_session_status(db_conn, session_id)
    print('Working in stage {}'.format(session_info['stage_str']))
    print('Session is {}'.format(session_id))
    create_max_of_frames(db_conn, session_id, config)

    close_connection(db_conn)

    with Connection(redis.from_url(config['REDIS_URL'])):
        q = Queue()
        task = q.enqueue(classify_for_mask, session_id)
        print('Task scheduled for classify_for_mask({})'.format(session_id))

    end_dt = datetime.now()
    delta = end_dt - start_dt
    print('prepare_for_mask for {} took:'.format(session_id), delta)
    return True

def classify_for_mask(session_id):
    print('Started \'classify_for_mask\' for {}'.format(session_id))
    start_dt = datetime.now()
    db_conn = get_db()

    config = get_flask_config()
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

    new_stage = SESSION_STAGE_TO_INDEX['mask_classification_in_progress']
    set_session_stage_to(db_conn, session_id, new_stage)
    print('\'classify_for_mask\' is in stage {}'.format(new_stage))

    classify_files_for_mask(db_conn, session_id, config)

    new_stage = SESSION_STAGE_TO_INDEX['mask_classification_completed']
    set_session_stage_to(db_conn, session_id, new_stage)
    print('\'classify_for_mask\' is in stage {}'.format(new_stage))
    
    close_connection(db_conn)
    end_dt = datetime.now()
    delta = end_dt - start_dt
    print('classify_for_mask for {} took:'.format(session_id), delta)
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
    obj['session_id'] = row.get('session_id')
    obj['file_stage'] = row.get('file_stage')
    obj['max_frame_path'] = row.get('max_frame_path')
    obj['dicom_path'] = path
    obj['base_name'] = os.path.splitext(os.path.basename(path))[0]
    obj['is_error'] = False
    obj['break_processing'] = False

    return obj

def save_file_stage(iter_element, options, db_conn, stage):
    for ie in iter_element:
        element = ie
        file_id = element.file_id
        element.file_stage = stage

        upsert_db(db_conn
                , 'UPDATE files SET file_stage = ? WHERE id = ?'
                , [element.file_stage, file_id])
        
        yield element

def save_file_stage_internal(element, options, db_conn, stage):
    if options['SHOW_DEBUG_MESSAGES']:
        print('save_file_stage_internal: ', element['id'])
    file_id = element['id']
    element['file_stage'] = stage

    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ? WHERE id = ?'
            , [element['file_stage'], file_id])
    
    return element

def save_max_frame_path(iter_element, options, db_conn):
    for ie in iter_element:
        element = ie
        file_id = element.file_id
        element.file_stage = FILE_STAGE_TO_INDEX['has_max_frame']
        #get file id and mask_path
        upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, max_frame_path = ? WHERE id = ?'
                , [element.file_stage, element.max_frame_path, file_id])
        
        yield element

def save_max_frame_path_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_mask_path_internal: ', element['id'], element['max_frame_path'])
    file_id = element['id']
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_max_frame']
    #get file id and mask_path
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, max_frame_path = ? WHERE id = ?'
            , [element['file_stage'], element['max_frame_path'], file_id])
    
    return element

def save_mask_path(iter_element, options, db_conn):
    for ie in iter_element:
        element = ie
        file_id = element.file_id
        element.file_stage = FILE_STAGE_TO_INDEX['has_mask_result']
        #get file id and mask_path
        upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, mask_path = ? WHERE id = ?'
                , [element.file_stage, element.mask_path, file_id])
        
        yield element

def save_mask_path_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_mask_path_internal: ', element['id'], element['mask_path'])
    file_id = element['id']
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_mask_result']
    #get file id and mask_path
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, mask_path = ? WHERE id = ?'
            , [element['file_stage'], element['mask_path'], file_id])
    
    return element


def create_max_of_frames(db_conn, session_id, config):
    relative_session_dir = './'+str(session_id)
    local_processing_session_dir = os.path.join(config['PROCESSING_DIR'], relative_session_dir)
    
    options = {}
    options['FRAME_SIZE'] = config['CLASSIFICATION_MASK_SIZE']
    options['CONVERT_TO_GRAY'] = config['CONVERT_TO_GRAY']
    options['PERSIST_FRAMES'] = config['PERSIST_FRAMES']
    options['PERSIST_FRAMES_DIRPATH'] =  os.path.join(local_processing_session_dir, config['PROCESSING_FRAME_DIR'])
    options['PERSIST_MAXFRAME_DIRPATH'] =  os.path.join(local_processing_session_dir, config['PROCESSING_MAXFRAME_DIR'])
    options['SHOW_DEBUG_MESSAGES'] = False

    os.mkdir(options['PERSIST_FRAMES_DIRPATH'])
    os.mkdir(options['PERSIST_MAXFRAME_DIRPATH'])

    if options['SHOW_DEBUG_MESSAGES']:
        count = query_db(db_conn
            ,'SELECT count(*) as count FROM files where session_id = ? and file_stage = ?', [session_id, FILE_STAGE_TO_INDEX['has_relevance_result']], one=True)

        print('Count ({}): '.format(session_id), count)

    for row in query_db(db_conn, 'SELECT id, processing_path FROM files where session_id = ? and relevance_result = ?', [session_id, 'YES']):
        element = {}
        element = dbrecord_to_object_internal(row, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 1 failure', element)
            continue

        element = get_max_of_frames_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 2 failure', element)
            continue

        # element = save_max_frame_element_internal(element, options)
        # if (element['break_processing']):
        #     #record reason
        #     if options['SHOW_DEBUG_MESSAGES']:
        #         print('Step 3 failure', element)
        #     continue

        element = save_max_frame_path_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 4 failure', element)
            continue  
    return True


def classify_files_for_mask(db_conn, session_id, config):
    options = {}
    options['SHOW_DEBUG_MESSAGES'] = False

    segmentation_model = get_segmentation_inference_model(config['SEGMENTATION_MODEL_FILE'], options)
    if segmentation_model is None:
        print('Error loading PyTorch model')
        return

    local_processing_session_dir = os.path.join(config['PROCESSING_DIR'], './'+str(session_id))
    
    options['FRAME_SIZE'] = config['FRAME_SIZE']
    options['CLASSIFICATION_MASK_SIZE'] = config['CLASSIFICATION_MASK_SIZE']
    options['SEGMENTATION_MODEL'] = segmentation_model
    options['PERSIST_FRAMES_DIRPATH'] =  os.path.join(local_processing_session_dir, config['PROCESSING_FRAME_DIR'])
    options['MASKS_TARGET_PATH'] = os.path.join(local_processing_session_dir, config['PROCESSING_MASK_DIR'])
    options['PERSIST_SEGMENTED_FRAMES_DIRPATH'] = os.path.join(local_processing_session_dir, config['PROCESSING_SEGMENTED_DIR'])
    options['SHOW_DEBUG_MESSAGES'] = False

    os.mkdir(options['MASKS_TARGET_PATH'])

    if options['SHOW_DEBUG_MESSAGES']:
        count = query_db(db_conn
            ,'SELECT count(*) as count FROM files where session_id = ? and file_stage = ?', [session_id, FILE_STAGE_TO_INDEX['has_max_frame']], one=True)

        print('Count ({}): '.format(session_id), count)

    for row in query_db(db_conn, 'SELECT id, processing_path, session_id, file_stage, max_frame_path FROM files where session_id = ? and relevance_result = ?', [session_id, 'YES']):       
        element = {}
        element = dbrecord_to_object_internal(row, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 1 failure', element)
            continue

        element = get_mask_for_dicom_internal(element, options)
        if (element['break_processing']):
            if options['SHOW_DEBUG_MESSAGES']:
                    print('Step 2 failure', element)
            continue

        element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['has_mask_frame'])
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 3 failure', element)
            continue
        
        element = save_mask_resized_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 4 failure', element)
            continue
        
        element = save_mask_path_internal(element, options, db_conn)
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



        


