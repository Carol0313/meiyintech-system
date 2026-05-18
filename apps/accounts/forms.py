"""
认证与账户相关表单
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User, CustomerProfile, Merchant, Address


class PhoneLoginForm(AuthenticationForm):
    """手机号登录表单"""
    username = forms.CharField(
        label='手机号', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号'})
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请输入密码'})
    )


class CustomerRegisterForm(forms.ModelForm):
    """终端用户注册表单"""
    password = forms.CharField(
        label='密码', min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password_confirm = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    invite_code = forms.CharField(
        label='商家邀请码', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入商家邀请码'})
    )
    company_name = forms.CharField(
        label='公司名称', max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    province = forms.ChoiceField(
        label='所在省份', choices=[(p, p) for p in [
            '北京', '上海', '天津', '重庆',
            '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
            '江苏', '浙江', '安徽', '福建', '江西', '山东',
            '河南', '湖北', '湖南', '广东', '广西', '海南',
            '四川', '贵州', '云南', '西藏', '陕西', '甘肃',
            '青海', '宁夏', '新疆', '香港', '澳门', '台湾'
        ]],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    city = forms.CharField(
        label='城市', max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    real_name = forms.CharField(
        label='真实姓名', max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['phone', 'username']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '登录用户名'}),
        }

    def clean_invite_code(self):
        code = self.cleaned_data.get('invite_code')
        try:
            self.merchant = Merchant.objects.get(invite_code=code, status='approved')
        except Merchant.DoesNotExist:
            raise forms.ValidationError('邀请码无效或商家未通过审核')
        return code

    def clean_password_confirm(self):
        pwd = self.cleaned_data.get('password')
        pwd2 = self.cleaned_data.get('password_confirm')
        if pwd and pwd2 and pwd != pwd2:
            raise forms.ValidationError('两次输入的密码不一致')
        return pwd2

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('该手机号已被注册')
        return phone


class CustomerProfileForm(forms.ModelForm):
    """终端用户资料修改表单"""
    class Meta:
        model = CustomerProfile
        fields = ['company_name', 'city', 'real_name']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'real_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class MerchantRegisterForm(forms.ModelForm):
    """商家入驻申请表单"""
    admin_phone = forms.CharField(
        label='管理员手机号', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    admin_password = forms.CharField(
        label='管理员密码', min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Merchant
        fields = ['name', 'address', 'service_regions', 'contact_phone', 'customer_service_wechat']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'service_regions': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如：上海,江苏,浙江'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_service_wechat': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_admin_phone(self):
        phone = self.cleaned_data.get('admin_phone')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('该手机号已被注册')
        return phone


class AddressForm(forms.ModelForm):
    """收货地址表单"""
    class Meta:
        model = Address
        fields = ['contact_name', 'phone', 'province', 'city', 'district', 'detail', 'is_default']
        widgets = {
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'detail': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ForgetPasswordForm(forms.Form):
    """忘记密码表单"""
    phone = forms.CharField(label='手机号', max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    new_password = forms.CharField(label='新密码', min_length=6, widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password_confirm = forms.CharField(label='确认新密码', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('该手机号未注册')
        return phone

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') != cleaned.get('new_password_confirm'):
            raise forms.ValidationError('两次输入的密码不一致')
        return cleaned
