"""健康检查接口测试。"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HealthCheckTest(TestCase):
    def test_healthy_when_database_and_cache_are_available(self):
        response = self.client.get(reverse('health_check'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'healthy')
        self.assertEqual(payload['checks'], {
            'database': 'ok',
            'cache': 'ok',
        })

    def test_database_failure_returns_service_unavailable(self):
        with patch('djangoblog.urls.connection.cursor', side_effect=RuntimeError('db down')):
            response = self.client.get(reverse('health_check'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['checks']['database'], 'error')

    def test_cache_failure_returns_service_unavailable(self):
        with patch('djangoblog.urls.cache.set', side_effect=RuntimeError('cache down')):
            response = self.client.get(reverse('health_check'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['checks']['cache'], 'error')
