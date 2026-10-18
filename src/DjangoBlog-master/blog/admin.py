# blog 应用的后台管理配置
# ---------------------------------------------------------------------------
# 本文件定义 6 个 ModelAdmin（对应 blog/models.py 的 6 个模型）与 4 个批量操作。
# 站长日常的发布/下架文章、维护分类标签、维护友情链接与全站配置都在这里完成。
#
# 重要：本文件只"定义"Admin 类，并没有调用 admin.site.register()。
#      真正的注册动作在 djangoblog/admin_site.py 中通过自定义 admin 站点完成
#      （项目启用的是自定义 admin_site，而非 Django 默认的 admin.site）。
# ---------------------------------------------------------------------------
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# Register your models here.
from .models import Article, Category, Tag, Links, SideBar, BlogSettings


# 文章的后台表单：直接暴露模型的全部字段（Markdown 正文由 MDTextField 提供编辑器）
class ArticleForm(forms.ModelForm):
    # body = forms.CharField(widget=AdminPagedownWidget())

    class Meta:
        model = Article
        fields = '__all__'


# ===== 批量操作（admin actions，作用于列表页勾选的多篇文章）=====

# 批量发布：把选中文章的状态置为 'p'（Published）
def makr_article_publish(modeladmin, request, queryset):
    queryset.update(status='p')


# 批量转草稿：把选中文章的状态置为 'd'（Draft）
def draft_article(modeladmin, request, queryset):
    queryset.update(status='d')


# 批量关闭评论：把选中文章的 comment_status 置为 'c'（Close）
def close_article_commentstatus(modeladmin, request, queryset):
    queryset.update(comment_status='c')


# 批量开放评论：把选中文章的 comment_status 置为 'o'（Open）
def open_article_commentstatus(modeladmin, request, queryset):
    queryset.update(comment_status='o')


# 以上四个 action 在后台下拉框中的显示名称
makr_article_publish.short_description = _('Publish selected articles')
draft_article.short_description = _('Draft selected articles')
close_article_commentstatus.short_description = _('Close article comments')
open_article_commentstatus.short_description = _('Open article comments')


# 文章后台。
# 注意：类名 "ArticlelAdmin" 中多出的字母 l 是既有拼写，为保持一致性不做改动。
class ArticlelAdmin(admin.ModelAdmin):
    # 列表页每页显示 20 条
    list_per_page = 20
    # 顶部搜索框可按正文与标题检索
    search_fields = ('body', 'title')
    # 使用上面定义的表单
    form = ArticleForm
    # 列表页展示的列（其中 link_to_category 是下面自定义的方法列）
    list_display = (
        'id',
        'title',
        'author',
        'link_to_category',
        'creation_time',
        'views',
        'status',
        'type',
        'article_order')
    # 点击可进入编辑页的列
    list_display_links = ('id', 'title')
    # 右侧过滤条件
    list_filter = ('status', 'type', 'category')
    # 顶部按创建时间的钻取导航（年/月/日）
    date_hierarchy = 'creation_time'
    # 多对多字段改用左右穿梭框，文章较多时比多选下拉更易用
    filter_horizontal = ('tags',)
    # 把这两个时间字段从后台表单中排除（表单里不显示、不可编辑）。
    # 注意：模型的 default=now 并不是 auto_now / auto_now_add，
    # 所以保存时并不会自动刷新这两个时间；此处仅是不让后台手工填写。
    exclude = ('creation_time', 'last_modify_time')
    # 列表页提供"在站点上查看"按钮（跳转地址由下面的 get_view_on_site_url 决定）
    view_on_site = True
    # 挂载上面定义的四个批量操作
    actions = [
        makr_article_publish,
        draft_article,
        close_article_commentstatus,
        open_article_commentstatus]
    # 作者与分类改用原始 ID 输入框，避免用户量大/分类多时下拉列表过长
    raw_id_fields = ('author', 'category',)

    # 列表页"分类"列的渲染：输出一个可直接跳到该分类编辑页的超链接
    def link_to_category(self, obj):
        info = (obj.category._meta.app_label, obj.category._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.category.id,))
        return format_html(u'<a href="%s">%s</a>' % (link, obj.category.name))

    link_to_category.short_description = _('category')

    # 限制作者下拉框只列出超级用户，即只有管理员才能作为文章作者
    def get_form(self, request, obj=None, **kwargs):
        form = super(ArticlelAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['author'].queryset = get_user_model(
        ).objects.filter(is_superuser=True)
        return form

    # 当前方法仅调用父类的 save_model，未添加额外的保存逻辑
    def save_model(self, request, obj, form, change):
        super(ArticlelAdmin, self).save_model(request, obj, form, change)

    # 决定"在站点上查看"按钮跳向哪里：有对象时跳该文章的完整 URL，否则退回到站点域名
    def get_view_on_site_url(self, obj=None):
        if obj:
            url = obj.get_full_url()
            return url
        else:
            from djangoblog.utils import get_current_site
            site = get_current_site().domain
            return site


# 标签后台。
# 既有不一致（此处仅记录，不修改可执行代码）：exclude 中的 'last_mod_time'
# 与 Tag 继承自 BaseModel 后实际存在的字段名 'last_modify_time' 不一致，
# 该名字不对应 Tag 上的任何字段；同列表中的 slug 与 creation_time 是真实字段。
class TagAdmin(admin.ModelAdmin):
    exclude = ('slug', 'last_mod_time', 'creation_time')


# 分类后台：列表页显示名称、父分类与排序权重。
# 既有不一致（此处仅记录，不修改可执行代码）：与 TagAdmin 相同，
# exclude 中的 'last_mod_time' 与 Category 继承自 BaseModel 的实际字段名
# 'last_modify_time' 不一致，不对应任何字段。
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'index')
    exclude = ('slug', 'last_mod_time', 'creation_time')


# 友情链接后台：只排除两个时间字段（该模型本就没有 slug）。
# 这里的 'last_mod_time' 与 Links 自身定义的字段名一致，不存在上面的名字不匹配问题。
class LinksAdmin(admin.ModelAdmin):
    exclude = ('last_mod_time', 'creation_time')


# 侧边栏区块后台。'last_mod_time' 与 SideBar 自身定义的字段名一致。
class SideBarAdmin(admin.ModelAdmin):
    list_display = ('name', 'content', 'is_enable', 'sequence')
    exclude = ('last_mod_time', 'creation_time')


# 全站配置后台：把它当作"单例设置页"使用——
# 进入列表页直接跳到唯一那条记录的编辑页，并禁止新增与删除。
# 需要区分三层限制各自的范围：
#   ① 后台权限（本类的方法）—— 只约束通过 admin 界面进行的操作；
#   ② 模型 clean() 校验 —— 只在 full_clean()（如 ModelForm 校验）时触发；
#   ③ 数据库约束 —— 该模型没有任何唯一约束来保证只能存在一行。
# 详见 blog/models.py 中 BlogSettings 的注释。
class BlogSettingsAdmin(admin.ModelAdmin):
    """单例配置Admin - 直接跳转到编辑页面"""

    # 已存在配置时禁止再新增——仅限制后台的新增入口，
    # 不覆盖代码里直接调用 save() / bulk_create() 等写入路径。
    def has_add_permission(self, request):
        """如果已经存在配置，则禁止添加"""
        return not BlogSettings.objects.exists()

    # 始终禁止删除配置
    def has_delete_permission(self, request, obj=None):
        """禁止删除配置"""
        return False

    # 列表页本身没有意义，直接重定向：有记录去编辑页，没有则去新增页
    def changelist_view(self, request, extra_context=None):
        """列表页直接跳转到编辑页面"""
        from django.http import HttpResponseRedirect
        obj = BlogSettings.objects.first()
        if obj:
            return HttpResponseRedirect(
                reverse('admin:blog_blogsettings_change', args=[obj.pk])
            )
        # 如果不存在配置，跳转到添加页面
        return HttpResponseRedirect(
            reverse('admin:blog_blogsettings_add')
        )

    # 保存设置后清空缓存：配置影响全站渲染（导航/SEO/配色），必须立即失效
    def save_model(self, request, obj, form, change):
        """保存设置时清除缓存"""
        super().save_model(request, obj, form, change)
        # 确保缓存被清除
        from djangoblog.utils import cache
        cache.clear()
        self.message_user(request, '设置已保存，缓存已清除')
