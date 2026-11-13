# ZZC: 本模块负责 djangoblog 项目的应用初始化，并在应用就绪后加载插件。
from django.apps import AppConfig


# ZZC: DjangoblogAppConfig 使用 BigAutoField 作为默认主键，并注册插件加载入口。
class DjangoblogAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'djangoblog'

    # ZZC: Django 完成应用注册后调用 ready()，此时可以安全导入并初始化插件。
    def ready(self):
        super().ready()
        # ZZC: 延迟导入可避免插件模块在应用注册完成前加载，减少循环依赖风险。
        from .plugin_manage.loader import load_plugins
        load_plugins()
