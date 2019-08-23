#pydicom
import pydicom
from pydicom.pixel_data_handlers import gdcm_handler #pillow_handler #, gdcm_handler
from pydicom.filereader import read_dicomdir, InvalidDicomError

#imaging 
import cv2
from PIL import Image

#tf
import numpy as np
import tensorflow as tf

#files
from os import listdir, walk
from os.path import basename, dirname, join, exists, isfile, getsize, splitext
import tempfile
import json
import copy

VALID_IMAGE_TYPES = ['1.2.840.10008.5.1.4.1.1.3.1','1.2.840.10008.5.1.4.1.1.6.1']
DICOMDIR_UID = '1.2.840.10008.1.3.10'
TYPES = ['.dcm', '']

def get_relevance_inference_interpreter(relevance_model_path, options):
    
    # init relevance model
    relevance_interpreter = tf.lite.Interpreter(model_path=relevance_model_path)
    relevance_interpreter.allocate_tensors()

    # Get input and output tensors.
    relevance_input_details = relevance_interpreter.get_input_details()
    relevance_output_details = relevance_interpreter.get_output_details()

    return relevance_interpreter, relevance_input_details, relevance_output_details

def get_segmentation_inference_interpreter(segmentation_model_path, options):
    # init segmentation model
    segmentation_interpreter = tf.lite.Interpreter(model_path=segmentation_model_path)
    
    # Get input and output tensors.
    segmentation_input_details = segmentation_interpreter.get_input_details()
    segmentation_output_details = segmentation_interpreter.get_output_details()

    # "segmentation_input_shape = segmentation_input_details[0]['shape']"
    return segmentation_interpreter, segmentation_input_details, segmentation_output_details

#color convert
def get_pixel_array_rgb(ds):
    if ds.PhotometricInterpretation in ['YBR_FULL', 'YBR_FULL_422']:
        return convert_ybr_to_rgb(ds.pixel_array)
    if ds.PhotometricInterpretation in ['MONOCHROME1', 'MONOCHROME2']:
        return convert_to_three_channels(ds.pixel_array)

    return ds.pixel_array
    
def convert_frame_to_rgb(frame, pi):
    if pi in ['YBR_FULL', 'YBR_FULL_422']:
        frame = convert_ybr_to_rgb(frame)   
    return frame

def convert_ybr_to_rgb(arr):
    if len(arr.shape) == 4:
        return np.vstack([convert_ybr_to_rgb(a)[np.newaxis] for a in arr])
    else:
        temp = arr[..., 1].copy()
        arr[..., 1] = arr[..., 2]
        arr[..., 2] = temp
        return cv2.cvtColor(arr, cv2.COLOR_YCR_CB2RGB)

def convert_to_three_channels(arr):
    return np.stack((arr,)*3, axis=-1)

def convert_to_grayscale(frame):
    return np.dot(frame[...,:3], [0.2989, 0.5870, 0.1140])

def get_frames_num(ds):
    try:
        return ds.NumberOfFrames
    except:
        return 0
    
def get_frame_rate(ds):
    frame_inc_pnt = ds.FrameIncrementPointer  #(0028, 0009) Frame Increment Pointer
    if frame_inc_pnt == (0x0018,0x1063):
        #Frame Time (0018,1063)
        frame_rate = round(ds[0x0018,0x1063].value, 2)
    else:
        #Frame Time Vector (0018,1065)
        frame_rate = ds[0x0018,0x1065].value
        frame_rate = round(sum(frame_rate) / len(frame_rate), 2)
    return frame_rate

def save_frame(dicom_path, image_dirpath, image_name, frame_data):
    filename = splitext(basename(dicom_path))[0]
    image_path = join(dirname(image_dirpath), image_name.format(filename))
    cv2.imwrite(image_path, frame_data)
    return image_path
    
def resize(frame, w, h, interpolation_type = cv2.INTER_AREA):
    return cv2.resize(frame,(w,h),interpolation=interpolation_type)


def create_frame(ds, frame_size, convert_to_gray):    
    frames_num = get_frames_num(ds)
    if frames_num == 0:
        frame = ds.pixel_array
    else:        
        frame = ds.pixel_array[0,:,:,:]

    frame = convert_frame_to_rgb(frame, ds.PhotometricInterpretation)
    frame = resize(frame, frame_size, frame_size)      

    frame_gray = None
    if convert_to_gray and frame.ndim == 3:
        frame_gray = convert_to_grayscale(frame)
        
    return frame, frame_gray
            
# copy to temp folder
def get_temp_directory(target_dir):
    temp_name = next(tempfile._get_candidate_names())
    return target_dir + temp_name + '/'

def get_temp_file_name(path, filename):
    filepath = path + filename.replace("/", "_")
    return filepath

def apply_mask(frame, mask):
#     if mask.ndim == 3:
#         mask = convert_to_grayscale(mask)
    if frame.shape != mask.shape:
        h, w = frame.shape[:2]
        mask = resize(mask, w, h)

    out_img = cv2.bitwise_and(frame, frame, mask=mask)
    return out_img

def create_mask(pred_mask):
    pred_mask = tf.argmax(pred_mask, axis=-1)
    pred_mask = pred_mask[..., tf.newaxis]
    return pred_mask[0]

#creates an initial version of the object.
def path_to_object(path):
    obj  = lambda: None
    obj.dicom_path = path
    obj.base_name = splitext(basename(path))[0]
    yield obj

def create_frame_for_classification_internal(element, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('create_frame_for_classification: {}'.format(element['id']))
    try:
        ds = pydicom.read_file(element['dicom_path'])
        metadata = ds.file_meta
        element['instance_id'] = metadata.MediaStorageSOPInstanceUID
        if options['SHOW_DEBUG_MESSAGES']:
            print('create_frame_for_classification ->SOPInstanceId: {}->{}'.format(element['id'], metadata.MediaStorageSOPInstanceUID))
        if metadata.MediaStorageSOPClassUID in VALID_IMAGE_TYPES:
            rgb, gray_frame = create_frame(ds, options['CLASSIFICATION_SIZE'], True)
            element['classification_frame'] = gray_frame
            
            element['break_processing'] = False
            element['is_supportedSOP'] = True
            #data[element.instance_id] = { 'dicom': element.dicom_path }
        else:
            print('Unsupported SOP class for {}:{}'.format(element['id'], metadata.MediaStorageSOPClassUID))
            element['error_message'] = 'Not supported SOP class'
            element['break_processing'] = True
            element['is_supportedSOP'] = False

    except IOError:
        element['error_message'] = 'No such file'
        element['is_error'] = True
        element['break_processing'] = True
        print('No such file')

    except InvalidDicomError:
        element['error_message'] = 'Invalid Dicom file'
        element['is_error'] = True
        element['break_processing'] = True
        print('Invalid Dicom file')

    return element

def create_frame_for_classification(iter_element, options):
    for ie in iter_element:
        element = ie
        print('create_frame_for_classification: {}'.format(element.id))
        try:
            ds = pydicom.read_file(element.dicom_path)
            metadata = ds.file_meta
            if metadata.MediaStorageSOPClassUID in VALID_IMAGE_TYPES:
                rgb, gray_frame = create_frame(ds, options['CLASSIFICATION_SIZE'], True)
                element.classification_frame = gray_frame
                element.instance_id = metadata.MediaStorageSOPInstanceUID
                print('create_frame_for_classification: {} frame'.format(element.id))
                #data[element.instance_id] = { 'dicom': element.dicom_path }
                yield element
        except IOError:
            print('No such file')

        except InvalidDicomError:
            print('Invalid Dicom file')

def get_relevance_internal(element, options):

    if options['SHOW_DEBUG_MESSAGES']:
        print('get_relevance_internal: ', element['id'])
    frame = element['classification_frame']
    relevance_model_interpreter = options['RELEVANCE_INTERPRETER']
    relevance_model_inputs = options['RELEVANCE_INTERPRETER_INPUTS']
    relevance_model_outputs = options['RELEVANCE_INTERPRETER_OUTPUTS']

    image_reshaped = frame.reshape(options['RELEVANCE_INPUT_SHAPE'])  #reshape into expected input tensor       
    #print(image.shape, image_gray.shape, image_reshaped.shape)  #for debug purposes

    input_data = np.array(image_reshaped, dtype=np.float32)
    relevance_model_interpreter.set_tensor(relevance_model_inputs[0]['index'], input_data)

    #invoke TF Lite Inference invoker
    relevance_model_interpreter.invoke()

    # The function `get_tensor()` returns a copy of the tensor data.
    # Use `tensor()` in order to get a pointer to the tensor.
    output_data = relevance_model_interpreter.get_tensor(relevance_model_outputs[0]['index'])
    output_index = np.argmax(output_data)
    output_value = np.max(output_data)
    
    element['relevant'] = output_index == 1 and output_value > options['RELEVANCE_THRESHOLD']
    
    #data[element.instance_id]['relevant'] = 1 if element.relevant else 0 #json.dump has troubles with writing of boolean
        
    return element

def get_relevance(iter_element, options):
    for ie in iter_element:
        element = ie
        id_ = element.instance_id
        frame = element.classification_frame
        relevance_model_interpreter = options['RELEVANCE_INTERPRETER']
        relevance_model_inputs = options['RELEVANCE_INTERPRETER_INPUTS']
        relevance_model_outputs = options['RELEVANCE_INTERPRETER_OUTPUTS']

        image_reshaped = frame.reshape(options['RELEVANCE_INPUT_SHAPE'])  #reshape into expected input tensor       
        #print(image.shape, image_gray.shape, image_reshaped.shape)  #for debug purposes

        input_data = np.array(image_reshaped, dtype=np.float32)
        relevance_model_interpreter.set_tensor(relevance_model_inputs[0]['index'], input_data)

        #invoke TF Lite Inference invoker
        relevance_model_interpreter.invoke()

        # The function `get_tensor()` returns a copy of the tensor data.
        # Use `tensor()` in order to get a pointer to the tensor.
        output_data = relevance_model_interpreter.get_tensor(relevance_model_outputs[0]['index'])
        output_index = np.argmax(output_data)
        output_value = np.max(output_data)
        
        element.relevant = output_index == 1 and output_value > options['RELEVANCE_THRESHOLD']
        
        #data[element.instance_id]['relevant'] = 1 if element.relevant else 0 #json.dump has troubles with writing of boolean
        
        if element.relevant:            
            yield element
        else:
            break
    
#calculates max frame color as generator
def get_max_of_frames(iter_element, options):    
    for ie in iter_element:    
        path = ie.dicom_path
        element = ie

        if not element.relevant:
            element.max_frame = None
            yield element
        else:
            opt_frame_size = options['FRAME_SIZE']
            opt_convert_to_gray = options['CONVERT_TO_GRAY']
            opt_persist_frames = options['PERSIST_FRAMES']
            opt_persist_frames_dirpath = options['PERSIST_FRAMES_DIRPATH']

            ds = pydicom.read_file(element.dicom_path)
            frames_num = get_frames_num(ds)
            element.frames_num = frames_num
            if frames_num == 0:
                rgb_frame, max_of_frames = create_frame(ds, opt_frame_size, opt_convert_to_gray)

                #saving frame if necessary
                if opt_persist_frames:
                    img_name = '{}' + '_frame_0.png'
                    save_frame(path, opt_persist_frames_dirpath, img_name, rgb_frame)
            else:
                max_of_frames = None
                cnt = 0

                #convert all frames to RGB
                all_frames = convert_frame_to_rgb(ds.pixel_array, ds.PhotometricInterpretation)

                element.frame_rate = get_frame_rate(ds)
                for frame in all_frames:                
                    _frame = rgb_frame = resize(frame, opt_frame_size, opt_frame_size)

                    if opt_convert_to_gray:
                        _frame = convert_to_grayscale(_frame)

                    #saving frame if necessary
                    if opt_persist_frames:
                        img_name = '{}' + '_frame_{}.png'.format(cnt)   #the first {} will be replaced in save_frame
                        save_frame(path, opt_persist_frames_dirpath, img_name, rgb_frame)

                    if max_of_frames is None:
                        #just for the first frame
                        max_of_frames = _frame
                    else:
                        #calc smax
                        max_of_frames = np.where(max_of_frames < _frame, _frame, max_of_frames)

                    cnt = cnt + 1

            #add property to element object
            element.max_frame = max_of_frames
            yield element

def get_max_of_frames_internal(element, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('get_max_of_frames_internal: ', element['id'])

    opt_frame_size = options['FRAME_SIZE']
    opt_convert_to_gray = options['CONVERT_TO_GRAY']
    opt_persist_frames = options['PERSIST_FRAMES']
    opt_persist_frames_dirpath = options['PERSIST_FRAMES_DIRPATH']

    ds = pydicom.dcmread(element['dicom_path'])
    frames_num = get_frames_num(ds)
    # element.frames_num = frames_num
    if frames_num == 0:
        rgb_frame, max_of_frames = create_frame(ds, opt_frame_size, opt_convert_to_gray)

        #saving frame if necessary
        if opt_persist_frames:
            img_name = '{}' + '_frame_0.png'
            save_frame(element['dicom_path'], opt_persist_frames_dirpath, img_name, rgb_frame)
    else:
        max_of_frames = None
        cnt = 0

        # somehow, it reads the pixel data in right way
        #convert all frames to RGB 
        # all_frames = convert_frame_to_rgb(ds.pixel_array, ds.PhotometricInterpretation)
        for frame in ds.pixel_array:
            _frame = resize(frame, opt_frame_size, opt_frame_size)
            rgb_frame = copy.copy(_frame)        

            if opt_convert_to_gray:
                _frame = convert_to_grayscale(_frame)

            #saving frame if necessary
            if opt_persist_frames:
                img_name = '{}' + '_frame_{}.png'.format(cnt)   #the first {} will be replaced in save_frame
                save_frame(element['dicom_path'], opt_persist_frames_dirpath, img_name, rgb_frame)

            if max_of_frames is None:
                #just for the first frame
                max_of_frames = _frame
            else:
                #calc smax
                max_of_frames = np.where(max_of_frames < _frame, _frame, max_of_frames)

            cnt = cnt + 1

    #add property to element object
    element['max_of_frames'] = max_of_frames
    return element

# generator to save .max_frame property to PNG
def save_max_frame_element(iter_element, options):
    for ie in iter_element:
        max_frame = ie.max_frame
        if max_frame is None:
            yield ie
        else:
            element = ie
            base_name = ie.base_name
            max_frame_dirpath = options['PERSIST_MAXFRAME_DIRPATH']
            file_path = base_name
            img_name = '{}' + '_maxframe_{}.png'.format(options['FRAME_SIZE'])
            
            max_frame_path = save_frame(ie.dicom_path, max_frame_dirpath, img_name, max_frame)
            element.max_frame_path = max_frame_path
            yield element

def save_max_frame_element_internal(element, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('get_max_of_frames_internal: ', element['id'])

    if element['max_of_frames'] is None:
        element['break_processing'] = True
        print('Frame data for mask classification missing {}:{}'.format(element['id'], metadata.MediaStorageSOPClassUID))
        element['error_message'] = 'Frame data for mask classification missing'
        return element

    max_frame_dirpath = options['PERSIST_MAXFRAME_DIRPATH']
    img_name = './{}' + '_maxframe_{}.png'.format(options['FRAME_SIZE'])
    
    max_frame_path = save_frame(element['dicom_path'], max_frame_dirpath, img_name, element['max_of_frames'])
    element['max_frame_path'] = max_frame_path
    return element

            
def get_mask_for_dicom(iter_element, options):
    for ie in iter_element:
        element = ie
        
        if ie.max_frame_path is None:
            yield element
        else:
            id_ = element.instance_id
            max_frame_path = element.max_frame_path
            image_wh = options['SEGMENTATION_FRAME_SIZE']

            #using CV2 to convert PNG path to Numpy
            image = cv2.imread(max_frame_path)
            image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) #into grayscal
            image_resized = resize(image_gray, image_wh, image_wh)        
            image_reshaped = image_resized.reshape(options['SEGMENTATION_INPUT_SHAPE'])  #reshape into expected input tensor
            image_normalized = image_reshaped/255

            input_data = np.array(image_normalized, dtype=np.float32)

            segmentation_interpreter.set_tensor(segmentation_input_details[0]['index'], input_data)

            #invoke TF Lite Inference invoker
            segmentation_interpreter.invoke()

            # The function `get_tensor()` returns a copy of the tensor data.
            # Use `tensor()` in order to get a pointer to the tensor.
            output_data = segmentation_interpreter.get_tensor(segmentation_output_details[0]['index'])

            output_mask = create_mask(output_data)

            element.mask_data = output_mask.numpy()*255
            yield element

def get_mask_for_dicom_internal(element, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('get_mask_for_dicom: ', element['id'])
        
    if element['max_frame_path'] is None:
        element['break_processing'] = True
        print('Max frame is missing {}:{}'.format(element['id'], metadata.MediaStorageSOPClassUID))
        element['error_message'] = 'Max frame is missing'
        return element

    image_wh = options['SEGMENTATION_FRAME_SIZE']
    segmentation_model_interpreter = options['SEGMENTATION_INTERPRETER']
    segmentation_model_inputs = options['SEGMENTATION_INTERPRETER_INPUTS']
    segmentation_model_outputs = options['SEGMENTATION_INTERPRETER_OUTPUTS']

    #using CV2 to convert PNG path to Numpy
    image = cv2.imread(element['max_frame_path'])
    image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) #into grayscal
    image_resized = resize(image_gray, image_wh, image_wh)
    image_reshaped = image_resized.reshape(options['SEGMENTATION_INPUT_SHAPE'])  #reshape into expected input tensor
    image_normalized = image_reshaped/255

    input_data = np.array(image_normalized, dtype=np.float32)

    segmentation_model_interpreter.set_tensor(segmentation_model_inputs[0]['index'], input_data)
    #invoke TF Lite Inference invoker
    segmentation_model_interpreter.invoke()

    # The function `get_tensor()` returns a copy of the tensor data.
    # Use `tensor()` in order to get a pointer to the tensor.
    output_data = segmentation_model_interpreter.get_tensor(segmentation_model_outputs[0]['index'])
    output_mask = create_mask(output_data)
    element['mask_data'] = output_mask.numpy()*255
    return element 

            
def save_mask_resized(iter_element, options):
    for ie in iter_element:
        element = ie
        mask_data = element.mask_data
        
        if mask_data is None:
            yield ie        
        else:
            id_ = element.base_name
            opt_masks_target_path = options['MASKS_TARGET_PATH']
            img_wh = options['FRAME_SIZE']
            base_name = element.base_name
            # at this stage error occurs, but resize will be executed anyway during applying of mask
            # resized_mask = resize(mask_data, img_wh, img_wh)
            #save mask
            mask_img_name = '{}_mask_{}.png'.format(base_name, img_wh)
            image_path = join(dirname(opt_masks_target_path),mask_img_name)
            cv2.imwrite(image_path, mask_data)

            element.mask_path = image_path
            #data[element.instance_id]['mask_path'] = element.mask_path

            yield element

def save_mask_resized_internal(element, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('get_mask_for_dicom: ', element['id'])
        
    if element['mask_data'] is None:
        element['break_processing'] = True
        print('Mask image data is missing {}:{}'.format(element['id'], metadata.MediaStorageSOPClassUID))
        element['error_message'] = 'Mask image data is missing'
        return element

    opt_masks_target_path = options['MASKS_TARGET_PATH']
    img_wh = options['FRAME_SIZE']
    # at this stage error occurs, but resize will be executed anyway during applying of mask
    # resized_mask = resize(mask_data, img_wh, img_wh)
    #save mask
    mask_img_name = '{}_mask_{}.png'.format(element['base_name'], img_wh)
    image_path = join(dirname(opt_masks_target_path), mask_img_name)
    cv2.imwrite(image_path, mask_data)

    element['mask_path'] = image_path
    return element
                
def apply_mask_to_frames(iter_element, options):
    for ie in iter_element:
        element = ie
        
        if element.mask_path is None:
            yield element
        else:
            base_name = element.base_name
            path = element.dicom_path
            frames_num = element.frames_num

            opt_frame_size = options['FRAME_SIZE']
            opt_masks_target_path = options['MASKS_TARGET_PATH']
            opt_persist_frames_dirpath = options['PERSIST_FRAMES_DIRPATH']
            opt_persist_segmented_frames_dirpath = options['PERSIST_SEGMENTED_FRAMES_DIRPATH']
            frame_size = options['FRAME_SIZE']

            mask_data = np.array(Image.open(element.mask_path))
    #         mask_data = cv2.imread(element.mask_path)
            if frames_num == 0:
                img_path = join(opt_persist_frames_dirpath,'{}_frame_0.png'.format(base_name))
                frame_data = cv2.imread(img_path)
                element.img_path = img_path
                out_img = apply_mask(frame_data, mask_data)
                img_name = '{}_frame_0.png'
                save_frame(path, opt_persist_segmented_frames_dirpath, img_name, out_img)
            else:
                for num in range(frames_num):
                    img_path = join(opt_persist_frames_dirpath,'{}_frame_{}.png'.format(element.base_name, num))
                    frame_data = cv2.imread(img_path)               
                    out_img = apply_mask(frame_data, mask_data)

                    img_name = '{}' + '_frame_{}.png'.format(num)
                    save_frame(path, opt_persist_segmented_frames_dirpath, img_name, out_img)
            yield element
        
def create_clips(iter_element, options):
    for ie in iter_element:
        element = ie
        frames_num = element.frames_num
        
        if frames_num == 0 and element.mask_path:
            yield element
        else:
            opt_persist_segmented_frames_dirpath = options['PERSIST_SEGMENTED_FRAMES_DIRPATH']
            opt_persist_clips_dirpath = options['PERSIST_CLIPS_DIRPATH']
            frame_wh= options['FRAME_SIZE']
            fps = element.frame_rate
            base_name = element.base_name

            clip_path = join(opt_persist_clips_dirpath,'{0}_clip.avi'.format(base_name)) 
            fourcc = cv2.VideoWriter_fourcc(*'XVID')

            video = cv2.VideoWriter(clip_path, fourcc, fps, (frame_wh, frame_wh))
            for num in range(frames_num):
                img_path = join(opt_persist_segmented_frames_dirpath,'{}_frame_{}.png'.format(base_name, num))
                img = cv2.imread(img_path, cv2.COLOR_BGR2RGB)
                video.write(img)
            video.release()

            yield element