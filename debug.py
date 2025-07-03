from file import test_all
from image import test_func, test_class
from logger import setup_logger, logger

setup_logger(level="DEBUG", output_file="debug.log")
# setup_logger(level="INFO", output_file="debug.log")

logger.info('main info')
logger.debug('main debug')
logger.error('main error')
logger.warning('main warning')
logger.critical('main critical')

test_all()
img_path = 'https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg'
test_func(img_path)
test_class(img_path)