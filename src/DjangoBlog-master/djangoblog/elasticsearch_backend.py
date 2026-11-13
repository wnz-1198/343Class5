# ZZC: 本模块实现 Haystack 的 Elasticsearch 后端、查询对象和搜索表单。
from django.utils.encoding import force_str
from elasticsearch_dsl import Q
from haystack.backends import BaseEngine, BaseSearchBackend, BaseSearchQuery, log_query
from haystack.forms import ModelSearchForm
from haystack.models import SearchResult
from haystack.utils import log as logging

from blog.documents import ArticleDocument, ArticleDocumentManager
from blog.models import Article

logger = logging.getLogger(__name__)


# ZZC: ElasticSearchBackend 负责索引更新、删除、推荐词和文章搜索。
class ElasticSearchBackend(BaseSearchBackend):
    # ZZC: 接入 ArticleDocumentManager，并默认启用搜索推荐词。
    def __init__(self, connection_alias, **connection_options):
        super(
            ElasticSearchBackend,
            self).__init__(
            connection_alias,
            **connection_options)
        self.manager = ArticleDocumentManager()
        self.include_spelling = True

    # ZZC: 空集合回退到全部文章；否则把模型对象转换为 Elasticsearch 文档。
    def _get_models(self, iterable):
        models = iterable if iterable and iterable[0] else Article.objects.all()
        docs = self.manager.convert_to_doc(models)
        return docs

    # ZZC: 建立索引后用转换后的文档执行全量重建。
    def _create(self, models):
        self.manager.create_index()
        docs = self._get_models(models)
        self.manager.rebuild(docs)

    # ZZC: 删除传入的文档对象并返回成功标记。
    def _delete(self, models):
        for m in models:
            m.delete()
        return True

    # ZZC: 传入空集合时重建全部文章，否则只更新指定文档。
    def _rebuild(self, models):
        models = models if models else Article.objects.all()
        docs = self.manager.convert_to_doc(models)
        self.manager.update_docs(docs)

    # ZZC: Haystack 更新索引时调用此方法，将模型数据写入 Elasticsearch。
    def update(self, index, iterable, commit=True):

        models = self._get_models(iterable)
        self.manager.update_docs(models)

    # ZZC: 删除指定文章对应的搜索文档。
    def remove(self, obj_or_string):
        models = self._get_models([obj_or_string])
        self._delete(models)

    # ZZC: 清空索引时复用 remove(None) 的全量删除分支。
    def clear(self, models=None, commit=True):
        self.remove(None)

    # ZZC: 使用文章正文的 term suggestion 返回推荐查询词。
    @staticmethod
    def get_suggestion(query: str) -> str:
        """获取推荐词, 如果没有找到添加原搜索词"""

        search = ArticleDocument.search() \
            .query("match", body=query) \
            .suggest('suggest_search', query, term={'field': 'body'}) \
            .execute()

        keywords = []
        for suggest in search.suggest.suggest_search:
            if suggest["options"]:
                keywords.append(suggest["options"][0]["text"])
            else:
                keywords.append(suggest["text"])

        return ' '.join(keywords)

    # ZZC: 同时匹配标题和正文，只返回已发布文章，并支持分页、高亮和推荐词。
    @log_query
    def search(self, query_string, **kwargs):
        logger.info('search query_string:' + query_string)

        start_offset = kwargs.get('start_offset')
        end_offset = kwargs.get('end_offset')
        highlight = kwargs.get('highlight', True)  # 默认启用高亮

        # ZZC: 允许调用方基于原始关键词生成推荐词，再使用推荐词执行正式搜索。
        if getattr(self, "is_suggest", None):
            suggestion = self.get_suggestion(query_string)
        else:
            suggestion = query_string

        q = Q('bool',
              should=[Q('match', body=suggestion), Q('match', title=suggestion)],
              minimum_should_match=1)  # 至少匹配1个should子句

        search = ArticleDocument.search() \
                     .query('bool', filter=[q]) \
                     .filter('term', status='p') \
                     .filter('term', type='a')

        # ZZC: 配置标题和正文的高亮标签及片段数量，便于搜索页面展示命中上下文。
        if highlight:
            search = search.highlight('title', 'body',
                                    fragment_size=150,  # 片段大小
                                    number_of_fragments=3,  # 片段数量
                                    pre_tags=['<mark>'],  # 高亮开始标签
                                    post_tags=['</mark>'])  # 高亮结束标签

        search = search.source(False)[start_offset: end_offset]

        results = search.execute()
        # ZZC: 兼容 ES 8.x 的 total 对象结构和旧版本的整数结构。
        hits_total = results['hits']['total']
        hits = hits_total['value'] if isinstance(hits_total, dict) else hits_total
        raw_results = []
        for raw_result in results['hits']['hits']:
            app_label = 'blog'
            model_name = 'Article'
            additional_fields = {}

            # 添加高亮内容
            if highlight and 'highlight' in raw_result:
                highlighted = {}
                if 'title' in raw_result['highlight']:
                    highlighted['title'] = raw_result['highlight']['title']
                if 'body' in raw_result['highlight']:
                    highlighted['body'] = raw_result['highlight']['body']

                if highlighted:
                    additional_fields['highlighted'] = highlighted

            result_class = SearchResult

            result = result_class(
                app_label,
                model_name,
                raw_result['_id'],
                raw_result['_score'],
                **additional_fields)
            raw_results.append(result)
        facets = {}
        spelling_suggestion = None if query_string == suggestion else suggestion

        return {
            'results': raw_results,
            'hits': hits,
            'facets': facets,
            'spelling_suggestion': spelling_suggestion,
        }


# ZZC: ElasticSearchQuery 负责时间格式转换、特殊字符清理和查询参数构建。
class ElasticSearchQuery(BaseSearchQuery):
    # ZZC: 将日期时间统一转换为 Elasticsearch 可识别的紧凑字符串格式。
    def _convert_datetime(self, date):
        if hasattr(date, 'hour'):
            return force_str(date.strftime('%Y%m%d%H%M%S'))
        else:
            return force_str(date.strftime('%Y%m%d000000'))

    # ZZC: 清理查询片段中的保留词，避免用户输入被解释为查询语法。
    def clean(self, query_fragment):
        """
        Provides a mechanism for sanitizing user input before presenting the
        value to the backend.

        Whoosh 1.X differs here in that you can no longer use a backslash
        to escape reserved characters. Instead, the whole word should be
        quoted.
        """
        words = query_fragment.split()
        cleaned_words = []

        for word in words:
            if word in self.backend.RESERVED_WORDS:
                word = word.replace(word, word.lower())

            for char in self.backend.RESERVED_CHARACTERS:
                if char in word:
                    word = "'%s'" % word
                    break

            cleaned_words.append(word)

        return ' '.join(cleaned_words)

    # ZZC: 当前实现直接使用预构建的 query_string，不再生成普通字段片段。
    def build_query_fragment(self, field, filter_type, value):
        return value.query_string

    # ZZC: 获取结果数量；无结果时返回零。
    def get_count(self):
        results = self.get_results()
        return len(results) if results else 0

    # ZZC: 返回后端记录的拼写建议。
    def get_spelling_suggestion(self, preferred_query=None):
        return self._spelling_suggestion

    # ZZC: 复用 Haystack 的默认参数构建逻辑。
    def build_params(self, spelling_query=None):
        kwargs = super(ElasticSearchQuery, self).build_params(spelling_query=spelling_query)
        return kwargs


# ZZC: 搜索表单根据 is_suggest 参数决定是否启用推荐词。
class ElasticSearchModelSearchForm(ModelSearchForm):

    # ZZC: 将表单参数写入后端实例，再调用父类完成搜索。
    def search(self):
        # 是否建议搜索
        self.searchqueryset.query.backend.is_suggest = self.data.get("is_suggest") != "no"
        sqs = super().search()
        return sqs


# ZZC: Engine 把 Haystack 的 backend 和 query 组合成可配置搜索引擎。
class ElasticSearchEngine(BaseEngine):
    backend = ElasticSearchBackend
    query = ElasticSearchQuery
