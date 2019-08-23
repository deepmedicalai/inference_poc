# project/server/config.py

import os
basedir = os.path.abspath(os.path.dirname(__file__))


class BaseConfig(object):
    """Base configuration."""
    WTF_CSRF_ENABLED = True
    REDIS_URL = 'redis://localhost:6379/0'
    DATABASE = './database/database.db'
    QUEUES = ['default']
    STATIC_FOLDER = './webclient/dist'
    SECRET_KEY = 'super_secret_key'
    INCOMING_DIR = './test/incoming'
    PROCESSING_DIR = './test/processing'

    CLASSIFICATION_RELEVANCE_SIZE = 48    #IMG_WIDTH IMG_HEIGHT
    RELEVANCE_MODEL_FILE = './tfmodels/dicom_rel_q_v1.tflite'
    RELEVANCE_FRAME_SUFFIX = '_rel48_v1'

    FRAME_SIZE = 512
    CLASSIFICATION_MASK_SIZE = 128
    CONVERT_TO_GRAY = True
    PERSIST_FRAMES = False
    SEGMENTATION_MODEL_FILE = './tfmodels/dicom_mask_v1.tflite'
    
    PROCESSING_MASK_DIR = './masks/'
    PROCESSING_FRAME_DIR = './frames/'
    PROCESSING_MAXFRAME_DIR = './maxframe/'
    PROCESSING_SEGMENTED_DIR = './segmented/'


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    WTF_CSRF_ENABLED = False


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False