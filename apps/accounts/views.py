"""
认证与账户视图
包含：登录、注册、忘记密码、个人中心、地址管理
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import User, CustomerProfile, Merchant, StaffProfile, Role, Address
from .forms import (
    PhoneLoginForm, CustomerRegisterForm, CustomerProfileForm,
    MerchantRegisterForm, AddressForm, ForgetPasswordForm
)


def user_login(request):
    """统一登录视图，根据用户类型跳转不同首页"""
    if request.user.is_authenticated:
        return _redirect_by_user_type(request.user)
    if request.method == 'POST':
        form = PhoneLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'登录成功，{user.username or user.phone}')
            return _redirect_by_user_type(user)
        else:
            error_msg = '手机号或密码错误'
            for err in form.non_field_errors():
                error_msg = err
                break
            messages.error(request, error_msg)
    else:
        form = PhoneLoginForm()
    return render(request, 'registration/login.html', {'form': form})


def _redirect_by_user_type(user):
    """根据用户类型跳转到对应首页"""
    if user.user_type == 'customer':
        return redirect('customer_dashboard')
    elif user.user_type == 'merchant_admin':
        return redirect('merchant_dashboard')
    elif user.user_type == 'merchant_staff':
        return redirect('merchant_dashboard')
    elif user.user_type == 'platform_admin':
        return redirect('admin_dashboard')
    return redirect('/')


def user_logout(request):
    """退出登录"""
    logout(request)
    messages.info(request, '您已安全退出')
    return redirect('login')


def customer_register(request):
    """终端用户注册"""
    if request.user.is_authenticated:
        return redirect('customer_dashboard')
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.user_type = 'customer'
                user.set_password(form.cleaned_data['password'])
                user.is_approved = False
                user.save()
                # 创建客户资料
                from utils.pricing_tiers import get_tier_by_province
                province = form.cleaned_data.get('province', '')
                CustomerProfile.objects.create(
                    user=user,
                    merchant=form.merchant,
                    invite_code=form.cleaned_data['invite_code'],
                    registration_status='pending',
                    company_name=form.cleaned_data.get('company_name', ''),
                    province=province,
                    city=form.cleaned_data.get('city', ''),
                    real_name=form.cleaned_data.get('real_name', ''),
                    pricing_tier=get_tier_by_province(province),
                )
            messages.success(request, '注册成功，请等待商家审核通过后方可登录。')
            return redirect('login')
    else:
        form = CustomerRegisterForm()
    return render(request, 'accounts/customer_register.html', {'form': form})


def merchant_register(request):
    """商家入驻申请"""
    if request.user.is_authenticated:
        return redirect('merchant_dashboard')
    if request.method == 'POST':
        form = MerchantRegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                merchant = form.save(commit=False)
                merchant.status = 'pending'
                # 处理服务区域JSON数据
                regions = request.POST.get('service_regions', '')
                try:
                    if regions and regions.startswith('['):
                        import json
                        json.loads(regions)  # 验证JSON有效
                        merchant.service_regions = regions
                    else:
                        merchant.service_regions = regions
                except:
                    merchant.service_regions = regions
                merchant.save()
                # 创建商家管理员账号
                user = User.objects.create_user(
                    username=form.cleaned_data['admin_phone'],
                    phone=form.cleaned_data['admin_phone'],
                    password=form.cleaned_data['admin_password'],
                    user_type='merchant_admin',
                    is_approved=False
                )
                merchant.admin_user = user
                merchant.save()
                # 创建默认角色
                for role_name, role_label in Role.ROLE_NAME_CHOICES:
                    Role.objects.create(merchant=merchant, name=role_name, custom_name=role_label)
            messages.success(request, '入驻申请已提交，请等待平台审核。')
            return redirect('login')
    else:
        form = MerchantRegisterForm()
    return render(request, 'accounts/merchant_register.html', {'form': form})


def forget_password(request):
    """忘记密码"""
    if request.method == 'POST':
        form = ForgetPasswordForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            user = User.objects.get(phone=phone)
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(request, '密码重置成功，请使用新密码登录。')
            return redirect('login')
    else:
        form = ForgetPasswordForm()
    return render(request, 'accounts/forget_password.html', {'form': form})


# ==================== 终端用户个人中心 ====================

@login_required
def profile(request):
    """个人中心"""
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('/')
    profile_obj = request.user.customer_profile
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, '个人信息已更新')
            return redirect('profile')
    else:
        form = CustomerProfileForm(instance=profile_obj)
    return render(request, 'customer/profile.html', {
        'form': form,
        'profile': profile_obj,
    })


@login_required
def my_addresses(request):
    """地址管理列表"""
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('/')
    addresses = request.user.addresses.all()
    return render(request, 'customer/addresses.html', {'addresses': addresses})


@login_required
def address_add(request):
    """添加地址"""
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('/')
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, '地址添加成功')
            return redirect('my_addresses')
    else:
        form = AddressForm()
    return render(request, 'customer/address_form.html', {'form': form, 'title': '添加地址'})


@login_required
def address_edit(request, pk):
    """编辑地址"""
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('/')
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=addr)
        if form.is_valid():
            form.save()
            messages.success(request, '地址修改成功')
            return redirect('my_addresses')
    else:
        form = AddressForm(instance=addr)
    return render(request, 'customer/address_form.html', {'form': form, 'title': '编辑地址'})


@login_required
@require_POST
def address_delete(request, pk):
    """删除地址"""
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('/')
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    addr.delete()
    messages.success(request, '地址已删除')
    return redirect('my_addresses')


# ==================== 手机号验证码登录 ====================

def api_send_verify_code(request):
    """AJAX：发送短信验证码"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '请使用POST请求'})
    phone = request.POST.get('phone', '').strip()
    if not phone or len(phone) != 11:
        return JsonResponse({'success': False, 'error': '请输入正确的11位手机号'})
    from utils.sms import send_verify_code
    success, msg = send_verify_code(phone)
    return JsonResponse({'success': success, 'message': msg})


def phone_code_login(request):
    """手机号验证码登录"""
    if request.user.is_authenticated:
        return _redirect_by_user_type(request.user)

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        code = request.POST.get('code', '').strip()

        if not phone or not code:
            messages.error(request, '请输入手机号和验证码')
            return render(request, 'registration/login.html', {'login_mode': 'phone'})

        from utils.sms import verify_sms_code
        if not verify_sms_code(phone, code):
            messages.error(request, '验证码错误或已过期')
            return render(request, 'registration/login.html', {'login_mode': 'phone'})

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            messages.error(request, '该手机号未注册')
            return render(request, 'registration/login.html', {'login_mode': 'phone'})

        # 复用密码登录的统一准入校验
        form = PhoneLoginForm(request)
        try:
            form.confirm_login_allowed(user)
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'registration/login.html', {'login_mode': 'phone'})

        login(request, user)
        messages.success(request, f'登录成功，{user.username or user.phone}')
        return _redirect_by_user_type(user)

    return render(request, 'registration/login.html', {'login_mode': 'phone'})
