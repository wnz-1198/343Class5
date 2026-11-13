# ZZC: 本模块集中定义插件系统和页面渲染位置使用的钩子名称。

# ZZC: 文章生命周期钩子，用于在创建、修改、删除和加载文章时触发插件。
ARTICLE_DETAIL_LOAD = 'article_detail_load'
ARTICLE_CREATE = 'article_create'
ARTICLE_UPDATE = 'article_update'
ARTICLE_DELETE = 'article_delete'

ARTICLE_CONTENT_HOOK_NAME = "the_content"

# ZZC: 位置钩子把插件组件映射到文章、侧边栏、页头页脚和评论区。
POSITION_HOOKS = {
    'article_top': 'article_top_widgets',
    'article_bottom': 'article_bottom_widgets',
    'sidebar': 'sidebar_widgets',
    'header': 'header_widgets',
    'footer': 'footer_widgets',
    'comment_before': 'comment_before_widgets',
    'comment_after': 'comment_after_widgets',
}

# ZZC: 资源注入钩子用于向 head 或 body 末尾追加插件静态资源。
HEAD_RESOURCES_HOOK = 'head_resources'
BODY_RESOURCES_HOOK = 'body_resources'

