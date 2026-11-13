# ZZC: 本模块实现轻量级 Action/Filter 钩子机制，供插件注册并在业务流程中执行。
import logging

logger = logging.getLogger(__name__)

# ZZC: 全局钩子注册表以钩子名为键，每个钩子可保存多个回调。
_hooks = {}


# ZZC: 注册回调前确保对应列表存在，并追加 callback。
def register(hook_name: str, callback: callable):
    """
    注册一个钩子回调。
    """
    if hook_name not in _hooks:
        _hooks[hook_name] = []
    _hooks[hook_name].append(callback)
    logger.debug(f"Registered hook '{hook_name}' with callback '{callback.__name__}'")


# ZZC: Action Hook 只执行回调并忽略返回值，单个回调异常不会中断后续回调。
def run_action(hook_name: str, *args, **kwargs):
    """
    执行一个 Action Hook。
    它会按顺序执行所有注册到该钩子上的回调函数。
    """
    if hook_name in _hooks:
        logger.debug(f"Running action hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error running action hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)


# ZZC: Filter Hook 将上一次回调结果传给下一次回调，从而形成处理链。
def apply_filters(hook_name: str, value, *args, **kwargs):
    """
    执行一个 Filter Hook。
    它会把 value 依次传递给所有注册的回调函数进行处理。
    """
    if hook_name in _hooks:
        logger.debug(f"Applying filter hook '{hook_name}'")
        for callback in _hooks[hook_name]:
            try:
                value = callback(value, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error applying filter hook '{hook_name}' callback '{callback.__name__}': {e}", exc_info=True)
    return value
