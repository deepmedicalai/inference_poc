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
    INCOMING_DIR = '/Users/dmitry/Documents/_projects/meeyana/usb2/main/test/incoming'
    PROCESSING_DIR = '/Users/dmitry/Documents/_projects/meeyana/usb2/main/test/processing'

    CLASSIFICATION_RELEVANCE_SIZE = 48    #IMG_WIDTH IMG_HEIGHT
    RELEVANCE_MODEL_FILE = '/Users/dmitry/Documents/_projects/meeyana/usb2/main/tfmodels/dicom_rel_q_v1.tflite'
    RELEVANCE_FRAME_SUFFIX = '_rel48_v1'




class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    WTF_CSRF_ENABLED = False

class DeviceDevelopmentConfig(DevelopmentConfig):
    INCOMING_DIR = './test/incoming'
    PROCESSING_DIR = './test/processing'
    RELEVANCE_MODEL_FILE = './tfmodels/dicom_rel_q_v1.tflite'

class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False