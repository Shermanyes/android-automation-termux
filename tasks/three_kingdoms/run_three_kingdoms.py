import os
import sys
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# 设置日志
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"three_kingdoms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('three_kingdoms')

def run_three_kingdoms_task():
    """运行三国杀任务"""
    try:
        from main_task import ThreeKingdomsTask
        
        # 创建任务实例
        task = ThreeKingdomsTask(
            task_id="three_kingdoms_daily",
            name="三国杀日常任务",
            app_id="three_kingdoms"
        )
        
        # 初始化任务
        if not task.initialize():
            logger.error("任务初始化失败")
            return False
            
        # 执行任务
        result = task.execute()
        
        logger.info(f"任务执行{'成功' if result else '失败'}")
        return result
        
    except Exception as e:
        logger.error(f"运行任务出错: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("开始三国杀日常任务")
    run_three_kingdoms_task()
    logger.info("三国杀日常任务结束")
