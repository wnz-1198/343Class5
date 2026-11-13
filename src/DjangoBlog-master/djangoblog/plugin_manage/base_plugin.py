# ZZC: 本模块定义插件基类，统一插件元数据、位置渲染、模板和静态资源访问接口。
import logging
from pathlib import Path

from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


# ZZC: BasePlugin 是各业务插件的父类，子类通过重写钩子和渲染方法扩展博客。
class BasePlugin:
    # 插件元数据
    PLUGIN_NAME = None
    PLUGIN_DESCRIPTION = None
    PLUGIN_VERSION = None
    PLUGIN_AUTHOR = None

    # 插件配置
    SUPPORTED_POSITIONS = []  # 支持的显示位置
    DEFAULT_PRIORITY = 100  # 默认优先级（数字越小优先级越高）
    POSITION_PRIORITIES = {}  # 各位置的优先级 {'sidebar': 50, 'article_bottom': 80}

    # ZZC: 初始化时校验必要元数据，定位插件目录，并执行子类初始化与钩子注册。
    def __init__(self):
        if not all([self.PLUGIN_NAME, self.PLUGIN_DESCRIPTION, self.PLUGIN_VERSION]):
            raise ValueError("Plugin metadata (PLUGIN_NAME, PLUGIN_DESCRIPTION, PLUGIN_VERSION) must be defined.")

        # 设置插件路径
        self.plugin_dir = self._get_plugin_directory()
        self.plugin_slug = self._get_plugin_slug()

        self.init_plugin()
        self.register_hooks()

    # ZZC: 通过类定义所在文件定位插件目录，避免依赖调用方的工作目录。
    def _get_plugin_directory(self):
        """获取插件目录路径"""
        import inspect
        plugin_file = inspect.getfile(self.__class__)
        return Path(plugin_file).parent

    # ZZC: 使用插件目录名作为稳定标识，用于模板和静态资源路径拼接。
    def _get_plugin_slug(self):
        """获取插件标识符（目录名）"""
        return self.plugin_dir.name

    # ZZC: 子类可重写初始化逻辑；基类默认只记录插件已初始化。
    def init_plugin(self):
        """
        插件初始化逻辑
        子类可以重写此方法来实现特定的初始化操作
        """
        logger.info(f'{self.PLUGIN_NAME} initialized.')

    # ZZC: 子类在此把回调注册到系统钩子；默认插件没有钩子。
    def register_hooks(self):
        """
        注册插件钩子
        子类可以重写此方法来注册特定的钩子
        """
        pass

    # === 位置渲染系统 ===
    # ZZC: 根据位置检查支持范围和显示条件，再动态调用对应 render_*_widget 方法。
    def render_position_widget(self, position, context, **kwargs):
        """
        根据位置渲染插件组件
        
        Args:
            position: 位置标识
            context: 模板上下文
            **kwargs: 额外参数
            
        Returns:
            dict: {'html': 'HTML内容', 'priority': 优先级} 或 None
        """
        if position not in self.SUPPORTED_POSITIONS:
            return None

        # 检查条件显示
        if not self.should_display(position, context, **kwargs):
            return None

        # 调用具体的位置渲染方法
        method_name = f'render_{position}_widget'
        if hasattr(self, method_name):
            html = getattr(self, method_name)(context, **kwargs)
            if html:
                priority = self.POSITION_PRIORITIES.get(position, self.DEFAULT_PRIORITY)
                return {
                    'html': html,
                    'priority': priority,
                    'plugin_name': self.PLUGIN_NAME
                }

        return None

    # ZZC: 默认所有组件都显示，子类可根据请求上下文添加条件。
    def should_display(self, position, context, **kwargs):
        """
        判断插件是否应该在指定位置显示
        子类可重写此方法实现条件显示逻辑
        
        Args:
            position: 位置标识
            context: 模板上下文
            **kwargs: 额外参数
            
        Returns:
            bool: 是否显示
        """
        return True

    # ZZC: 以下 render 方法定义插件可插入的页面位置，子类按需覆盖。
    def render_sidebar_widget(self, context, **kwargs):
        """渲染侧边栏组件"""
        return None

    # ZZC: 子类可重写此方法，在文章底部渲染插件组件。
    def render_article_bottom_widget(self, context, **kwargs):
        """渲染文章底部组件"""
        return None

    # ZZC: 子类可重写此方法，在文章顶部渲染插件组件。
    def render_article_top_widget(self, context, **kwargs):
        """渲染文章顶部组件"""
        return None

    # ZZC: 子类可重写此方法，在页头位置渲染插件组件。
    def render_header_widget(self, context, **kwargs):
        """渲染页头组件"""
        return None

    # ZZC: 子类可重写此方法，在页脚位置渲染插件组件。
    def render_footer_widget(self, context, **kwargs):
        """渲染页脚组件"""
        return None

    # ZZC: 子类可重写此方法，在评论区前方渲染插件组件。
    def render_comment_before_widget(self, context, **kwargs):
        """渲染评论前组件"""
        return None

    # ZZC: 子类可重写此方法，在评论区后方渲染插件组件。
    def render_comment_after_widget(self, context, **kwargs):
        """渲染评论后组件"""
        return None

    # === 模板系统 ===
    # ZZC: 渲染插件模板；模板缺失时返回空字符串，避免单个插件破坏整页。
    def render_template(self, template_name, context=None):
        """
        渲染插件模板
        
        Args:
            template_name: 模板文件名
            context: 模板上下文
            
        Returns:
            HTML字符串
        """
        if context is None:
            context = {}

        template_path = f"plugins/{self.plugin_slug}/{template_name}"

        try:
            return render_to_string(template_path, context)
        except TemplateDoesNotExist:
            logger.warning(f"Plugin template not found: {template_path}")
            return ""

    # === 静态资源系统 ===
    # ZZC: 统一生成插件静态文件 URL，子类无需重复拼接路径。
    def get_static_url(self, static_file):
        """获取插件静态文件URL"""
        from django.templatetags.static import static
        return static(f"{self.plugin_slug}/static/{self.plugin_slug}/{static_file}")

    # ZZC: 子类通过这两个方法声明需要加载的 CSS 和 JavaScript 文件。
    def get_css_files(self):
        """获取插件CSS文件列表"""
        return []

    # ZZC: 子类通过此方法声明插件需要加载的 JavaScript 文件。
    def get_js_files(self):
        """获取插件JavaScript文件列表"""
        return []

    # ZZC: 返回需在 head 早期阻塞加载的关键 HTML，用于防闪烁等场景。
    def get_critical_head_html(self, context=None):
        """
        获取需要在<head>最早执行的关键HTML内容（阻塞式加载）

        用于防闪烁脚本等必须在页面渲染前执行的关键代码。
        此方法返回的内容会在所有CSS和其他资源之前加载。

        注意：此方法应该只用于真正需要阻塞加载的关键资源，
        普通资源请使用 get_head_html()
        """
        return ""

    # ZZC: 返回在 CSS 之后插入 head 的插件 HTML。
    def get_head_html(self, context=None):
        """获取需要插入到<head>中的HTML内容（在CSS之后）"""
        return ""

    # ZZC: 返回在 body 底部插入的插件 HTML。
    def get_body_html(self, context=None):
        """获取需要插入到<body>底部的HTML内容"""
        return ""

    # ZZC: 返回插件元数据和运行时目录，供插件管理页面展示。
    def get_plugin_info(self):
        """
        获取插件信息
        :return: 包含插件元数据的字典
        """
        return {
            'name': self.PLUGIN_NAME,
            'description': self.PLUGIN_DESCRIPTION,
            'version': self.PLUGIN_VERSION,
            'author': self.PLUGIN_AUTHOR,
            'slug': self.plugin_slug,
            'directory': str(self.plugin_dir),
            'supported_positions': self.SUPPORTED_POSITIONS,
            'priorities': self.POSITION_PRIORITIES
        }
