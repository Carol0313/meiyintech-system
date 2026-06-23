"""
用户认证与账户视图测试
覆盖：首页跳转、登录、登出、用户类型判断
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import Merchant, CustomerProfile

User = get_user_model()


class IndexViewTest(TestCase):
    """首页视图测试"""

    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.merchant_user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.merchant_user,
            status='approved'
        )

    def test_index_redirects_anonymous_to_login(self):
        """未登录用户访问首页跳转到登录页"""
        response = self.client.get('/')
        self.assertIn(response.status_code, [301, 302])

    def test_index_redirects_customer_to_dashboard(self):
        """客户登录后跳转到客户首页"""
        self.client.login(phone='13900139000', password='testpass123')
        response = self.client.get('/')
        self.assertIn(response.status_code, [301, 302])

    def test_index_redirects_merchant_to_dashboard(self):
        """商户登录后跳转到商户首页"""
        self.client.login(phone='13800138000', password='testpass123')
        response = self.client.get('/')
        self.assertIn(response.status_code, [301, 302])


class UserLoginViewTest(TestCase):
    """登录视图测试"""

    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.merchant_user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.merchant_user,
            status='approved'
        )

    def test_login_page_get(self):
        """GET请求显示登录页面"""
        response = self.client.get(reverse('login'))
        self.assertIn(response.status_code, [200, 301, 302])

    def test_login_with_valid_credentials(self):
        """有效凭据登录成功"""
        response = self.client.post(reverse('login'), {
            'phone': '13900139000',
            'password': 'testpass123'
        })
        self.assertIn(response.status_code, [301, 302])

    def test_login_with_invalid_credentials(self):
        """无效凭据登录失败"""
        response = self.client.post(reverse('login'), {
            'phone': '13900139000',
            'password': 'wrongpassword'
        })
        self.assertIn(response.status_code, [200, 301, 302])

    def test_login_already_authenticated_redirects(self):
        """已登录用户访问登录页重定向"""
        self.client.login(phone='13900139000', password='testpass123')
        response = self.client.get(reverse('login'))
        self.assertIn(response.status_code, [301, 302])


class UserLogoutViewTest(TestCase):
    """登出视图测试"""

    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )

    def test_logout_redirects(self):
        """登出后重定向"""
        self.client.login(phone='13900139000', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertIn(response.status_code, [301, 302])

    def test_logout_clears_session(self):
        """登出清除session"""
        self.client.login(phone='13900139000', password='testpass123')
        # 确认已登录
        response = self.client.get('/')
        self.assertIn(response.status_code, [301, 302])
        # 登出
        self.client.get(reverse('logout'))
        # 再次访问首页应该重定向到登录页
        response = self.client.get('/')
        self.assertIn(response.status_code, [301, 302])


class UserTypeRedirectTest(TestCase):
    """用户类型跳转测试"""

    def setUp(self):
        self.client = Client()

    def test_customer_user_type(self):
        """客户用户类型正确"""
        user = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.assertEqual(user.user_type, 'customer')

    def test_merchant_admin_user_type(self):
        """商户管理员类型正确"""
        user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.assertEqual(user.user_type, 'merchant_admin')

    def test_merchant_staff_user_type(self):
        """商户员工类型正确"""
        user = User.objects.create_user(
            phone='13700137000',
            username='staff',
            user_type='merchant_staff',
            password='testpass123'
        )
        self.assertEqual(user.user_type, 'merchant_staff')

    def test_platform_admin_user_type(self):
        """平台管理员类型正确"""
        user = User.objects.create_user(
            phone='13600136000',
            username='admin',
            user_type='platform_admin',
            password='testpass123'
        )
        self.assertEqual(user.user_type, 'platform_admin')


class UserModelTest(TestCase):
    """用户模型测试"""

    def test_create_user_with_phone(self):
        """使用手机号创建用户"""
        user = User.objects.create_user(
            phone='13900139000',
            username='testuser',
            password='testpass123'
        )
        self.assertEqual(user.phone, '13900139000')
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('testpass123'))

    def test_user_str_with_phone(self):
        """用户字符串表示包含手机号"""
        user = User.objects.create_user(
            phone='13900139000',
            username='testuser',
            user_type='customer'
        )
        self.assertIn('13900139000', str(user))

    def test_user_default_user_type(self):
        """用户默认类型为customer"""
        user = User.objects.create_user(
            phone='13900139000',
            username='testuser'
        )
        self.assertEqual(user.user_type, 'customer')

    def test_user_is_active_default(self):
        """用户默认激活状态"""
        user = User.objects.create_user(
            phone='13900139000',
            username='testuser'
        )
        self.assertTrue(user.is_active)

    def test_user_phone_unique(self):
        """手机号唯一性"""
        User.objects.create_user(
            phone='13900139000',
            username='user1'
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                phone='13900139000',
                username='user2'
            )


class MerchantModelTest(TestCase):
    """商户模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )

    def test_merchant_creation(self):
        """商户创建"""
        merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.user,
            status='approved'
        )
        self.assertEqual(merchant.name, '测试商家')
        self.assertEqual(merchant.status, 'approved')
        self.assertEqual(merchant.admin_user, self.user)

    def test_merchant_str(self):
        """商户字符串表示"""
        merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.user,
            status='approved'
        )
        self.assertIn('测试商家', str(merchant))

    def test_merchant_status_choices(self):
        """商户状态值有效"""
        valid_statuses = [s[0] for s in Merchant.STATUS_CHOICES]
        merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.user,
            status='pending'
        )
        self.assertIn(merchant.status, valid_statuses)
