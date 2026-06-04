"""
阿里云 OSS 自定义 Storage 后端

使用方式：
1. 在 settings.py 中配置 OSS 参数
2. 在模型 FileField 中设置 storage=AliyunOSSStorage()
3. 或设置 DEFAULT_FILE_STORAGE = 'utils.oss_storage.AliyunOSSStorage'

OSS 配置参数（settings.py）：
    OSS_ACCESS_KEY_ID = 'your-access-key-id'
    OSS_ACCESS_KEY_SECRET = 'your-access-key-secret'
    OSS_ENDPOINT = 'oss-cn-hangzhou.aliyuncs.com'  # 根据地域修改
    OSS_BUCKET_NAME = 'your-bucket-name'
    OSS_BASE_DIR = 'magnesium/'  # 文件在bucket中的前缀目录
    OSS_INTERNAL = False  # 是否使用内网Endpoint（ECS同区域建议True）
    OSS_CUSTOM_DOMAIN = ''  # 自定义CDN域名，如 'https://cdn.example.com'
"""

import os
import mimetypes
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.base import File
from django.utils.deconstruct import deconstructible

import oss2


@deconstructible
class AliyunOSSStorage(Storage):
    """
    Django Storage backend for Alibaba Cloud OSS
    """

    def __init__(self, **kwargs):
        self.access_key_id = kwargs.get('access_key_id') or getattr(settings, 'OSS_ACCESS_KEY_ID', '')
        self.access_key_secret = kwargs.get('access_key_secret') or getattr(settings, 'OSS_ACCESS_KEY_SECRET', '')
        self.endpoint = kwargs.get('endpoint') or getattr(settings, 'OSS_ENDPOINT', '')
        self.bucket_name = kwargs.get('bucket_name') or getattr(settings, 'OSS_BUCKET_NAME', '')
        self.base_dir = kwargs.get('base_dir') or getattr(settings, 'OSS_BASE_DIR', 'magnesium/')
        self.use_internal = kwargs.get('use_internal') or getattr(settings, 'OSS_INTERNAL', False)
        self.custom_domain = kwargs.get('custom_domain') or getattr(settings, 'OSS_CUSTOM_DOMAIN', '')

        # 如果启用内网，将 endpoint 中的 .aliyuncs.com 替换为 -internal.aliyuncs.com
        if self.use_internal and '.aliyuncs.com' in self.endpoint and '-internal' not in self.endpoint:
            self.endpoint = self.endpoint.replace('.aliyuncs.com', '-internal.aliyuncs.com')

        self._bucket = None
        super().__init__()

    @property
    def bucket(self):
        if self._bucket is None:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self._bucket = oss2.Bucket(auth, f"https://{self.endpoint}", self.bucket_name)
        return self._bucket

    def _get_object_name(self, name):
        """将 Django 的相对路径转换为 OSS 的完整对象名"""
        name = name.replace('\\', '/')
        if self.base_dir:
            return f"{self.base_dir.rstrip('/')}/{name.lstrip('/')}"
        return name.lstrip('/')

    def _open(self, name, mode='rb'):
        """从 OSS 读取文件"""
        object_name = self._get_object_name(name)
        resp = self.bucket.get_object(object_name)
        return File(resp, name)

    def _save(self, name, content):
        """保存文件到 OSS"""
        object_name = self._get_object_name(name)

        # 自动检测 MIME 类型
        content_type = getattr(content, 'content_type', None)
        if not content_type:
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'

        # 获取文件内容
        if hasattr(content, 'seek'):
            content.seek(0)

        self.bucket.put_object(object_name, content, headers={'Content-Type': content_type})
        return name

    def exists(self, name):
        """检查文件是否存在于 OSS"""
        object_name = self._get_object_name(name)
        return self.bucket.object_exists(object_name)

    def delete(self, name):
        """从 OSS 删除文件"""
        object_name = self._get_object_name(name)
        try:
            self.bucket.delete_object(object_name)
        except oss2.exceptions.NoSuchKey:
            pass

    def url(self, name):
        """获取文件的访问 URL"""
        object_name = self._get_object_name(name)

        # 如果配置了自定义 CDN 域名
        if self.custom_domain:
            domain = self.custom_domain.rstrip('/')
            return f"{domain}/{object_name}"

        # 否则使用 OSS 默认 URL
        return f"https://{self.bucket_name}.{self.endpoint}/{object_name}"

    def size(self, name):
        """获取文件大小"""
        object_name = self._get_object_name(name)
        try:
            head = self.bucket.head_object(object_name)
            return head.content_length
        except oss2.exceptions.NoSuchKey:
            return 0

    def path(self, name):
        """OSS 没有本地路径，返回 URL"""
        return self.url(name)

    def get_available_name(self, name, max_length=None):
        """生成可用的文件名（OSS 会自动覆盖同名文件）"""
        return name


class AliyunOSSMediaStorage(AliyunOSSStorage):
    """
    专用于 Media 文件的 OSS Storage
    注意：如需公开访问，请在阿里云 OSS 控制台将 Bucket 设为"公共读"
    """
    def _save(self, name, content):
        object_name = self._get_object_name(name)
        content_type = getattr(content, 'content_type', None)
        if not content_type:
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'

        if hasattr(content, 'seek'):
            content.seek(0)

        headers = {
            'Content-Type': content_type,
        }
        self.bucket.put_object(object_name, content, headers=headers)
        return name
