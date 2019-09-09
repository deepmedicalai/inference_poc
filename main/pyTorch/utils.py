import torch
from torchvision import transforms

class CustomToImageTensor(transforms.ToTensor):
    """
    Extension of original ToTensor but applying to an image property only
    """
    def __init__(self):
        super(CustomToImageTensor, self).__init__()
        
    def __call__(self, sample):
        image = sample['image']
        
        image_tensor = super().__call__(image)
        return {'image': image_tensor}
    
class CustomToVideoTensor(transforms.ToTensor):
    """
    Extension of original ToTensor but applying to an image property only
    """
    def __init__(self):
        super(CustomToVideoTensor, self).__init__()
        
    def __call__(self, sample):
        frames = sample['image']

        frames_tensor = torch.tensor(frames, dtype=torch.float32)
        return {'image': frames_tensor}

class CustomNormalize(transforms.Normalize):
    """
    Extension of original Normalize but applying to an image property only
    
    """
    def __init__(self, mean, std, inplace=False):
        super(CustomNormalize, self).__init__(mean, std, inplace)
        
    def __call__(self, sample):
        image_tensor = sample['image']
        
        normalized_image_tensor = super().__call__(image_tensor)
        
        return {'image': normalized_image_tensor}