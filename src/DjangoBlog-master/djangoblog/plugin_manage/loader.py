# ZZC: 本模块根据 settings.ACTIVE_PLUGINS 动态加载并初始化插件模块。
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ZZC: _loaded_plugins 保存当前进程已成功导入的插件实例。
_loaded_plugins = []

# ZZC: 清理旧注册表后逐个校验目录和 plugin.py，再导入插件实例。
def load_plugins():
    """
    Dynamically loads and initializes plugins from the 'plugins' directory.
    This function is intended to be called when the Django app registry is ready.
    """
    global _loaded_plugins
    _loaded_plugins = []

    # ZZC: 插件通过 plugin.py 中的 plugin 对象暴露实例，目录必须位于 PLUGINS_DIR。
    for plugin_name in settings.ACTIVE_PLUGINS:
        plugin_path = os.path.join(settings.PLUGINS_DIR, plugin_name)
        if os.path.isdir(plugin_path) and os.path.exists(os.path.join(plugin_path, 'plugin.py')):
            try:
                # 导入插件模块
                plugin_module = __import__(f'plugins.{plugin_name}.plugin', fromlist=['plugin'])

                # 获取插件实例
                if hasattr(plugin_module, 'plugin'):
                    plugin_instance = plugin_module.plugin
                    _loaded_plugins.append(plugin_instance)
                    logger.info(f"Successfully loaded plugin: {plugin_name} - {plugin_instance.PLUGIN_NAME}")
                else:
                    logger.warning(f"Plugin {plugin_name} does not have 'plugin' instance")

            except ImportError as e:
                logger.error(f"Failed to import plugin: {plugin_name}", exc_info=e)
            except AttributeError as e:
                logger.error(f"Failed to get plugin instance: {plugin_name}", exc_info=e)
            except Exception as e:
                logger.error(f"Unexpected error loading plugin: {plugin_name}", exc_info=e)

    # ZZC: 返回本次加载结果，方便启动阶段记录或测试插件配置。
    return _loaded_plugins

# ZZC: 获取全部已加载插件实例，供系统级遍历和调试使用。
def get_loaded_plugins():
    """获取所有已加载的插件"""
    return _loaded_plugins

# ZZC: 按插件名称查找实例；找不到时返回 None。
def get_plugin_by_name(plugin_name):
    """根据名称获取插件"""
    for plugin in _loaded_plugins:
        if plugin.plugin_slug == plugin_name:
            return plugin
    return None

# ZZC: 按目录标识 slug 查找插件，模板和静态资源通常依赖该标识。
def get_plugin_by_slug(plugin_slug):
    """根据slug获取插件"""
    for plugin in _loaded_plugins:
        if plugin.plugin_slug == plugin_slug:
            return plugin
    return None

# ZZC: 汇总插件元数据，供插件信息展示接口使用。
def get_plugins_info():
    """获取所有插件的信息"""
    return [plugin.get_plugin_info() for plugin in _loaded_plugins]

# ZZC: 筛选支持指定页面位置的插件，再交给渲染层统一处理。
def get_plugins_by_position(position):
    """获取支持指定位置的插件"""
    return [plugin for plugin in _loaded_plugins if position in plugin.SUPPORTED_POSITIONS]
